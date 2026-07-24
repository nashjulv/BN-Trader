"""
顶部状态栏 — 匹配 UI 设计稿
[手动/自动] | BTC/USDT 价格 +涨跌 | 今日盈亏 | 总权益 | 胜率 |  ☾  API
"""

from PyQt6.QtWidgets import (QWidget, QHBoxLayout, QLabel, QPushButton,
                               QComboBox, QFrame)
from PyQt6.QtCore import pyqtSignal, Qt, QSize, QRectF, QPointF
from PyQt6.QtGui import QColor, QIcon, QPainter, QPixmap, QPen

from gui.styles import Theme
from config import Config


class PnlBar(QWidget):
    mode_changed = pyqtSignal(bool)
    theme_toggled = pyqtSignal(str)
    api_settings_clicked = pyqtSignal()
    symbol_changed = pyqtSignal(str)
    refresh_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setFixedHeight(48)
        self._auto_mode = False
        self._api_ok = False
        self._init_ui()
        self._restyle()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(12)

        # --- 手动 / 自动 切换 ---
        self.auto_btn = QPushButton("手动")
        self.auto_btn.setCheckable(True)
        self.auto_btn.setFixedSize(72, 30)
        self.auto_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.auto_btn.clicked.connect(self._toggle_mode)
        layout.addWidget(self.auto_btn)

        layout.addWidget(self._vsep())

        # --- 交易对 ---
        self.symbol_combo = QComboBox()
        self.symbol_combo.addItems([
            symbol.removesuffix("USDT") + "/USDT"
            for symbol in Config.DEFAULT_SYMBOLS
        ])
        self.symbol_combo.setFixedWidth(110)
        self.symbol_combo.setFixedHeight(30)
        self.symbol_combo.currentTextChanged.connect(self._on_symbol)
        layout.addWidget(self.symbol_combo)

        # --- 价格 ---
        self.price_label = QLabel("---")
        layout.addWidget(self.price_label)

        self.change_label = QLabel("+0.00%")
        layout.addWidget(self.change_label)

        layout.addWidget(self._vsep())

        # --- 今日盈亏 ---
        col1 = self._stat_block("今日盈亏", "+0.00 USDT")
        self.daily_pnl_label = col1[1]
        layout.addLayout(col1[0])

        layout.addWidget(self._vsep())

        # --- 总权益 ---
        col2 = self._stat_block("总权益", "10,000.00 USDT")
        self.total_label = col2[1]
        layout.addLayout(col2[0])

        layout.addWidget(self._vsep())

        # --- 胜率 ---
        col3 = self._stat_block("胜率", "--")
        self.win_rate_label = col3[1]
        layout.addLayout(col3[0])

        layout.addStretch()

        # --- 全局刷新 ---
        self.refresh_btn = QPushButton()
        self.refresh_btn.setFixedSize(30, 30)
        self.refresh_btn.setIconSize(QSize(18, 18))
        self.refresh_btn.setToolTip("刷新行情、账户并清空手动止盈止损价")
        self.refresh_btn.setAccessibleName("刷新全部数据")
        self.refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_btn.clicked.connect(self._request_refresh)
        layout.addWidget(self.refresh_btn)

        # --- 主题 ---
        self.theme_btn = QPushButton("暗" if Theme.is_dark() else "明")
        self.theme_btn.setFixedSize(30, 30)
        self.theme_btn.setToolTip("切换主题")
        self.theme_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.theme_btn.clicked.connect(self._on_theme_clicked)
        layout.addWidget(self.theme_btn)

        # --- API ---
        self.api_btn = QPushButton("API")
        self.api_btn.setFixedHeight(30)
        self.api_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.api_btn.clicked.connect(self.api_settings_clicked.emit)
        layout.addWidget(self.api_btn)

    def _stat_block(self, caption: str, value: str):
        from PyQt6.QtWidgets import QVBoxLayout
        box = QVBoxLayout()
        box.setSpacing(0)
        box.setContentsMargins(0, 4, 0, 4)
        cap = QLabel(caption)
        cap.setObjectName("dimLabel")
        val = QLabel(value)
        val.setStyleSheet("font-size:13px; font-weight:700;")
        box.addWidget(cap)
        box.addWidget(val)
        return box, val

    def _vsep(self) -> QFrame:
        f = QFrame()
        f.setFixedWidth(1)
        f.setFixedHeight(28)
        f.setObjectName("sep")
        return f

    # ------- 模式 -------

    def _toggle_mode(self):
        self._auto_mode = self.auto_btn.isChecked()
        self._update_mode_btn()
        self.mode_changed.emit(self._auto_mode)

    def _update_mode_btn(self):
        t = Theme.colors()
        if self._auto_mode:
            self.auto_btn.setText("自动")
            self.auto_btn.setStyleSheet(
                f"background:{t['danger']}; color:#fff; font-weight:700; "
                f"font-size:13px; border:none; border-radius:15px;")
        else:
            self.auto_btn.setText("手动")
            self.auto_btn.setStyleSheet(
                f"background:{t['accent']}; color:#fff; font-weight:600; "
                f"font-size:13px; border:none; border-radius:15px;")

    def is_auto_mode(self) -> bool:
        return self._auto_mode

    def set_auto_mode(self, enabled: bool):
        self._auto_mode = enabled
        self.auto_btn.blockSignals(True)
        self.auto_btn.setChecked(enabled)
        self.auto_btn.blockSignals(False)
        self._update_mode_btn()

    # ------- 主题 -------

    def _on_theme_clicked(self):
        new = Theme.toggle()
        self.theme_toggled.emit(new)
        self._restyle()

    def _on_symbol(self, text: str):
        # BTC/USDT → BTCUSDT
        sym = text.replace("/", "")
        self.symbol_changed.emit(sym)

    def _request_refresh(self):
        if self.refresh_btn.isEnabled():
            self.set_refreshing(True)
            self.refresh_requested.emit()

    def set_refreshing(self, refreshing: bool):
        self.refresh_btn.setEnabled(not refreshing)
        self.refresh_btn.setToolTip(
            "正在刷新行情与账户…"
            if refreshing else
            "刷新行情、账户并清空手动止盈止损价"
        )

    def set_global_ready(self, ready: bool):
        pass

    def _restyle(self):
        t = Theme.colors()
        self.setStyleSheet(
            f"PnlBar {{ background:{t['pnlbar_bg']}; "
            f"border-bottom:1px solid {t['pnlbar_border']}; }}"
        )
        self.price_label.setStyleSheet(
            f"font-size:16px; font-weight:700; color:{t['text_primary']};")
        self.change_label.setStyleSheet(f"font-size:12px; color:{t['text_secondary']};")
        self.theme_btn.setText("暗" if Theme.is_dark() else "明")
        self.theme_btn.setStyleSheet(
            f"background:transparent; border:1px solid {t['border']}; "
            f"border-radius:4px; font-size:12px; padding:0;")
        self.refresh_btn.setIcon(self._refresh_icon(t["text_secondary"]))
        self.refresh_btn.setStyleSheet(
            f"QPushButton {{ background:transparent; "
            f"border:1px solid {t['border']}; border-radius:4px; padding:0; }}"
            f"QPushButton:hover {{ background:{t['bg_hover']}; "
            f"border-color:{t['hover_border']}; }}"
            f"QPushButton:pressed {{ background:{t['bg_hover']}; }}"
            f"QPushButton:disabled {{ background:transparent; "
            f"border-color:{t['divider']}; }}"
        )
        for sep in self.findChildren(QFrame, "sep"):
            sep.setStyleSheet(f"background:{t['divider']}; border:none;")
        self._update_mode_btn()
        self.set_api_status(self._api_ok)

    @staticmethod
    def _refresh_icon(color: str) -> QIcon:
        """绘制与侧栏一致的线性刷新图标。"""
        pixmap = QPixmap(20, 20)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor(color))
        pen.setWidthF(1.6)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawArc(QRectF(3, 3, 14, 14), 35 * 16, 285 * 16)
        painter.drawLine(QPointF(3.7, 5.8), QPointF(3.4, 2.8))
        painter.drawLine(QPointF(3.4, 2.8), QPointF(6.4, 3.6))
        painter.end()
        return QIcon(pixmap)

    # ------- 数据更新 -------

    def update_price(self, symbol: str, price: float, change_pct: float):
        t = Theme.colors()
        # 同步下拉框显示
        display = f"{symbol[:-4]}/{symbol[-4:]}" if symbol.endswith("USDT") else symbol
        idx = self.symbol_combo.findText(display)
        if idx >= 0 and self.symbol_combo.currentIndex() != idx:
            self.symbol_combo.blockSignals(True)
            self.symbol_combo.setCurrentIndex(idx)
            self.symbol_combo.blockSignals(False)

        self.price_label.setText(f"{price:,.2f}")
        c = t["success"] if change_pct >= 0 else t["danger"]
        self.change_label.setText(f"{change_pct:+.2f}%")
        self.change_label.setStyleSheet(f"font-size:12px; font-weight:600; color:{c};")

    def update_pnl(self, daily_pnl: float, daily_pnl_ratio: float,
                   total: float, win_rate: float):
        t = Theme.colors()
        pnl_color = t["success"] if daily_pnl >= 0 else t["danger"]
        self.daily_pnl_label.setText(f"{daily_pnl:+,.2f} USDT")
        self.daily_pnl_label.setStyleSheet(
            f"font-size:13px; font-weight:700; color:{pnl_color};")
        self.total_label.setText(f"{total:,.2f} USDT")
        self.total_label.setStyleSheet(
            f"font-size:13px; font-weight:700; color:{t['text_primary']};")
        self.win_rate_label.setText(f"{win_rate:.2%}")
        self.win_rate_label.setStyleSheet(
            f"font-size:13px; font-weight:700; color:{t['text_primary']};")

    def set_api_status(self, connected: bool):
        self._api_ok = connected
        t = Theme.colors()
        if connected:
            self.api_btn.setText("● API")
            self.api_btn.setStyleSheet(
                f"color:{t['success']}; border:1px solid {t['success']}; "
                f"border-radius:4px; background:transparent; "
                f"font-size:12px; padding:4px 10px;")
        else:
            self.api_btn.setText("API")
            self.api_btn.setStyleSheet(
                f"color:{t['text_secondary']}; border:1px solid {t['border']}; "
                f"border-radius:4px; background:transparent; "
                f"font-size:12px; padding:4px 10px;")

    def set_api_connecting(self):
        self._api_ok = False
        t = Theme.colors()
        self.api_btn.setText("… API")
        self.api_btn.setStyleSheet(
            f"color:{t['text_secondary']}; border:1px solid {t['border']}; "
            f"border-radius:4px; background:{t['bg_hover']}; "
            f"font-size:12px; padding:4px 10px;"
        )
