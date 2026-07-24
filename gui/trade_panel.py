"""
手动下单面板 — 匹配 UI 设计稿右侧下单区
限价单 / 市价单 · 价格 · 数量 · 百分比 · 止盈止损 · 买入/卖出
"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QComboBox, QDoubleSpinBox,
                               QFrame, QButtonGroup, QMessageBox, QCheckBox)
from PyQt6.QtCore import Qt, pyqtSignal

from gui.styles import Theme
from config import Config


class ManualPriceSpinBox(QDoubleSpinBox):
    """可区分人工步进与程序 setValue 的价格输入框。"""

    user_edited = pyqtSignal()

    def stepBy(self, steps: int):
        self.user_edited.emit()
        super().stepBy(steps)


def validate_exit_prices(
    side: str,
    entry_price: float,
    stop_loss: float = 0.0,
    take_profit: float = 0.0,
    max_loss_ratio: float | None = None,
) -> tuple[bool, str]:
    """校验手动订单的绝对止盈/止损价格，并返回可操作的提示。"""
    side = side.upper()
    if entry_price <= 0:
        return False, "当前入场价格无效，请等待行情更新后重试。"

    if stop_loss > 0:
        wrong_side = (
            side == "BUY" and stop_loss >= entry_price
        ) or (
            side == "SELL" and stop_loss <= entry_price
        )
        if wrong_side:
            direction = "低于" if side == "BUY" else "高于"
            return (
                False,
                f"止损价必须{direction}入场价。\n\n"
                f"入场价：{entry_price:g} USDT\n"
                f"止损价：{stop_loss:g} USDT\n\n"
                "这里填写的是目标价格，不是百分比。",
            )

        loss_ratio = abs(entry_price - stop_loss) / entry_price
        if max_loss_ratio is not None and loss_ratio > max_loss_ratio:
            return (
                False,
                f"止损价距离入场价 {loss_ratio:.2%}，"
                f"超过当前单笔风险上限 {max_loss_ratio:.2%}。\n\n"
                f"入场价：{entry_price:g} USDT\n"
                f"止损价：{stop_loss:g} USDT\n\n"
                "这里填写的是绝对价格，不是百分比。"
                "例如入场价 100、止损 0.7%，应填写 99.3（买入）或 100.7（卖出）。",
            )

    if take_profit > 0:
        wrong_side = (
            side == "BUY" and take_profit <= entry_price
        ) or (
            side == "SELL" and take_profit >= entry_price
        )
        if wrong_side:
            direction = "高于" if side == "BUY" else "低于"
            return (
                False,
                f"止盈价必须{direction}入场价。\n\n"
                f"入场价：{entry_price:g} USDT\n"
                f"止盈价：{take_profit:g} USDT\n\n"
                "这里填写的是目标价格，不是百分比。",
            )

    return True, ""


def validate_available_balance(
    side: str,
    quantity: float,
    price: float,
    quote_available: float,
    base_available: float,
    base_asset: str = "BTC",
    quote_asset: str = "USDT",
) -> tuple[bool, str]:
    """按币安 free 余额校验手动订单，避免提交必然失败的订单。"""
    if side.upper() == "BUY":
        required = quantity * price
        if required > quote_available + 1e-9:
            return (
                False,
                f"可用 {quote_asset} 余额不足。\n\n"
                f"订单预计需要：{required:,.4f} {quote_asset}\n"
                f"币安实际可用：{quote_available:,.4f} {quote_asset}\n\n"
                "请减少数量，或同步账户后重试。",
            )
    elif quantity > base_available + 1e-12:
        return (
            False,
            f"可用 {base_asset} 余额不足。\n\n"
            f"计划卖出：{quantity:g} {base_asset}\n"
            f"币安实际可用：{base_available:g} {base_asset}\n\n"
            "请减少数量，或确认资产是否被其他挂单锁定。",
        )
    return True, ""


class TradePanel(QWidget):
    place_order = pyqtSignal(str, str, float, float, float, float)

    def __init__(self):
        super().__init__()
        self.setMinimumWidth(240)
        self._available = 0.0
        self._quote_available = 0.0
        self._base_available = 0.0
        self._base_asset = "BTC"
        self._quote_asset = "USDT"
        self._exchange_balance_mode = False
        self._last_price = 0.0
        self._manual_enabled = True
        self._stop_loss_user_edited = False
        self._take_profit_user_edited = False
        self._max_loss_ratio = Config.MAX_LOSS_PER_TRADE
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
            btn.setToolTip("按币安可用 USDT 余额计算买入数量")
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

        sl_col = QVBoxLayout()
        self.stop_loss_enabled = QCheckBox("启用止损价 (USDT)")
        self.stop_loss_enabled.setToolTip("勾选后，止损价才会参与订单校验")
        self.stop_loss_input = ManualPriceSpinBox()
        self.stop_loss_input.setRange(0, 9999999)
        self.stop_loss_input.setDecimals(2)
        self.stop_loss_input.setSpecialValueText("—")
        self.stop_loss_input.setToolTip("填写止损目标价格，不是百分比")
        self.stop_loss_input.setEnabled(False)
        self.stop_loss_input.lineEdit().textEdited.connect(
            lambda _text: self._mark_exit_price_edited("stop_loss")
        )
        self.stop_loss_input.user_edited.connect(
            lambda: self._mark_exit_price_edited("stop_loss")
        )
        self.stop_loss_enabled.toggled.connect(
            lambda enabled: self._toggle_exit_price("stop_loss", enabled)
        )
        sl_col.addWidget(self.stop_loss_enabled)
        sl_col.addWidget(self.stop_loss_input)

        tp_col = QVBoxLayout()
        self.take_profit_enabled = QCheckBox("启用止盈价 (USDT)")
        self.take_profit_enabled.setToolTip("勾选后，止盈价才会参与订单校验")
        self.take_profit_input = ManualPriceSpinBox()
        self.take_profit_input.setRange(0, 9999999)
        self.take_profit_input.setDecimals(2)
        self.take_profit_input.setSpecialValueText("—")
        self.take_profit_input.setToolTip("填写止盈目标价格，不是百分比")
        self.take_profit_input.setEnabled(False)
        self.take_profit_input.lineEdit().textEdited.connect(
            lambda _text: self._mark_exit_price_edited("take_profit")
        )
        self.take_profit_input.user_edited.connect(
            lambda: self._mark_exit_price_edited("take_profit")
        )
        self.take_profit_enabled.toggled.connect(
            lambda enabled: self._toggle_exit_price("take_profit", enabled)
        )
        tp_col.addWidget(self.take_profit_enabled)
        tp_col.addWidget(self.take_profit_input)

        # 与交易逻辑顺序一致：先止损，再止盈。
        sl_tp_row.addLayout(sl_col)
        sl_tp_row.addLayout(tp_col)
        layout.addLayout(sl_tp_row)

        self.exit_price_hint = QLabel("止盈/止损请输入目标价格，不填写百分比。")
        self.exit_price_hint.setObjectName("dimLabel")
        self.exit_price_hint.setWordWrap(True)
        layout.addWidget(self.exit_price_hint)

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
        self.price_input.valueChanged.connect(self._refresh_exit_hint)
        self.take_profit_input.valueChanged.connect(self._refresh_exit_hint)
        self.stop_loss_input.valueChanged.connect(self._refresh_exit_hint)
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
        self.exit_price_hint.setStyleSheet(
            f"color:{t['text_secondary']}; font-size:11px;"
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
        base = symbol.split("/")[0] if "/" in symbol else symbol.removesuffix("USDT")
        self.qty_cap.setText(f"数量 ({base})")
        # 退出价是交易对相关的绝对价格，切换币种时不可沿用旧值。
        self.clear_exit_prices()

    def update_price(self, price: float):
        self._last_price = float(price)
        decimals = self._price_decimals(price)
        for control in (
            self.price_input, self.take_profit_input, self.stop_loss_input
        ):
            control.setDecimals(decimals)
            control.setSingleStep(10 ** -decimals)
        # 行情只允许更新入场价。若外部刷新错误地把现货价写进退出价，
        # 且用户从未编辑过该字段，则立即恢复为空。
        self._clear_unedited_exit_prices()
        self.price_label.setText(f"{price:,.{decimals}f}")
        if not self.price_input.hasFocus():
            self.price_input.setValue(price)

    def set_available(self, amount: float):
        self._exchange_balance_mode = False
        self._available = amount
        self.avail_label.setText(f"可用: {amount:,.2f} USDT")
        self._update_estimate()

    def set_exchange_balances(
        self,
        quote_amount: float,
        base_amount: float,
        base_asset: str,
        quote_asset: str = "USDT",
    ):
        """使用交易所 free 余额，而不是本地模拟资金池。"""
        self._exchange_balance_mode = True
        self._available = max(0.0, float(quote_amount))
        self._quote_available = self._available
        self._base_available = max(0.0, float(base_amount))
        self._base_asset = base_asset
        self._quote_asset = quote_asset
        self.avail_label.setText(
            f"可用: {self._quote_available:,.2f} {quote_asset}"
            f" · {self._base_available:g} {base_asset}"
        )
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

    def _refresh_exit_hint(self):
        entry = self.price_input.value()
        sl = (
            self.stop_loss_input.value()
            if self.stop_loss_enabled.isChecked() else 0
        )
        tp = (
            self.take_profit_input.value()
            if self.take_profit_enabled.isChecked() else 0
        )
        parts = []
        if entry > 0 and sl > 0:
            parts.append(f"止损距离 {abs(entry - sl) / entry:.2%}")
        if entry > 0 and tp > 0:
            parts.append(f"止盈距离 {abs(entry - tp) / entry:.2%}")
        self.exit_price_hint.setText(
            " · ".join(parts) if parts
            else "止盈/止损请输入目标价格，不填写百分比。"
        )

    def set_max_loss_ratio(self, ratio: float):
        self._max_loss_ratio = max(0.0, float(ratio))

    def _mark_exit_price_edited(self, field: str):
        if field == "stop_loss":
            self._stop_loss_user_edited = True
        elif field == "take_profit":
            self._take_profit_user_edited = True

    def _toggle_exit_price(self, field: str, enabled: bool):
        control = (
            self.stop_loss_input
            if field == "stop_loss"
            else self.take_profit_input
        )
        control.setEnabled(enabled and self._manual_enabled)
        if not enabled:
            if field == "stop_loss":
                self._stop_loss_user_edited = False
            else:
                self._take_profit_user_edited = False
            control.setValue(0)
        self._refresh_exit_hint()

    def _clear_unedited_exit_prices(self):
        """任何非用户输入的退出价都无效，避免行情或缓存误回填。"""
        if not self._stop_loss_user_edited and self.stop_loss_input.value() > 0:
            self.stop_loss_input.setValue(0)
        if not self._take_profit_user_edited and self.take_profit_input.value() > 0:
            self.take_profit_input.setValue(0)

    def clear_exit_prices(self):
        """清除与交易对价格绑定的手动退出价。"""
        self._stop_loss_user_edited = False
        self._take_profit_user_edited = False
        self.stop_loss_enabled.setChecked(False)
        self.take_profit_enabled.setChecked(False)
        self.stop_loss_input.setValue(0)
        self.take_profit_input.setValue(0)
        self._refresh_exit_hint()

    def _submit_order(self, side: str):
        sym = self.symbol_combo.currentText()
        qty = self.qty_input.value()
        price = self.price_input.value()
        sl = (
            self.stop_loss_input.value()
            if self.stop_loss_enabled.isChecked() else 0
        )
        tp = (
            self.take_profit_input.value()
            if self.take_profit_enabled.isChecked() else 0
        )
        # 二次防护：未由用户输入、却与现货价相同的退出价视为空值，
        # 避免错误的行情回填阻断手动下单。
        self._clear_unedited_exit_prices()
        sl = (
            self.stop_loss_input.value()
            if self.stop_loss_enabled.isChecked() else 0
        )
        tp = (
            self.take_profit_input.value()
            if self.take_profit_enabled.isChecked() else 0
        )
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
        if self._exchange_balance_mode:
            balance_ok, balance_message = validate_available_balance(
                side,
                qty,
                price,
                self._quote_available,
                self._base_available,
                self._base_asset,
                self._quote_asset,
            )
            if not balance_ok:
                QMessageBox.warning(
                    self, "余额不足", balance_message
                )
                self.qty_input.setFocus()
                return
        valid, message = validate_exit_prices(
            side, price, sl, tp, self._max_loss_ratio
        )
        if not valid:
            QMessageBox.warning(self, "止盈止损价格无效", message)
            self.stop_loss_input.setFocus()
            return
        self.place_order.emit(sym, side, qty, price, sl, tp)

    def set_manual_enabled(self, enabled: bool):
        """锁定下单控件时保留明确说明，避免整栏看似失效。"""
        self._manual_enabled = enabled
        controls = [
            self.symbol_combo, self._limit_btn, self._market_btn,
            self.price_input, self.qty_input,
            self.take_profit_enabled, self.stop_loss_enabled,
            self.buy_btn, self.sell_btn, *self._pct_btns,
        ]
        for control in controls:
            control.setEnabled(enabled)
        if enabled and self._market_btn.isChecked():
            self.price_input.setEnabled(False)
        self.stop_loss_input.setEnabled(
            enabled and self.stop_loss_enabled.isChecked()
        )
        self.take_profit_input.setEnabled(
            enabled and self.take_profit_enabled.isChecked()
        )
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
