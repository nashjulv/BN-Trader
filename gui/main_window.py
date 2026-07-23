"""
主窗口 — 匹配 docs/UI设计.png

┌──────┬──────────────────────────────────────────────────────────┐
│ Side │  顶栏 PnlBar                                              │
│ Bar  ├──────────┬────────────────────────────┬──────────────────┤
│ 图标 │ 行情场景  │                            │   手动下单        │
│ 导航 │ 资金概览  │         K 线图              │                  │
│      │ 风控状态  │                            │                  │
│      │ 当前持仓  ├────────────────────────────┤                  │
│      │          │       交易日志              │                  │
├──────┴──────────┴────────────────────────────┴──────────────────┤
│  状态栏                                                          │
└─────────────────────────────────────────────────────────────────┘

侧栏切换：主界面 / 策略 / 资金 / 风控 / 持仓 / 日志 / 回测 / API设置
"""

import logging
from typing import Dict, Optional

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
                               QSplitter, QStackedWidget, QMessageBox, QStatusBar,
                               QLabel, QScrollArea, QFrame)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QSettings
from PyQt6.QtGui import QAction, QKeySequence

import pandas as pd

from gui.styles import Theme
from gui.sidebar import SideBar
from gui.pnl_bar import PnlBar
from gui.api_settings_dialog import ApiSettingsPage
from gui.chart_widget import ChartWidget
from gui.capital_panel import CapitalPanel
from gui.scene_panel import ScenePanel
from gui.risk_panel import RiskPanel
from gui.trade_panel import TradePanel
from gui.position_panel import PositionPanel
from gui.log_panel import LogPanel
from gui.strategy_settings_dialog import (StrategySettingsPage,
                                            load_strategy_settings,
                                            SETTINGS_PATH as STRATEGY_SETTINGS_PATH,
                                            LEGACY_SETTINGS_PATH as LEGACY_STRATEGY_SETTINGS_PATH)
from gui.global_settings_dialog import (RiskSettingsPage, PositionSettingsPage,
                                          CapitalSettingsPage,
                                          load_global_settings)
from gui.review_dialog import ReviewDialog
from gui.help_center import HelpCenterPage
from gui.automation_page import AutomationPage

from services.binance_client import BinanceClient
from services.account_sync import AccountSyncService
from services.scene_detector import SceneDetector, Scene
from services.capital_pool import CapitalPool
from services.risk_manager import RiskManager, RiskCheck
from services.strategy_engine import StrategyEngine
from services.automation_manager import (
    AutomationManager, RUNNING, EVALUATING
)
from services.automation_worker import AutomationEvaluationWorker
from strategies.base import SignalType

from indicators.technical import calculate_all_indicators
from config import Config

logger = logging.getLogger(__name__)


class DataWorker(QThread):
    data_updated = pyqtSignal(dict)

    def __init__(self, client: BinanceClient, symbol: str, timeframe: str):
        super().__init__()
        self.client = client
        self.symbol = symbol
        self.timeframe = timeframe
        self.running = True

    def run(self):
        while self.running:
            try:
                klines = self.client.get_klines(self.symbol, self.timeframe, limit=100)
                if klines:
                    df = BinanceClient.klines_to_dataframe(klines)
                    df["symbol"] = self.symbol
                    ticker = self.client.get_ticker_24h(self.symbol)
                    self.data_updated.emit({
                        "klines": df, "symbol": self.symbol,
                        "current_price": float(ticker.get("lastPrice", 0)),
                        "price_change": float(ticker.get("priceChangePercent", 0)),
                    })
            except Exception as e:
                logger.error(f"数据获取失败: {e}")
            self.sleep(Config.CHART_UPDATE_INTERVAL // 1000)

    def stop(self):
        self.running = False


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        Theme.set(QSettings("BN-Trader", "BN-Trader").value(
            "theme", "light", type=str))
        self.setWindowTitle(f"{Config.APP_NAME} v{Config.APP_VERSION}")
        self.resize(1440, 840)
        self.setMinimumSize(1180, 720)

        self.client = BinanceClient()
        self.account_sync = AccountSyncService(self.client)
        self.scene_detector = SceneDetector()
        self.capital_pool = CapitalPool()
        self.risk_manager = RiskManager()
        self.strategy_engine = StrategyEngine()
        self.automation_manager = AutomationManager()
        self.automation_worker: Optional[AutomationEvaluationWorker] = None

        self.data_worker: Optional[DataWorker] = None
        self.current_symbol = "BTCUSDT"
        self.current_timeframe = "15m"
        self.current_klines: Optional[pd.DataFrame] = None
        self.current_scene: Optional[Scene] = None
        self.positions = []
        self._last_auto_signals = {}
        self._auto_trading = False
        self._strategy_configured = self._check_strategy_configured()
        self._apply_saved_strategy_params()

        self._init_ui()
        self._apply_global_settings(load_global_settings(), announce=False)
        self.pnl_bar.set_api_status(self.client.has_keys())

        self.account_sync.balances_updated.connect(self._on_balances_updated)
        self.account_sync.total_value_updated.connect(self._on_total_value_updated)
        self.account_sync.error_occurred.connect(
            lambda msg: self.log_panel.add_system_log(msg, "ERROR"))
        self.capital_panel._sync_btn.clicked.connect(self._sync_account)

        self._init_menu()
        self._apply_theme()
        self._start_data_worker()

        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._periodic_update)
        self.update_timer.start(1000)

        self.automation_timer = QTimer()
        self.automation_timer.timeout.connect(self._automation_tick)
        self.automation_timer.start(1000)

        logger.info("主窗口初始化完成")

    # ==================================================================
    #  布局
    # ==================================================================

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ---- 侧栏 ----
        self.sidebar = SideBar()
        self.sidebar.navigated.connect(self._on_sidebar_nav)
        root.addWidget(self.sidebar)

        # ---- 右侧内容栈 ----
        self.page_stack = QStackedWidget()
        root.addWidget(self.page_stack, 1)

        # 页面索引
        self._pages = {}
        self._pages["dashboard"] = self._build_dashboard()
        self.page_stack.addWidget(self._pages["dashboard"])

        self.automation_page = AutomationPage(self.automation_manager)
        self.automation_page.start_requested.connect(self._start_automation_task)
        self.automation_page.stop_requested.connect(self._stop_automation_task)
        self.automation_page.start_all_requested.connect(
            self._start_all_automation_tasks)
        self.automation_page.stop_all_requested.connect(
            self._stop_all_automation_tasks)
        self._pages["automation"] = self.automation_page
        self.page_stack.addWidget(self._pages["automation"])

        self._pages["strategy"] = StrategySettingsPage()
        self._pages["strategy"].settings_saved.connect(self._on_strategy_saved)
        self.page_stack.addWidget(self._pages["strategy"])

        self._pages["capital"] = CapitalSettingsPage()
        self._pages["capital"].settings_saved.connect(self._on_global_saved)
        self.page_stack.addWidget(self._pages["capital"])

        self._pages["risk"] = RiskSettingsPage()
        self._pages["risk"].settings_saved.connect(self._on_global_saved)
        self.page_stack.addWidget(self._pages["risk"])

        self._pages["position"] = PositionSettingsPage()
        self._pages["position"].settings_saved.connect(self._on_global_saved)
        self.page_stack.addWidget(self._pages["position"])

        self.log_detail = LogPanel(detail_mode=True)
        self._pages["logs"] = self.log_detail
        self.page_stack.addWidget(self._pages["logs"])

        self._pages["backtest"] = self._build_placeholder("回测", "回测功能即将上线")
        self.page_stack.addWidget(self._pages["backtest"])

        self.help_page = HelpCenterPage()
        self._pages["help"] = self.help_page
        self.page_stack.addWidget(self._pages["help"])

        self._pages["research"] = self._build_placeholder(
            "AI 研究报告", "研报功能建设中"
        )
        self.page_stack.addWidget(self._pages["research"])

        self.api_page = ApiSettingsPage()
        self.api_page._save_btn.clicked.connect(self._on_api_page_saved)
        self.api_page._cancel_btn.clicked.connect(
            lambda: self._on_sidebar_nav("dashboard"))
        self._pages["settings"] = self.api_page
        self.page_stack.addWidget(self._pages["settings"])

        # ---- 状态栏 ----
        self._status_msg = QLabel("就绪")
        self._status_scene = QLabel("场景 ---")
        self._status_risk = QLabel("风控 ---")
        self._status_api = QLabel("API ---")
        sb = QStatusBar()
        sb.addWidget(self._status_msg)
        sb.addPermanentWidget(self._status_scene)
        sb.addPermanentWidget(self._status_risk)
        sb.addPermanentWidget(self._status_api)
        self.setStatusBar(sb)

    def _build_dashboard(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 顶栏
        self.pnl_bar = PnlBar()
        self.pnl_bar.mode_changed.connect(self._on_mode_changed)
        self.pnl_bar.theme_toggled.connect(self._on_theme_toggled)
        self.pnl_bar.api_settings_clicked.connect(
            lambda: self._on_sidebar_nav("settings"))
        self.pnl_bar.symbol_changed.connect(self._on_symbol_changed)
        layout.addWidget(self.pnl_bar)

        # 三栏主体
        self.body_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.body_splitter.setHandleWidth(1)
        self.body_splitter.setChildrenCollapsible(False)

        # --- 左栏：堆叠卡片 ---
        left_scroll = QScrollArea()
        self.left_scroll = left_scroll
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        left_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        left_scroll.setMinimumWidth(220)
        left_scroll.setMaximumWidth(300)

        left_inner = QWidget()
        self.left_inner = left_inner
        left_inner.setObjectName("dashboardLeftContent")
        lv = QVBoxLayout(left_inner)
        lv.setContentsMargins(10, 10, 6, 10)
        lv.setSpacing(10)

        self.scene_panel = ScenePanel(compact=True)
        self.capital_panel = CapitalPanel(compact=True)
        self.risk_panel = RiskPanel(compact=True)
        self.position_panel = PositionPanel(compact=True)

        lv.addWidget(self.scene_panel)
        lv.addWidget(self.capital_panel)
        lv.addWidget(self.risk_panel)
        lv.addWidget(self.position_panel)
        lv.addStretch()
        left_scroll.setWidget(left_inner)
        self.body_splitter.addWidget(left_scroll)

        # --- 中栏：K线 + 日志 ---
        center_splitter = QSplitter(Qt.Orientation.Vertical)
        center_splitter.setHandleWidth(1)
        center_splitter.setChildrenCollapsible(False)

        chart_wrap = QFrame()
        chart_wrap.setObjectName("cardFrame")
        cw = QVBoxLayout(chart_wrap)
        cw.setContentsMargins(8, 8, 8, 8)
        self.chart_widget = ChartWidget()
        self.chart_widget.request_data.connect(self._on_chart_data_request)
        cw.addWidget(self.chart_widget)
        center_splitter.addWidget(chart_wrap)

        self.log_panel = LogPanel(detail_mode=False)
        center_splitter.addWidget(self.log_panel)

        center_splitter.setStretchFactor(0, 65)
        center_splitter.setStretchFactor(1, 35)
        self.body_splitter.addWidget(center_splitter)

        # --- 右栏：下单 ---
        right_wrap = QWidget()
        rv = QVBoxLayout(right_wrap)
        rv.setContentsMargins(6, 10, 10, 10)
        self.trade_panel = TradePanel()
        self.trade_panel.place_order.connect(self._on_place_order)
        rv.addWidget(self.trade_panel)
        right_wrap.setMinimumWidth(230)
        right_wrap.setMaximumWidth(300)
        self.body_splitter.addWidget(right_wrap)

        self.body_splitter.setStretchFactor(0, 22)
        self.body_splitter.setStretchFactor(1, 50)
        self.body_splitter.setStretchFactor(2, 28)
        self.body_splitter.setSizes([240, 760, 260])

        layout.addWidget(self.body_splitter, 1)
        return page

    def _build_placeholder(self, title: str, msg: str) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        t = QLabel(title)
        t.setStyleSheet("font-size:22px; font-weight:700;")
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        m = QLabel(msg)
        m.setObjectName("captionLabel")
        m.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(t)
        lay.addWidget(m)
        return w

    # ==================================================================
    #  侧栏导航
    # ==================================================================

    def _on_sidebar_nav(self, key: str):
        page = self._pages.get(key)
        if page is None:
            return
        self.page_stack.setCurrentWidget(page)
        self.sidebar.set_active(key)
        if key == "logs":
            self.log_detail.sync_from(self.log_panel)
        if key == "dashboard":
            self._status_msg.setText("主界面")
        else:
            names = {
                "strategy": "策略设置", "capital": "资金设置",
                "automation": "自动化任务台",
                "risk": "风控设置", "position": "持仓设置",
                "logs": "日志详情", "backtest": "回测",
                "help": "帮助中心",
                "research": "AI 研究报告 · 建设中",
                "settings": "API 设置",
            }
            self._status_msg.setText(names.get(key, key))

    # ==================================================================
    #  主题
    # ==================================================================

    def _apply_theme(self):
        # 使用应用级样式，确保 QMessageBox 和所有顶层 QDialog 也继承主题。
        app = QApplication.instance()
        if app:
            app.setStyleSheet(Theme.stylesheet())
        self.setStyleSheet("")
        t = Theme.colors()
        self.body_splitter.setStyleSheet(
            f"QSplitter {{ background:transparent; }} "
            f"QSplitter::handle {{ background:{t['divider']}; }} "
            f"QSplitter::handle:hover {{ background:{t['hover_border']}; }}")
        self.pnl_bar._restyle()
        self.chart_widget._apply_theme()
        self.sidebar._apply_theme()
        self.left_inner.setStyleSheet(
            f"QWidget#dashboardLeftContent {{ background:{t['bg_main']}; }}"
            f"QWidget#dashboardLeftContent QLabel {{ background:transparent; }}")
        self.left_scroll.viewport().setStyleSheet(
            f"background:{t['bg_main']};")

        for attr in ['_status_msg', '_status_scene', '_status_risk', '_status_api']:
            lbl = getattr(self, attr, None)
            if lbl:
                lbl.setStyleSheet(f"color:{t['text_secondary']}; font-size:12px;")

        for panel in [self.scene_panel, self.capital_panel, self.risk_panel,
                       self.position_panel, self.log_panel, self.trade_panel,
                       self.log_detail]:
            if hasattr(panel, '_refresh_theme'):
                panel._refresh_theme()

        # 图表卡片
        for frame in self.findChildren(QFrame, "cardFrame"):
            frame.setStyleSheet(Theme.card_style())

        for page in [self._pages.get("strategy"), self._pages.get("risk"),
                      self._pages.get("position"), self._pages.get("capital"),
                      self.api_page, self.help_page, self.automation_page]:
            if page and hasattr(page, '_refresh_theme'):
                page._refresh_theme()

    def _on_theme_toggled(self, new_theme: str):
        QSettings("BN-Trader", "BN-Trader").setValue("theme", new_theme)
        self._apply_theme()
        self._update_all_panels()
        self.log_panel.add_system_log(
            f"主题切换: {'暗黑' if new_theme == 'dark' else '明亮'}")

    # ==================================================================
    #  菜单
    # ==================================================================

    def _init_menu(self):
        mb = self.menuBar()
        f = mb.addMenu("文件")
        f.addAction(QAction("API 配置", self,
                            triggered=lambda: self._on_sidebar_nav("settings")))
        f.addAction(QAction("导出交易记录", self))
        f.addSeparator()
        f.addAction(QAction("退出", self, triggered=self.close))
        t = mb.addMenu("交易")
        t.addAction(QAction("策略参数设定", self,
                            triggered=lambda: self._on_sidebar_nav("strategy")))
        t.addAction(QAction("重置日度统计", self, triggered=self._reset_daily))
        t.addSeparator()
        t.addAction(QAction("切换自动/手动", self,
                            triggered=lambda: self.pnl_bar.auto_btn.click()))
        h = mb.addMenu("帮助")
        help_action = QAction("帮助中心", self)
        help_action.setShortcut(QKeySequence("F1"))
        help_action.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        help_action.triggered.connect(lambda: self._on_sidebar_nav("help"))
        self.addAction(help_action)
        h.addAction(help_action)
        h.addAction(QAction("关于", self, triggered=self._show_about))
        # 设计稿使用应用内导航；保留快捷菜单能力但不占用窗口内容高度。
        mb.setVisible(False)

    # ==================================================================
    #  数据
    # ==================================================================

    def _start_data_worker(self):
        if self.data_worker:
            self.data_worker.stop()
            self.data_worker.wait()
        self.data_worker = DataWorker(
            self.client, self.current_symbol, self.current_timeframe)
        self.data_worker.data_updated.connect(self._on_data_updated)
        self.data_worker.start()
        self.log_panel.add_system_log(
            f"订阅: {self.current_symbol} {self.current_timeframe}")

    def _on_data_updated(self, data: Dict):
        try:
            df = data.get("klines")
            price = data.get("current_price", 0)
            change = data.get("price_change", 0)
            self.pnl_bar.update_price(
                data.get("symbol", self.current_symbol), price, change)

            if df is not None and not df.empty:
                self.current_klines = df
                self.chart_widget.update_data(df, current_price=price)
                self.trade_panel.update_price(price)

                df_ind = calculate_all_indicators(df.copy())
                scene = self.scene_detector.detect(df_ind)
                self.current_scene = scene

                self.scene_panel.update_scene({
                    "type": scene.type, "confidence": scene.confidence,
                    "trend_strength": scene.trend_strength,
                    "volatility": scene.volatility,
                    "volume_change": scene.volume_change,
                    "price_position": scene.price_position,
                    "is_breakout": scene.is_breakout,
                    "is_divergence": scene.is_divergence,
                })
                self._status_scene.setText(
                    f"{scene.type} ({scene.confidence:.0%})")

            self._update_all_panels()
            t = Theme.colors()
            ok = self.client.has_keys()
            self._status_api.setText("API ✓" if ok else "API ✗")
            self._status_api.setStyleSheet(
                f"color:{t['success'] if ok else t['danger']}; font-size:12px;")

        except Exception as e:
            logger.error(f"数据处理: {e}")

    def _on_chart_data_request(self, symbol: str, timeframe: str):
        self.current_symbol = symbol
        self.current_timeframe = timeframe
        self._start_data_worker()

    def _on_symbol_changed(self, symbol: str):
        self.current_symbol = symbol
        self.chart_widget.symbol_combo.blockSignals(True)
        idx = self.chart_widget.symbol_combo.findText(symbol)
        if idx >= 0:
            self.chart_widget.symbol_combo.setCurrentIndex(idx)
        self.chart_widget.symbol_combo.blockSignals(False)
        self.trade_panel.symbol_combo.setCurrentText(symbol)
        self._start_data_worker()

    # ==================================================================
    #  交易
    # ==================================================================

    def _on_place_order(self, symbol, side, qty, price, sl, tp):
        self._execute_order(symbol, side, qty, price, sl, tp, confirm=True)

    def _execute_order(self, symbol, side, qty, price, sl=0, tp=0,
                       confirm: bool = False, automatic: bool = False,
                       task_id: str = ""):
        check = self.risk_manager.check_trade_permission(
            self.capital_pool.total, qty * price, price, sl)
        if not check.allowed:
            if automatic:
                self.log_panel.add_risk_log(
                    f"自动任务被风控拦截: {check.message}", check.level)
            else:
                self._show_risk_warning(check)
            return False
        can, reason = self.capital_pool.can_trade()
        if not can:
            if automatic:
                self.log_panel.add_risk_log(
                    f"自动任务停止执行: {reason}", "STOP")
            else:
                QMessageBox.warning(self, "交易禁止", reason)
            return False
        # 0=限价 1=市价
        order_type = (
            "MARKET" if automatic else
            ("LIMIT" if self.trade_panel.type_group.checkedId() == 0 else "MARKET")
        )
        order_status = "FILLED"
        if confirm:
            reply = QMessageBox.question(
                self, "确认交易",
                f"{side} {symbol}\n数量:{qty:.4f} 价格:{price:.2f}\n"
                f"类型:{order_type}\n止损:{sl:.2f} 止盈:{tp:.2f}",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply != QMessageBox.StandardButton.Yes:
                return False
        if self.client.has_keys():
            result = self.account_sync.execute_real_order(
                symbol, side, qty, price, order_type)
            if result and result.get("status") in ("FILLED", "NEW"):
                order_status = result["status"]
                self.log_panel.add_trade_log(
                    f"实盘 {side} {symbol} {qty:.4f}@{price:.2f} [{result['status']}]",
                    "SUCCESS")
                self._sync_account()
            else:
                self.log_panel.add_system_log("下单失败", "CRITICAL")
                return False
        else:
            self.log_panel.add_trade_log(
                f"模拟 {side} {symbol} {qty:.4f}@{price:.2f}", "WARNING")
        cap = qty * price
        if not self.capital_pool.lock_capital(cap):
            QMessageBox.warning(self, "资金不足", "可用资金不足，无法提交订单。")
            return False
        if order_status == "NEW":
            self._update_all_panels()
            return True
        self.capital_pool.add_margin(cap)
        self.positions.append({
            "symbol": symbol,
            "side": side,
            "quantity": qty,
            "entry_price": price,
            "current_price": price,
            "stop_loss": sl,
            "take_profit": tp,
            "capital_used": cap,
            "pnl": 0.0,
            "pnl_ratio": 0.0,
            "automatic": automatic,
            "task_id": task_id,
        })
        self._update_all_panels()
        return True

    # ==================================================================
    #  自动化任务台
    # ==================================================================

    def _start_automation_task(self, task_id: str):
        if not self._strategy_configured:
            QMessageBox.information(
                self, "请先配置策略",
                "启动自动化任务前，请先保存策略参数。")
            self._on_sidebar_nav("strategy")
            return
        try:
            self.automation_manager.start(task_id)
        except ValueError as error:
            QMessageBox.warning(self, "无法启动", str(error))
            return
        task = self.automation_manager.get(task_id)
        self._auto_trading = True
        self.pnl_bar.set_auto_mode(True)
        self.trade_panel.set_manual_enabled(False)
        self.automation_page.add_log(f"已手动启动：{task.name}")
        self.log_panel.add_system_log(f"自动任务启动: {task.name}")
        self.automation_page.refresh()

    def _stop_automation_task(self, task_id: str):
        task = self.automation_manager.get(task_id)
        self.automation_manager.stop(task_id)
        if task:
            self.automation_page.add_log(f"已停止：{task.name}")
            self.log_panel.add_system_log(f"自动任务停止: {task.name}")
        self._sync_automation_master_state()
        self.automation_page.refresh()

    def _start_all_automation_tasks(self):
        if not self._strategy_configured:
            QMessageBox.information(
                self, "请先配置策略",
                "启动自动化任务前，请先保存策略参数。")
            self._on_sidebar_nav("strategy")
            return
        try:
            self.automation_manager.validate_allocations()
            enabled_tasks = [
                task for task in self.automation_manager.tasks
                if self.automation_manager.allocation_for(task.symbol)
            ]
            if not enabled_tasks:
                raise ValueError("没有可启动的投资币种或自动化任务")
            for task in enabled_tasks:
                self.automation_manager.start(task.id)
        except ValueError as error:
            QMessageBox.warning(self, "无法启动全部任务", str(error))
            return
        self._auto_trading = True
        self.pnl_bar.set_auto_mode(True)
        self.trade_panel.set_manual_enabled(False)
        self.automation_page.add_log("已由客户手动启动全部任务")
        self.log_panel.add_system_log("全部自动化任务已启动")
        self.automation_page.refresh()

    def _stop_all_automation_tasks(self):
        self.automation_manager.stop_all()
        self.automation_page.add_log("已停止全部自动化任务")
        self.log_panel.add_system_log("全部自动化任务已停止")
        self._sync_automation_master_state()
        self.automation_page.refresh()

    def _sync_automation_master_state(self):
        active = self.automation_manager.running_count() > 0
        self._auto_trading = active
        self.pnl_bar.set_auto_mode(active)
        self.trade_panel.set_manual_enabled(not active)

    def _automation_tick(self):
        if not self._auto_trading:
            return
        task = self.automation_manager.due_task()
        if not task:
            return
        self.automation_manager.mark_evaluating(task.id)
        self.automation_page.refresh()
        self.automation_page.add_log(
            f"{task.symbol} · 开始评估 {task.strategy} 策略")
        self.automation_worker = AutomationEvaluationWorker(
            task, load_strategy_settings())
        self.automation_worker.evaluated.connect(
            self._on_automation_evaluated)
        self.automation_worker.finished.connect(
            self._on_automation_worker_finished)
        self.automation_worker.start()

    def _on_automation_worker_finished(self):
        worker = self.automation_worker
        self.automation_worker = None
        if worker:
            worker.deleteLater()

    def _on_automation_evaluated(self, task_id: str, result: dict):
        task = self.automation_manager.get(task_id)
        if not task:
            return
        was_stopped = task.status == "STOPPED"
        ok = bool(result.get("ok"))
        message = result.get("message", "评估完成")
        self.automation_manager.finish_evaluation(
            task_id, message, success=ok)
        if was_stopped:
            self.automation_page.add_log(
                f"{task.symbol} · 任务已停止，本轮结果已忽略")
            self._sync_automation_master_state()
            self.automation_page.refresh()
            return
        self.automation_page.add_log(f"{task.symbol} · {message}")

        signal = result.get("signal")
        if ok and signal:
            signal_key = (
                signal["side"], round(signal["price"], 6), signal["reason"]
            )
            if self._last_auto_signals.get(task_id) != signal_key:
                self._execute_automation_signal(task, result, signal, signal_key)
        elif not ok:
            self.log_panel.add_system_log(
                f"自动任务异常 {task.name}: {message}", "ERROR")
        self._sync_automation_master_state()
        self.automation_page.refresh()

    def _execute_automation_signal(
        self, task, result: dict, signal: dict, signal_key
    ):
        allocation = self.automation_manager.allocation_for(task.symbol)
        if not allocation:
            self.automation_page.add_log(
                f"{task.symbol} · 资金分配已停用，未下单")
            return
        task_budget = self.capital_pool.total * allocation.allocation_ratio
        used = sum(
            position.get("capital_used", 0)
            for position in self.positions
            if position.get("automatic")
            and position.get("symbol") == task.symbol
        )
        remaining_budget = max(0.0, task_budget - used)
        task_order_limit = task_budget * task.per_trade_ratio
        scene_limit = self.capital_pool.allocate_for_trade(
            result.get("scene", "RANGING"),
            float(result.get("confidence", 0.5)),
        )
        effective_available = max(
            0.0,
            self.capital_pool.available
            - self.capital_pool.locked
            - self.capital_pool.margin,
        )
        amount = min(
            remaining_budget, task_order_limit,
            scene_limit, effective_available,
        )
        if amount <= 0:
            self.automation_page.add_log(
                f"{task.symbol} · 任务预算或可用资金不足，未下单")
            return
        price = float(signal["price"])
        quantity = amount / price if price > 0 else 0
        if quantity <= 0:
            return
        success = self._execute_order(
            signal["symbol"], signal["side"], quantity, price,
            float(signal.get("stop_loss", 0)),
            float(signal.get("take_profit", 0)),
            confirm=False, automatic=True, task_id=task.id,
        )
        if success:
            self._last_auto_signals[task.id] = signal_key
            detail = (
                f"{signal['side']} {signal['symbol']} "
                f"{quantity:.6f}@{price:.4f} · 使用 {amount:.2f} USDT"
            )
            self.automation_manager.record_execution(task.id, detail)
            self.automation_page.add_log(detail)
            self.log_panel.add_trade_log(
                f"自动任务 {task.name}: {detail}", "SUCCESS")

    # ==================================================================
    #  模式 & 设定回调
    # ==================================================================

    def _check_strategy_configured(self) -> bool:
        try:
            return (
                STRATEGY_SETTINGS_PATH.exists()
                or LEGACY_STRATEGY_SETTINGS_PATH.exists()
            )
        except Exception:
            return False

    def _apply_saved_strategy_params(self):
        settings = load_strategy_settings()
        self._enabled_strategies = {
            scene_type for scene_type, values in settings.items()
            if isinstance(values, dict) and values.get("enabled", True)
        }
        for scene_type, strategy in self.strategy_engine.strategies.items():
            values = settings.get(scene_type)
            if isinstance(values, dict):
                sp = {}
                for k, v in values.items():
                    if k == "enabled":
                        continue
                    sp[k] = v / 100.0 if k.endswith("_pct") and v > 1 else v
                strategy.set_params(**sp)

    def _on_mode_changed(self, auto: bool):
        if auto and not self._strategy_configured:
            QMessageBox.information(
                self, "提示", "请先在「策略设置」中配置并保存策略参数。")
            self.pnl_bar.auto_btn.setChecked(False)
            self.pnl_bar._auto_mode = False
            self.pnl_bar._update_mode_btn()
            self._on_sidebar_nav("strategy")
            return
        if auto:
            self._auto_trading = True
            self.trade_panel.set_manual_enabled(False)
            self._on_sidebar_nav("automation")
            self.automation_page.add_log(
                "已进入自动模式；请选择任务并手动启动")
            self.log_panel.add_system_log(
                "自动模式已打开，等待客户在任务台启动任务")
        else:
            self.automation_manager.stop_all()
            self._auto_trading = False
            self.trade_panel.set_manual_enabled(True)
            self.automation_page.refresh()
            self.log_panel.add_system_log("已切换为手动模式")

    def _on_strategy_saved(self):
        self._strategy_configured = True
        self._apply_saved_strategy_params()
        self.log_panel.add_system_log("策略参数已更新")

    def _on_global_saved(self, data: dict):
        self._apply_global_settings(data, announce=True)

    def _apply_global_settings(self, data: dict, announce: bool = True):
        cap = data.get("capital", {})
        risk = data.get("risk", {})
        position = data.get("position", {})
        if "total_capital" in cap:
            nt = cap["total_capital"]
            self.capital_pool.total = nt
            self.capital_pool.peak_capital = nt
            self.capital_pool.reserve = nt * cap.get("reserve_ratio", 0.20)
            self.capital_pool.available = nt - self.capital_pool.reserve
        self.capital_pool.max_single_trade_ratio = cap.get(
            "max_single_trade_ratio", 0.30)
        self.capital_pool.daily_loss_limit = cap.get("daily_loss_limit", 0.05)
        self.capital_pool.position_multiplier = position.get(
            "position_multiplier", self.capital_pool.position_multiplier)
        self.risk_manager.single_limits["max_loss_ratio"] = risk.get(
            "max_loss_per_trade", 0.02)
        self.risk_manager.single_limits["max_profit_ratio"] = risk.get(
            "max_profit_per_trade", 0.05)
        self.risk_manager.single_limits["max_hold_time"] = int(
            risk.get("max_hold_time", 3600))
        self.risk_manager.daily_limits["max_daily_trades"] = int(
            risk.get("max_daily_trades", 20))
        self.risk_manager.daily_limits["max_daily_loss"] = cap.get(
            "daily_loss_limit", 0.05)
        self.risk_manager.daily_limits["max_consecutive_loss"] = int(
            risk.get("max_consecutive_loss", 3))
        self.risk_manager.daily_limits["cooldown_seconds"] = int(
            risk.get("cooldown_seconds", 300))
        self.risk_manager.account_limits["max_drawdown"] = risk.get(
            "max_drawdown", 0.20)
        self.risk_manager.account_limits["min_reserve_ratio"] = risk.get(
            "min_reserve_ratio", 0.10)
        self.risk_manager.single_limits["max_position_ratio"] = cap.get(
            "max_single_trade_ratio", 0.30)
        self.pnl_bar.set_global_ready(True)
        if announce:
            self.log_panel.add_system_log("全局参数已应用")
        self._update_all_panels()

    def _on_api_page_saved(self):
        if self.api_page.saved:
            t = Theme.colors()
            self._status_api.setText("API ✓")
            self._status_api.setStyleSheet(
                f"color:{t['success']}; font-size:12px;")
            self.pnl_bar.set_api_status(True)
            self.client.reload_keys()
            self.log_panel.add_system_log("API Key 已更新，正在同步...")
            self._sync_account()
            self.api_page.saved = False

    def _show_api_settings(self):
        self._on_sidebar_nav("settings")

    def _show_strategy_settings(self):
        self._on_sidebar_nav("strategy")

    def _sync_account(self):
        self.account_sync.sync()

    def _on_balances_updated(self, balances):
        self.capital_panel.update_balances(
            balances, self.account_sync.total_value_usdt)

    def _on_total_value_updated(self, total_usdt: float):
        self.pnl_bar.update_pnl(
            self.capital_pool.daily_pnl, self.capital_pool.daily_pnl_ratio,
            self.capital_pool.total,
            self.capital_pool.win_count / max(self.capital_pool.total_trades, 1))
        self.trade_panel.set_available(
            self.capital_pool.available if self.capital_pool.available > 0
            else total_usdt)

    # ==================================================================
    #  风控
    # ==================================================================

    def _show_risk_warning(self, check: RiskCheck):
        icons = {
            "WARNING": QMessageBox.Icon.Warning,
            "CRITICAL": QMessageBox.Icon.Critical,
            "STOP": QMessageBox.Icon.Critical,
        }
        m = QMessageBox(self)
        m.setWindowTitle("风控拦截")
        m.setIcon(icons.get(check.level, QMessageBox.Icon.Warning))
        m.setText(check.message)
        if check.detail:
            m.setInformativeText(check.detail)
        m.exec()
        self.log_panel.add_risk_log(f"风控: {check.message}", check.level)
        if self.risk_manager.review_required:
            self._show_review_dialog()

    def _show_review_dialog(self):
        dlg = ReviewDialog(self.risk_manager.state.review_reason, self)
        if dlg.exec() == ReviewDialog.DialogCode.Accepted:
            data = dlg.get_data()
            ok = dlg.is_qualified()
            self.risk_manager.complete_review(ok)
            self.log_panel.add_system_log(
                f"复盘: {data['emotion_state']}",
                "SUCCESS" if ok else "WARNING")
            if ok:
                QMessageBox.information(self, "复盘通过", "交易权限已恢复")
        self._update_all_panels()

    # ==================================================================
    #  刷新
    # ==================================================================

    def _periodic_update(self):
        self._update_all_panels()
        if self.risk_manager.review_required:
            self._show_review_dialog()

    def _update_all_panels(self):
        t = Theme.colors()
        cs = self.capital_pool.get_status()
        self.risk_manager.state.reserve_ratio = (
            self.capital_pool.reserve / self.capital_pool.total
            if self.capital_pool.total > 0 else 0
        )
        self.risk_manager.update_drawdown(
            self.capital_pool.total, self.capital_pool.peak_capital)
        rs = self.risk_manager.get_risk_summary()
        self.pnl_bar.update_pnl(
            cs.get("daily_pnl", 0), cs.get("daily_pnl_ratio", 0),
            cs.get("total", 0), cs.get("win_rate", 0))
        if hasattr(self, "automation_page"):
            self.automation_page.set_capital(cs.get("total", 0))
            allowed, reason = self.capital_pool.can_trade()
            self.automation_page.set_risk_state(allowed, reason)
        self.capital_panel.update_status(cs)
        self.risk_panel.update_risk(rs)
        self._status_risk.setText(self.risk_manager.get_status_text())
        ok = self.risk_manager.is_trading_allowed
        self._status_risk.setStyleSheet(
            f"color:{t['success'] if ok else t['danger']}; font-size:12px;")

        self.trade_panel.set_available(cs.get("available", 0))

        current_price = self.trade_panel.price_input.value()
        for pos in self.positions:
            if pos["symbol"] == self.current_symbol and current_price > 0:
                pos["current_price"] = current_price
            direction = 1 if pos["side"] == "BUY" else -1
            pos["pnl"] = (
                pos["current_price"] - pos["entry_price"]
            ) * pos["quantity"] * direction
            pos["pnl_ratio"] = (
                pos["pnl"] / pos["capital_used"]
                if pos["capital_used"] > 0 else 0
            )
        self.position_panel.update_positions(self.positions)

    def _reset_daily(self):
        r = QMessageBox.question(
            self, "确认", "重置日度统计？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if r == QMessageBox.StandardButton.Yes:
            self.capital_pool.reset_daily()
            self.risk_manager.reset_daily()
            self._update_all_panels()
            self.log_panel.add_system_log("日度统计已重置")

    def _show_about(self):
        QMessageBox.about(
            self, f"关于 {Config.APP_NAME}",
            f"<h3>{Config.APP_NAME} v{Config.APP_VERSION}</h3>"
            f"<p>本地短线交易系统 · 币安交易所</p>")

    def closeEvent(self, event):
        self.automation_manager.stop_all()
        if self.automation_worker and self.automation_worker.isRunning():
            self.automation_worker.requestInterruption()
            self.automation_worker.wait(5000)
        if self.data_worker:
            self.data_worker.stop()
            self.data_worker.wait()
        self.log_panel.add_system_log("应用关闭")
        event.accept()
