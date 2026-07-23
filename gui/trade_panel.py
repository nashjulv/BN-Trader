"""
手动下单面板 — 匹配 UI 设计稿右侧下单区
限价单 / 市价单 · 价格 · 数量 · 百分比 · 止盈止损 · 买入/卖出
"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QComboBox, QDoubleSpinBox,
                               QFrame, QButtonGroup, QMessageBox)
from PyQt6.QtCore import Qt, pyqtSignal

from gui.styles import Theme
from config import Config


class TradePanel(QWidget):
    place_order = pyqtSignal(str, str, float, float, float, float)

    def __init__(self):
        super().__init__()
        self.setMinimumWidth(240)
        self._available = 0.0
        self._last_price = 0.0
        self._init_ui()
        self._refresh_theme()

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        self._card = QFrame()
        self._card.setObjectName("cardFrame")
        layout = QVBoxLayout(self._card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        # 标题
        self._title = QLabel("手动下单")
        self._title.setObjectName("sectionTitle")
        layout.addWidget(self._title)
        self.mode_hint = QLabel(
            "自动模式运行中，手动下单已暂停。切换为手动模式后可继续操作。"
        )
        self.mode_hint.setObjectName("tradeModeHint")
        self.mode_hint.setWordWrap(True)
        self.mode_hint.hide()
        layout.addWidget(self.mode_hint)

        # 交易对
        self.symbol_combo = QComboBox()
        self.symbol_combo.addItems(Config.DEFAULT_SYMBOLS)
        layout.addWidget(self.symbol_combo)

        # 限价 / 市价 Tab 按钮
        type_row = QHBoxLayout()
        type_row.setSpacing(0)
        self.type_group = QButtonGroup(self)
        self._limit_btn = QPushButton("限价单")
        self._market_btn = QPushButton("市价单")
        for i, btn in enumerate([self._limit_btn, self._market_btn]):
            btn.setCheckable(True)
            btn.setFixedHeight(32)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.type_group.addButton(btn, i)
            type_row.addWidget(btn)
        self._limit_btn.setChecked(True)
        layout.addLayout(type_row)

        # 价格
        self.price_cap = QLabel("价格 (USDT)")
        self.price_cap.setObjectName("captionLabel")
        layout.addWidget(self.price_cap)
        self.price_input = QDoubleSpinBox()
        self.price_input.setRange(0, 9999999)
        self.price_input.setDecimals(2)
        self.price_input.setButtonSymbols(
            QDoubleSpinBox.ButtonSymbols.UpDownArrows)
        layout.addWidget(self.price_input)

        # 数量
        self.qty_cap = QLabel("数量 (BTC)")
        self.qty_cap.setObjectName("captionLabel")
        layout.addWidget(self.qty_cap)
        self.qty_input = QDoubleSpinBox()
        self.qty_input.setRange(0, 9999)
        self.qty_input.setDecimals(4)
        self.qty_input.setSingleStep(0.001)
        layout.addWidget(self.qty_input)

        # 百分比快捷
        pct_row = QHBoxLayout()
        pct_row.setSpacing(6)
        self._pct_btns = []
        for pct in [25, 50, 75, 100]:
            btn = QPushButton(f"{pct}%")
            btn.setFixedHeight(28)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, v=pct: self._set_qty_pct(v))
            pct_row.addWidget(btn)
            self._pct_btns.append(btn)
        layout.addLayout(pct_row)

        # 止盈 / 止损
        sl_tp_row = QHBoxLayout()
        sl_tp_row.setSpacing(8)

        tp_col = QVBoxLayout()
        tp_cap = QLabel("止盈 (可选)")
        tp_cap.setObjectName("dimLabel")
        self.take_profit_input = QDoubleSpinBox()
        self.take_profit_input.setRange(0, 9999999)
        self.take_profit_input.setDecimals(2)
        self.take_profit_input.setSpecialValueText("—")
        tp_col.addWidget(tp_cap)
        tp_col.addWidget(self.take_profit_input)

        sl_col = QVBoxLayout()
        sl_cap = QLabel("止损 (可选)")
        sl_cap.setObjectName("dimLabel")
        self.stop_loss_input = QDoubleSpinBox()
        self.stop_loss_input.setRange(0, 9999999)
        self.stop_loss_input.setDecimals(2)
        self.stop_loss_input.setSpecialValueText("—")
        sl_col.addWidget(sl_cap)
        sl_col.addWidget(self.stop_loss_input)

        sl_tp_row.addLayout(tp_col)
        sl_tp_row.addLayout(sl_col)
        layout.addLayout(sl_tp_row)

        # 可用余额
        self.avail_label = QLabel("可用: — USDT")
        self.avail_label.setObjectName("captionLabel")
        layout.addWidget(self.avail_label)

        # 买卖按钮
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        self.buy_btn = QPushButton("买入 / 做多")
        self.buy_btn.setObjectName("buyBtn")
        self.buy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.buy_btn.clicked.connect(lambda: self._submit_order("BUY"))
        self.sell_btn = QPushButton("卖出 / 做空")
        self.sell_btn.setObjectName("sellBtn")
        self.sell_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sell_btn.clicked.connect(lambda: self._submit_order("SELL"))
        btn_row.addWidget(self.buy_btn)
        btn_row.addWidget(self.sell_btn)
        layout.addLayout(btn_row)

        # 费用预估
        self.fee_label = QLabel("预估手续费: —  ·  预估保证金: —")
        self.fee_label.setObjectName("dimLabel")
        self.fee_label.setWordWrap(True)
        layout.addWidget(self.fee_label)

        # 隐藏的价格标签（兼容旧 API）
        self.price_label = QLabel()
        self.price_label.hide()

        layout.addStretch()
        root.addWidget(self._card)

        self.qty_input.valueChanged.connect(self._update_estimate)
        self.price_input.valueChanged.connect(self._update_estimate)
        self.type_group.buttonClicked.connect(self._on_type_changed)
        self.symbol_combo.currentTextChanged.connect(self._on_symbol_changed)

    def _refresh_theme(self):
        t = Theme.colors()
        self._card.setStyleSheet(Theme.card_style())
        for btn in [self._limit_btn, self._market_btn]:
            self._style_type_btn(btn, btn.isChecked())
        for btn in self._pct_btns:
            btn.setStyleSheet(
                f"font-size:12px; padding:2px; border:1px solid {t['border']}; "
                f"border-radius:4px; background:transparent; color:{t['text_secondary']};")
        self.mode_hint.setStyleSheet(
            f"color:{t['warning']}; background:{t['tip_bg']}; "
            f"border:1px solid {t['tip_border']}; border-radius:6px; "
            "padding:7px; font-size:11px;"
        )

    def _style_type_btn(self, btn: QPushButton, active: bool):
        t = Theme.colors()
        if active:
            btn.setStyleSheet(
                f"background:{t['accent']}; color:#fff; border:none; "
                f"font-weight:600; font-size:13px;")
        else:
            btn.setStyleSheet(
                f"background:{t['bg_main']}; color:{t['text_secondary']}; "
                f"border:1px solid {t['border']}; font-size:13px;")

    def _on_type_changed(self, btn):
        for b in [self._limit_btn, self._market_btn]:
            self._style_type_btn(b, b is btn)
        # 市价单禁用价格输入
        self.price_input.setEnabled(btn is self._limit_btn)

    def _on_symbol_changed(self, symbol: str):
        base = symbol.removesuffix("USDT")
        self.qty_cap.setText(f"数量 ({base})")

    def update_price(self, price: float):
        self._last_price = float(price)
        decimals = self._price_decimals(price)
        for control in (
            self.price_input, self.take_profit_input, self.stop_loss_input
        ):
            control.setDecimals(decimals)
            control.setSingleStep(10 ** -decimals)
        self.price_label.setText(f"{price:,.{decimals}f}")
        if not self.price_input.hasFocus():
            self.price_input.setValue(price)

    def set_available(self, amount: float):
        self._available = amount
        self.avail_label.setText(f"可用: {amount:,.2f} USDT")
        self._update_estimate()

    def _set_qty_pct(self, pct: int):
        price = self.price_input.value()
        if price <= 0 or self._available <= 0:
            return
        qty = (self._available * pct / 100) / price
        self.qty_input.setValue(round(qty, 4))

    def _update_estimate(self):
        qty = self.qty_input.value()
        price = self.price_input.value()
        notional = qty * price
        fee = notional * 0.001
        self.fee_label.setText(
            f"预估手续费: {fee:.4f} USDT  ·  预估保证金: {notional:,.2f} USDT")

    def _submit_order(self, side: str):
        sym = self.symbol_combo.currentText()
        qty = self.qty_input.value()
        price = self.price_input.value()
        sl = self.stop_loss_input.value()
        tp = self.take_profit_input.value()
        if qty <= 0:
            QMessageBox.warning(
                self, "无法下单",
                "请输入交易数量，或使用 25% / 50% / 75% / 100% 快捷按钮。"
            )
            self.qty_input.setFocus()
            return
        if price <= 0:
            QMessageBox.warning(
                self, "无法下单", "当前价格无效，请等待行情更新后重试。"
            )
            return
        self.place_order.emit(sym, side, qty, price, sl, tp)

    def set_manual_enabled(self, enabled: bool):
        """锁定下单控件时保留明确说明，避免整栏看似失效。"""
        controls = [
            self.symbol_combo, self._limit_btn, self._market_btn,
            self.price_input, self.qty_input,
            self.take_profit_input, self.stop_loss_input,
            self.buy_btn, self.sell_btn, *self._pct_btns,
        ]
        for control in controls:
            control.setEnabled(enabled)
        if enabled and self._market_btn.isChecked():
            self.price_input.setEnabled(False)
        self.mode_hint.setVisible(not enabled)

    @staticmethod
    def _price_decimals(price: float) -> int:
        price = abs(float(price))
        if price >= 100:
            return 2
        if price >= 1:
            return 4
        if price >= 0.01:
            return 6
        return 8
