from PyQt6.QtWidgets import QApplication

from gui.pnl_bar import PnlBar
from gui.trade_panel import TradePanel


def _app():
    return QApplication.instance() or QApplication([])


def test_refresh_button_emits_once_and_shows_loading_state():
    app = _app()
    bar = PnlBar()
    emitted = []
    bar.refresh_requested.connect(lambda: emitted.append(True))

    bar.refresh_btn.click()

    assert emitted == [True]
    assert not bar.refresh_btn.isEnabled()
    assert "正在刷新" in bar.refresh_btn.toolTip()

    bar.set_refreshing(False)
    assert bar.refresh_btn.isEnabled()
    assert app is QApplication.instance()


def test_api_button_has_connecting_state():
    app = _app()
    bar = PnlBar()

    bar.set_api_connecting()

    assert bar.api_btn.text() == "… API"
    assert not bar._api_ok
    assert app is QApplication.instance()


def test_global_refresh_can_clear_manual_exit_prices():
    app = _app()
    panel = TradePanel()
    panel.update_price(100)
    panel.stop_loss_input.setValue(99)
    panel.take_profit_input.setValue(102)

    panel.clear_exit_prices()

    assert panel.stop_loss_input.value() == 0
    assert panel.take_profit_input.value() == 0
    assert "不填写百分比" in panel.exit_price_hint.text()
    assert app is QApplication.instance()


def test_market_update_clears_any_unedited_value_from_stop_loss():
    app = _app()
    panel = TradePanel()

    # 模拟外部行情刷新链路错误地把现货价写入止损栏。
    panel.stop_loss_input.setValue(68_419.99)
    panel.update_price(68_420)

    assert panel.price_input.value() == 68_420
    assert panel.stop_loss_input.value() == 0
    assert panel.stop_loss_input.text() == "—"
    assert app is QApplication.instance()


def test_user_entered_exit_price_survives_market_refresh():
    app = _app()
    panel = TradePanel()
    panel.stop_loss_input.lineEdit().textEdited.emit("67,000")
    panel.stop_loss_input.setValue(67_000)

    panel.update_price(67_000)

    assert panel.stop_loss_input.value() == 67_000
    assert app is QApplication.instance()


def test_auto_filled_spot_stop_does_not_block_manual_order():
    app = _app()
    panel = TradePanel()
    panel.update_price(68_420)
    panel.qty_input.setValue(0.01)
    panel.stop_loss_input.setValue(68_420)
    orders = []
    panel.place_order.connect(lambda *args: orders.append(args))

    panel._submit_order("BUY")

    assert len(orders) == 1
    assert orders[0][4] == 0
    assert panel.stop_loss_input.value() == 0
    assert app is QApplication.instance()


def test_exit_price_only_participates_after_user_enables_it():
    app = _app()
    panel = TradePanel()
    panel.update_price(64_812.8)
    panel.qty_input.setValue(0.01)
    panel.stop_loss_input.setValue(65_450)
    orders = []
    panel.place_order.connect(lambda *args: orders.append(args))

    panel._submit_order("BUY")

    assert len(orders) == 1
    assert orders[0][4] == 0
    assert not panel.stop_loss_enabled.isChecked()
    assert app is QApplication.instance()
