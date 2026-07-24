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
import time
from collections import deque
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
from gui.open_orders_panel import OpenOrdersPanel
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
from services.account_sync import AccountSyncService, fetch_account_snapshot
from services.scene_detector import SceneDetector, Scene
from services.capital_pool import CapitalPool
from services.risk_manager import RiskManager, RiskCheck
from services.strategy_engine import StrategyEngine
from services.automation_manager import (
    AutomationManager, RUNNING, EVALUATING
)
from services.automation_worker import AutomationEvaluationWorker
from utils.parameter_units import strategy_runtime_params
from strategies.base import SignalType

from indicators.technical import calculate_all_indicators
from config import Config

logger = logging.getLogger(__name__)

MAX_PARALLEL_AUTOMATION_EVALUATIONS = 3


def normalize_open_order(order: Dict) -> Dict:
    """将币安字段转换为右侧挂单面板使用的稳定结构。"""
    executed_quantity = float(order.get("executedQty", 0) or 0)
    price = float(order.get("price", 0) or 0)
    if price <= 0 and executed_quantity > 0:
        quote_quantity = float(
            order.get("cummulativeQuoteQty", 0) or 0
        )
        if quote_quantity > 0:
            price = quote_quantity / executed_quantity
    return {
        "order_id": str(order.get("orderId", order.get("order_id", ""))),
        "symbol": str(order.get("symbol", "")),
        "side": str(order.get("side", "BUY")).upper(),
        "quantity": float(
            order.get("origQty", order.get("quantity", 0)) or 0
        ),
        "executed_quantity": executed_quantity,
        "price": price,
        "status": str(order.get("status", "NEW")),
        "type": str(order.get("type", "")),
    }


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


class OpenOrdersWorker(QThread):
    orders_updated = pyqtSignal(list)
    failed = pyqtSignal(str)

    def __init__(self, client: BinanceClient, symbol: str):
        super().__init__()
        self.client = client
        self.symbol = symbol

    def run(self):
        try:
            open_orders = self.client.get_open_orders()
            recent_orders = self.client.get_all_orders(
                self.symbol, limit=10
            )
            merged = {}
            for order in recent_orders:
                merged[str(order.get("orderId", ""))] = order
            for order in open_orders:
                merged[str(order.get("orderId", ""))] = order
            self.orders_updated.emit(list(merged.values()))
        except Exception as error:
            self.failed.emit(str(error))


class AccountSyncWorker(QThread):
    snapshot_updated = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self, client: BinanceClient):
        super().__init__()
        self.client = client

    def run(self):
        try:
            self.snapshot_updated.emit(
                fetch_account_snapshot(self.client)
            )
        except Exception as error:
            self.failed.emit(str(error))


class ApiConnectionWorker(QThread):
    completed = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self, client: BinanceClient, symbol: str):
        super().__init__()
        self.client = client
        self.symbol = symbol

    def run(self):
        started = time.monotonic()
        try:
            account = self.client.get_account()
            trade_ok = True
            trade_message = ""
            try:
                self.client.test_order(self.symbol)
            except Exception as error:
                trade_ok = False
                trade_message = str(error)
            self.completed.emit({
                "latency_ms": int((time.monotonic() - started) * 1000),
                "account_can_trade": bool(account.get("canTrade", False)),
                "trade_test_ok": trade_ok,
                "trade_message": trade_message,
            })
        except Exception as error:
            self.failed.emit(str(error))


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
        self.automation_workers: Dict[str, AutomationEvaluationWorker] = {}
        self._automation_order_queue = deque()
        self._queued_auto_signal_keys = set()
        self._automation_order_busy = False
        self._automation_order_item = None
        self._automation_order_worker: Optional[AccountSyncWorker] = None

        self.data_worker: Optional[DataWorker] = None
        self.current_symbol = "BTCUSDT"
        self.current_timeframe = "15m"
        self.current_klines: Optional[pd.DataFrame] = None
        self.current_scene: Optional[Scene] = None
        self.positions = []
        self.exchange_balances = {}
        self._real_account_snapshot = {}
        self.open_orders = []
        self._known_open_order_ids = set()
        self.open_orders_worker: Optional[OpenOrdersWorker] = None
        self.account_sync_worker: Optional[AccountSyncWorker] = None
        self.api_connection_worker: Optional[ApiConnectionWorker] = None
        self._last_auto_signals = {}
        self._auto_trading = False
        self._strategy_configured = self._check_strategy_configured()
        self._apply_saved_strategy_params()

        self._init_ui()
        self._apply_global_settings(load_global_settings(), announce=False)
        self.pnl_bar.set_api_status(False)

        self.account_sync.balances_updated.connect(self._on_balances_updated)
        self.account_sync.total_value_updated.connect(self._on_total_value_updated)
        self.account_sync.snapshot_updated.connect(
            self._on_account_snapshot_updated
        )
        self.account_sync.error_occurred.connect(
            lambda msg: self.log_panel.add_system_log(msg, "ERROR"))
        self.capital_panel._sync_btn.clicked.connect(self._sync_account)

        self._init_menu()
        self._apply_theme()
        self._start_data_worker()
        QTimer.singleShot(300, self._test_api_connection)

        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._periodic_update)
        self.update_timer.start(1000)

        self.automation_timer = QTimer()
        self.automation_timer.timeout.connect(self._automation_tick)
        self.automation_timer.start(1000)

        self.automation_order_timer = QTimer()
        self.automation_order_timer.timeout.connect(
            self._process_automation_order_queue
        )
        self.automation_order_timer.start(250)

        self.open_orders_timer = QTimer()
        self.open_orders_timer.timeout.connect(self._sync_open_orders)
        self.open_orders_timer.start(30000)

        self.account_sync_timer = QTimer()
        self.account_sync_timer.timeout.connect(self._sync_account)
        self.account_sync_timer.start(15000)

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
        self.api_page.credentials_changed.connect(
            self._on_api_credentials_changed
        )
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
        self.pnl_bar.refresh_requested.connect(self._refresh_all_data)
        layout.addWidget(self.pnl_bar)

        # 三栏主体
        self.body_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.body_splitter.setObjectName("dashboardBodySplitter")
        self.body_splitter.setHandleWidth(7)
        self.body_splitter.setOpaqueResize(True)
        self.body_splitter.setChildrenCollapsible(False)

        # --- 左栏：堆叠卡片 ---
        left_scroll = QScrollArea()
        self.left_scroll = left_scroll
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        left_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        left_scroll.setMinimumWidth(200)
        left_scroll.setMaximumWidth(420)

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
        self.center_splitter = QSplitter(Qt.Orientation.Vertical)
        self.center_splitter.setObjectName("dashboardCenterSplitter")
        self.center_splitter.setHandleWidth(7)
        self.center_splitter.setOpaqueResize(True)
        self.center_splitter.setChildrenCollapsible(False)

        chart_wrap = QFrame()
        chart_wrap.setObjectName("cardFrame")
        cw = QVBoxLayout(chart_wrap)
        cw.setContentsMargins(8, 8, 8, 8)
        self.chart_widget = ChartWidget()
        self.chart_widget.request_data.connect(self._on_chart_data_request)
        cw.addWidget(self.chart_widget)
        self.center_splitter.addWidget(chart_wrap)

        self.log_panel = LogPanel(detail_mode=False)
        self.center_splitter.addWidget(self.log_panel)

        self.center_splitter.setStretchFactor(0, 65)
        self.center_splitter.setStretchFactor(1, 35)
        self.body_splitter.addWidget(self.center_splitter)

        # --- 右栏：下单 ---
        right_wrap = QWidget()
        rv = QVBoxLayout(right_wrap)
        rv.setContentsMargins(6, 10, 10, 10)
        self.trade_panel = TradePanel()
        self.trade_panel.place_order.connect(self._on_place_order)
        rv.addWidget(self.trade_panel)
        self.open_orders_panel = OpenOrdersPanel()
        self.open_orders_panel.refresh_requested.connect(
            self._sync_open_orders
        )
        rv.addWidget(self.open_orders_panel)
        right_wrap.setMinimumWidth(230)
        right_wrap.setMaximumWidth(420)
        self.body_splitter.addWidget(right_wrap)

        self.body_splitter.setStretchFactor(0, 22)
        self.body_splitter.setStretchFactor(1, 50)
        self.body_splitter.setStretchFactor(2, 28)
        self.body_splitter.setSizes([240, 760, 260])
        self.center_splitter.setSizes([520, 260])
        self._configure_splitter_handles()
        self._restore_splitter_sizes()

        layout.addWidget(self.body_splitter, 1)
        return page

    def _configure_splitter_handles(self):
        for index in range(1, self.body_splitter.count()):
            handle = self.body_splitter.handle(index)
            handle.setCursor(Qt.CursorShape.SplitHCursor)
            handle.setToolTip("左右拖动调整 K 线与侧栏宽度")
            handle.setAccessibleName("调整 K 线与侧栏宽度")
        for index in range(1, self.center_splitter.count()):
            handle = self.center_splitter.handle(index)
            handle.setCursor(Qt.CursorShape.SplitVCursor)
            handle.setToolTip("上下拖动调整 K 线与日志高度")
            handle.setAccessibleName("调整 K 线与日志高度")
        self.body_splitter.splitterMoved.connect(
            lambda *_: self._save_splitter_sizes()
        )
        self.center_splitter.splitterMoved.connect(
            lambda *_: self._save_splitter_sizes()
        )

    def _restore_splitter_sizes(self):
        settings = QSettings("BN-Trader", "BN-Trader")
        body_sizes = settings.value("dashboard/body_splitter_sizes")
        center_sizes = settings.value("dashboard/center_splitter_sizes")
        if isinstance(body_sizes, list) and len(body_sizes) == 3:
            self.body_splitter.setSizes([int(value) for value in body_sizes])
        if isinstance(center_sizes, list) and len(center_sizes) == 2:
            self.center_splitter.setSizes(
                [int(value) for value in center_sizes]
            )

    def _save_splitter_sizes(self):
        settings = QSettings("BN-Trader", "BN-Trader")
        settings.setValue(
            "dashboard/body_splitter_sizes",
            self.body_splitter.sizes(),
        )
        settings.setValue(
            "dashboard/center_splitter_sizes",
            self.center_splitter.sizes(),
        )

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
        splitter_style = (
            "QSplitter { background:transparent; } "
            f"QSplitter::handle {{ background:{t['divider']}; "
            "border-radius:2px; margin:2px; } "
            f"QSplitter::handle:hover {{ background:{t['hover_border']}; "
            "margin:1px; }"
        )
        self.body_splitter.setStyleSheet(splitter_style)
        self.center_splitter.setStyleSheet(splitter_style)
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
                       self.open_orders_panel, self.log_detail]:
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
        """非阻塞启动数据线程，避免切换周期时 GUI 卡顿。"""
        if self.data_worker and self.data_worker.isRunning():
            # 断开旧信号，以免旧数据更新干扰
            try:
                self.data_worker.data_updated.disconnect()
            except TypeError:
                pass
            self.data_worker.stop()
            # 等旧线程退出后再启动新线程，不阻塞 UI
            self.data_worker.finished.connect(self._restart_worker)
        else:
            self._restart_worker()

    def _restart_worker(self):
        """实际创建并启动 DataWorker（可能在旧线程 finished 回调中调用）。"""
        # 防止多次重启
        if self.data_worker:
            try:
                self.data_worker.finished.disconnect(self._restart_worker)
            except TypeError:
                pass
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
                    "scene_scores": scene.scene_scores,
                })
                self._status_scene.setText(
                    f"{scene.type} ({scene.confidence:.0%})")

            self._update_all_panels()
            t = Theme.colors()
            ok = self.client.has_keys()
            self._status_api.setText("API ✓" if ok else "API ✗")
            self._status_api.setStyleSheet(
                f"color:{t['success'] if ok else t['danger']}; font-size:12px;")
            self.pnl_bar.set_refreshing(False)
            if self._status_msg.text() == "正在刷新全部数据…":
                self._status_msg.setText("刷新完成")

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
        self._update_trade_balances()
        self._start_data_worker()

    # ==================================================================
    #  交易
    # ==================================================================

    def _on_place_order(self, symbol, side, qty, price, sl, tp):
        self._execute_order(symbol, side, qty, price, sl, tp, confirm=True)

    def _execute_order(self, symbol, side, qty, price, sl=0, tp=0,
                       confirm: bool = False, automatic: bool = False,
                       task_id: str = ""):
        risk_capital = float(
            self._real_account_snapshot.get("total_value_usdt", 0) or 0
        )
        if not self.client.has_keys() or risk_capital <= 0:
            risk_capital = self.capital_pool.total
        check = self.risk_manager.check_trade_permission(
            risk_capital, qty * price, price, sl)
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
        real_order = self.client.has_keys()
        if confirm:
            reply = QMessageBox.question(
                self, "确认交易",
                f"{side} {symbol}\n数量:{qty:.4f} 价格:{price:.2f}\n"
                f"类型:{order_type}\n止损:{sl:.2f} 止盈:{tp:.2f}",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply != QMessageBox.StandardButton.Yes:
                return False
        if real_order:
            result = self.account_sync.execute_real_order(
                symbol, side, qty, price, order_type)
            if result and result.get("status") in ("FILLED", "NEW"):
                order_status = result["status"]
                qty = float(result.get("quantity", qty))
                if float(result.get("price", 0) or 0) > 0:
                    price = float(result["price"])
                self.log_panel.add_trade_log(
                    f"实盘订单 {side} {symbol} {qty:.4f}@{price:.2f} "
                    f"[{result['status']}] · 订单号 {result.get('order_id', '—')}",
                    "SUCCESS")
                if order_status == "NEW":
                    self._upsert_open_order({
                        "order_id": result.get("order_id", ""),
                        "symbol": symbol,
                        "side": side,
                        "quantity": qty,
                        "price": price,
                        "status": "NEW",
                        "type": order_type,
                    })
                self.risk_manager.record_order_execution()
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
        if not real_order:
            self.risk_manager.record_order_execution()
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
        capacity = (
            MAX_PARALLEL_AUTOMATION_EVALUATIONS
            - len(self.automation_workers)
        )
        if capacity <= 0:
            return
        tasks = self.automation_manager.due_tasks(capacity)
        if not tasks:
            return
        strategy_settings = load_strategy_settings()
        for task in tasks:
            self.automation_manager.mark_evaluating(task.id)
            self.automation_page.add_log(
                f"{task.symbol} · 开始并行评估 {task.strategy} 策略")
            worker = AutomationEvaluationWorker(
                task, strategy_settings
            )
            self.automation_workers[task.id] = worker
            worker.evaluated.connect(self._on_automation_evaluated)
            worker.finished.connect(
                lambda task_id=task.id:
                self._on_automation_worker_finished(task_id)
            )
            worker.start()
        self.automation_page.refresh()

    def _on_automation_worker_finished(self, task_id: str):
        worker = self.automation_workers.pop(task_id, None)
        if worker:
            worker.deleteLater()

    def _on_automation_evaluated(self, task_id: str, result: dict):
        task = self.automation_manager.get(task_id)
        if not task:
            return
        was_stopped = task.status == "STOPPED"
        ok = bool(result.get("ok"))
        retryable = bool(result.get("retryable"))
        message = result.get("message", "评估完成")
        self.automation_manager.finish_evaluation(
            task_id, message, success=ok or retryable)
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
                self._enqueue_automation_signal(
                    task, result, signal, signal_key
                )
        elif retryable:
            self.log_panel.add_system_log(
                f"自动任务网络波动 {task.name}: {message}", "WARNING")
        elif not ok:
            self.log_panel.add_system_log(
                f"自动任务异常 {task.name}: {message}", "ERROR")
        self._sync_automation_master_state()
        self.automation_page.refresh()

    def _enqueue_automation_signal(
        self, task, result: dict, signal: dict, signal_key
    ):
        queue_key = (task.id, signal_key)
        if queue_key in self._queued_auto_signal_keys:
            return
        self._queued_auto_signal_keys.add(queue_key)
        self._automation_order_queue.append({
            "task_id": task.id,
            "result": dict(result),
            "signal": dict(signal),
            "signal_key": signal_key,
            "queue_key": queue_key,
        })
        self.automation_page.add_log(
            f"{task.symbol} · 信号已进入下单队列 "
            f"（前方 {len(self._automation_order_queue) - 1} 笔）"
        )

    def _process_automation_order_queue(self):
        if self._automation_order_busy or not self._automation_order_queue:
            return
        item = self._automation_order_queue.popleft()
        self._automation_order_item = item
        self._automation_order_busy = True
        task = self.automation_manager.get(item["task_id"])
        if not task or task.status == "STOPPED":
            self._finish_automation_order_item()
            return
        if not self.client.has_keys():
            self._execute_automation_signal(
                task,
                item["result"],
                item["signal"],
                item["signal_key"],
            )
            self._finish_automation_order_item()
            return

        worker = AccountSyncWorker(self.client)
        self._automation_order_worker = worker
        worker.snapshot_updated.connect(
            self._on_automation_order_snapshot
        )
        worker.failed.connect(self._on_automation_order_preflight_failed)
        worker.finished.connect(self._on_automation_order_preflight_finished)
        worker.start()

    def _on_automation_order_snapshot(self, snapshot: Dict):
        item = self._automation_order_item
        if not item:
            return
        self.account_sync.apply_snapshot(snapshot)
        task = self.automation_manager.get(item["task_id"])
        if not task or task.status == "STOPPED":
            return
        self.automation_page.add_log(
            f"{task.symbol} · 已按最新账户快照完成队列前置校验"
        )
        self._execute_automation_signal(
            task,
            item["result"],
            item["signal"],
            item["signal_key"],
        )

    def _on_automation_order_preflight_failed(self, message: str):
        item = self._automation_order_item
        task = (
            self.automation_manager.get(item["task_id"])
            if item else None
        )
        name = task.name if task else "未知任务"
        self.log_panel.add_system_log(
            f"自动下单队列前置校验失败 {name}: {message}",
            "WARNING",
        )

    def _on_automation_order_preflight_finished(self):
        worker = self._automation_order_worker
        self._automation_order_worker = None
        if worker:
            worker.deleteLater()
        self._finish_automation_order_item()

    def _finish_automation_order_item(self):
        item = self._automation_order_item
        if item:
            self._queued_auto_signal_keys.discard(item["queue_key"])
        self._automation_order_item = None
        self._automation_order_busy = False

    def _execute_automation_signal(
        self, task, result: dict, signal: dict, signal_key
    ):
        allocation = self.automation_manager.allocation_for(task.symbol)
        if not allocation:
            self.automation_page.add_log(
                f"{task.symbol} · 资金分配已停用，未下单")
            return
        real_snapshot = (
            self._real_account_snapshot
            if self.client.has_keys() else {}
        )
        capital_base = float(
            real_snapshot.get("total_value_usdt", 0) or 0
        )
        if capital_base <= 0:
            capital_base = self.capital_pool.total
        task_budget = capital_base * allocation.allocation_ratio
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
        if real_snapshot:
            symbol = signal["symbol"].upper()
            quote_asset = "USDT" if symbol.endswith("USDT") else ""
            base_asset = (
                symbol[:-len(quote_asset)] if quote_asset else symbol
            )
            if signal["side"] == "BUY":
                effective_available = float(
                    real_snapshot.get("available_usdt", 0) or 0
                )
            else:
                base_free = self.exchange_balances.get(
                    base_asset, {}
                ).get("free", 0)
                effective_available = base_free * float(signal["price"])
        else:
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
                strategy.set_params(**strategy_runtime_params(values))

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
        max_loss_ratio = risk.get("max_loss_per_trade", 0.02)
        self.risk_manager.single_limits["max_loss_ratio"] = max_loss_ratio
        self.trade_panel.set_max_loss_ratio(max_loss_ratio)
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

    def _on_api_credentials_changed(self, has_credentials: bool):
        self.client.reload_keys()
        t = Theme.colors()
        if has_credentials:
            self.log_panel.add_system_log("API Key 已更新，正在自动测试...")
            self._test_api_connection()
            self.api_page.saved = False
            return

        self._status_api.setText("API ✗")
        self._status_api.setStyleSheet(
            f"color:{t['danger']}; font-size:12px;"
        )
        self.pnl_bar.set_api_status(False)
        self.account_sync.balances = []
        self.account_sync.total_value_usdt = 0
        self.account_sync.last_snapshot = {}
        self._real_account_snapshot = {}
        self.exchange_balances = {}
        self.capital_panel.update_balances([], 0)
        self.capital_panel.clear_exchange_snapshot()
        self.trade_panel.set_available(0)
        self.open_orders = []
        self._known_open_order_ids.clear()
        self.open_orders_panel.update_orders([])
        self.log_panel.add_system_log(
            "API Key、Secret Key 与运行时缓存已清除"
        )

    def _test_api_connection(self):
        """启动或凭据更新后自动完成鉴权与无成交下单测试。"""
        if not self.client.has_keys():
            self._status_api.setText("API ✗")
            self.pnl_bar.set_api_status(False)
            return
        if (
            self.api_connection_worker
            and self.api_connection_worker.isRunning()
        ):
            return
        t = Theme.colors()
        self._status_api.setText("API …")
        self._status_api.setStyleSheet(
            f"color:{t['text_secondary']}; font-size:12px;"
        )
        self.pnl_bar.set_api_connecting()
        worker = ApiConnectionWorker(self.client, self.current_symbol)
        self.api_connection_worker = worker
        worker.completed.connect(self._on_api_connection_completed)
        worker.failed.connect(self._on_api_connection_failed)
        worker.finished.connect(self._on_api_connection_finished)
        worker.start()

    def _on_api_connection_completed(self, result: Dict):
        if not self.client.has_keys():
            return
        t = Theme.colors()
        self._status_api.setText("API ✓")
        self._status_api.setStyleSheet(
            f"color:{t['success']}; font-size:12px;"
        )
        self.pnl_bar.set_api_status(True)
        self.api_page._connected = True
        self.api_page._update_status_badge()
        latency = int(result.get("latency_ms", 0))
        if result.get("trade_test_ok") and result.get("account_can_trade"):
            self.log_panel.add_system_log(
                f"API 自动连接成功 · 现货测试通过 · {latency} ms",
                "SUCCESS",
            )
        else:
            reason = result.get("trade_message") or "账户未开放交易"
            self.log_panel.add_system_log(
                f"API 已连接，但现货测试未通过: {reason}", "WARNING"
            )
        self._sync_account()
        self._sync_open_orders()

    def _on_api_connection_failed(self, message: str):
        t = Theme.colors()
        self._status_api.setText("API ✗")
        self._status_api.setStyleSheet(
            f"color:{t['danger']}; font-size:12px;"
        )
        self.pnl_bar.set_api_status(False)
        self.api_page._connected = False
        self.api_page._update_status_badge()
        self.log_panel.add_system_log(
            f"API 自动连接失败: {message}", "ERROR"
        )

    def _on_api_connection_finished(self):
        worker = self.api_connection_worker
        self.api_connection_worker = None
        if worker:
            worker.deleteLater()

    def _show_api_settings(self):
        self._on_sidebar_nav("settings")

    def _show_strategy_settings(self):
        self._on_sidebar_nav("strategy")

    def _sync_account(self):
        """在后台读取完整账户快照，避免网络请求阻塞界面。"""
        if not self.client.has_keys():
            return
        if (
            self.account_sync_worker
            and self.account_sync_worker.isRunning()
        ):
            return
        worker = AccountSyncWorker(self.client)
        self.account_sync_worker = worker
        worker.snapshot_updated.connect(self.account_sync.apply_snapshot)
        worker.failed.connect(self._on_account_sync_failed)
        worker.finished.connect(self._on_account_sync_finished)
        worker.start()

    def _on_account_sync_failed(self, message: str):
        self.log_panel.add_system_log(
            f"账户同步失败: {message}", "ERROR"
        )

    def _on_account_sync_finished(self):
        worker = self.account_sync_worker
        self.account_sync_worker = None
        if worker:
            worker.deleteLater()

    def _sync_open_orders(self):
        """后台同步币安当前挂单，避免阻塞主界面。"""
        if not self.client.has_keys():
            self.open_orders = []
            self.open_orders_panel.update_orders([])
            return
        if self.open_orders_worker and self.open_orders_worker.isRunning():
            return
        self.open_orders_panel.set_loading(True)
        worker = OpenOrdersWorker(self.client, self.current_symbol)
        self.open_orders_worker = worker
        worker.orders_updated.connect(self._on_open_orders_updated)
        worker.failed.connect(self._on_open_orders_failed)
        worker.finished.connect(self._on_open_orders_sync_finished)
        worker.start()

    def _on_open_orders_updated(self, raw_orders):
        orders = [normalize_open_order(order) for order in raw_orders]
        orders.sort(key=lambda order: order.get("order_id", ""), reverse=True)
        previous = {
            str(order.get("order_id", "")): order
            for order in self.open_orders
            if order.get("order_id")
        }
        current_ids = {
            order["order_id"] for order in orders if order["order_id"]
        }

        for order in orders:
            order_id = order["order_id"]
            if order_id and order_id not in self._known_open_order_ids:
                action = {
                    "FILLED": "成交同步",
                    "CANCELED": "撤单同步",
                    "EXPIRED": "失效订单同步",
                    "REJECTED": "拒绝订单同步",
                }.get(order["status"], "挂单同步")
                self.log_panel.add_trade_log(
                    f"{action} {order['side']} {order['symbol']} "
                    f"{order['quantity']:g}@{order['price']:.2f} "
                    f"[{order['status']}] · 订单号 {order_id}",
                    "INFO",
                )
                self._known_open_order_ids.add(order_id)

        for order_id, order in previous.items():
            if order_id not in current_ids:
                self.log_panel.add_trade_log(
                    f"挂单已结束或成交 {order['side']} {order['symbol']} "
                    f"· 订单号 {order_id}",
                    "INFO",
                )

        self.open_orders = orders
        self.open_orders_panel.update_orders(orders)

    def _upsert_open_order(self, order: Dict):
        normalized = normalize_open_order(order)
        order_id = normalized["order_id"]
        self.open_orders = [
            existing for existing in self.open_orders
            if existing.get("order_id") != order_id or not order_id
        ]
        self.open_orders.insert(0, normalized)
        if order_id:
            self._known_open_order_ids.add(order_id)
        self.open_orders_panel.update_orders(self.open_orders)

    def _on_open_orders_failed(self, message: str):
        self.log_panel.add_system_log(
            f"挂单同步失败: {message}", "WARNING"
        )

    def _on_open_orders_sync_finished(self):
        self.open_orders_panel.set_loading(False)
        worker = self.open_orders_worker
        self.open_orders_worker = None
        if worker:
            worker.deleteLater()

    def _on_balances_updated(self, balances):
        self.exchange_balances = {
            str(balance.get("asset", "")): {
                "free": float(balance.get("free", 0) or 0),
                "locked": float(balance.get("locked", 0) or 0),
            }
            for balance in balances
        }
        self.capital_panel.update_balances(
            balances, self.account_sync.total_value_usdt
        )
        self._update_trade_balances()

    def _on_account_snapshot_updated(self, snapshot: Dict):
        self._real_account_snapshot = dict(snapshot)
        self.capital_panel.update_exchange_snapshot(
            snapshot,
            self.capital_pool.reserve_ratio,
        )
        missing = snapshot.get("unpriced_assets", [])
        if missing:
            self.log_panel.add_system_log(
                "账户估值未包含无法换算为 USDT 的资产: "
                + ", ".join(missing),
                "WARNING",
            )
        self._update_all_panels()

    def _update_trade_balances(self):
        if not self.client.has_keys() or not self.exchange_balances:
            return
        symbol = self.current_symbol.upper()
        quote_asset = "USDT" if symbol.endswith("USDT") else ""
        base_asset = (
            symbol[:-len(quote_asset)] if quote_asset else symbol
        )
        quote_free = self.exchange_balances.get(
            quote_asset, {}
        ).get("free", 0)
        base_free = self.exchange_balances.get(
            base_asset, {}
        ).get("free", 0)
        self.trade_panel.set_exchange_balances(
            quote_free, base_free, base_asset, quote_asset or "USDT"
        )

    def _on_total_value_updated(self, total_usdt: float):
        display_total = (
            total_usdt if self.client.has_keys()
            else self.capital_pool.total
        )
        self.pnl_bar.update_pnl(
            self.capital_pool.daily_pnl, self.capital_pool.daily_pnl_ratio,
            display_total,
            (
                self.capital_pool.win_count / self.capital_pool.total_trades
                if self.capital_pool.total_trades else None
            ))
        if self.client.has_keys() and self.exchange_balances:
            self._update_trade_balances()
        else:
            self.trade_panel.set_available(
                self.capital_pool.available
                if self.capital_pool.available > 0 else total_usdt
            )

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

    def _refresh_all_data(self):
        """刷新行情、账户与页面状态，并清除交易对相关的手动退出价。"""
        self._status_msg.setText("正在刷新全部数据…")
        self.trade_panel.clear_exit_prices()
        self.client.reload_keys()
        self._start_data_worker()
        if self.client.has_keys():
            self._test_api_connection()
        self.automation_page.refresh()
        self._update_all_panels()
        self.log_panel.add_system_log(
            f"手动刷新: {self.current_symbol}；已清空止盈止损价"
        )
        # 行情异常时也恢复按钮，允许用户再次尝试。
        QTimer.singleShot(10000, lambda: self.pnl_bar.set_refreshing(False))

    def _periodic_update(self):
        self._update_all_panels()
        if self.risk_manager.review_required:
            self._show_review_dialog()

    def _update_all_panels(self):
        t = Theme.colors()
        cs = self.capital_pool.get_status()
        real_snapshot = (
            self._real_account_snapshot
            if self.client.has_keys() else {}
        )
        real_total = float(
            real_snapshot.get("total_value_usdt", 0) or 0
        )
        display_total = real_total if real_total > 0 else cs.get("total", 0)
        self.risk_manager.state.reserve_ratio = (
            self.capital_pool.reserve / self.capital_pool.total
            if self.capital_pool.total > 0 else 0
        )
        self.risk_manager.update_drawdown(
            self.capital_pool.total, self.capital_pool.peak_capital)
        rs = self.risk_manager.get_risk_summary()
        self.pnl_bar.update_pnl(
            cs.get("daily_pnl", 0), cs.get("daily_pnl_ratio", 0),
            display_total,
            cs.get("win_rate") if cs.get("total_trades", 0) else None)
        if hasattr(self, "automation_page"):
            self.automation_page.set_capital(display_total)
            allowed, reason = self.capital_pool.can_trade()
            self.automation_page.set_risk_state(allowed, reason)
        if real_snapshot:
            self.capital_panel.update_exchange_snapshot(
                real_snapshot,
                self.capital_pool.reserve_ratio,
            )
        else:
            self.capital_panel.update_status(cs)
        self.risk_panel.update_risk(rs)
        self._status_risk.setText(self.risk_manager.get_status_text())
        ok = self.risk_manager.is_trading_allowed
        self._status_risk.setStyleSheet(
            f"color:{t['success'] if ok else t['danger']}; font-size:12px;")

        if self.client.has_keys() and self.exchange_balances:
            self._update_trade_balances()
        else:
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
        for worker in list(self.automation_workers.values()):
            if worker.isRunning():
                worker.requestInterruption()
                worker.wait(5000)
        if (
            self._automation_order_worker
            and self._automation_order_worker.isRunning()
        ):
            self._automation_order_worker.wait(20000)
        if self.open_orders_worker and self.open_orders_worker.isRunning():
            self.open_orders_worker.wait(15000)
        if (
            self.account_sync_worker
            and self.account_sync_worker.isRunning()
        ):
            self.account_sync_worker.wait(20000)
        if (
            self.api_connection_worker
            and self.api_connection_worker.isRunning()
        ):
            self.api_connection_worker.wait(20000)
        if self.data_worker:
            self.data_worker.stop()
            self.data_worker.wait()
        self.log_panel.add_system_log("应用关闭")
        event.accept()
