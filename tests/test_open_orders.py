from PyQt6.QtWidgets import QApplication

from gui.main_window import normalize_open_order
from gui.open_orders_panel import OpenOrdersPanel


def _app():
    return QApplication.instance() or QApplication([])


def test_normalize_binance_open_order():
    order = normalize_open_order({
        "orderId": 12345,
        "symbol": "BTCUSDT",
        "side": "BUY",
        "origQty": "0.00100000",
        "executedQty": "0.00020000",
        "price": "64743.68000000",
        "status": "PARTIALLY_FILLED",
        "type": "LIMIT",
    })

    assert order == {
        "order_id": "12345",
        "symbol": "BTCUSDT",
        "side": "BUY",
        "quantity": 0.001,
        "executed_quantity": 0.0002,
        "price": 64743.68,
        "status": "PARTIALLY_FILLED",
        "type": "LIMIT",
    }


def test_open_orders_panel_displays_synced_order():
    app = _app()
    panel = OpenOrdersPanel()

    panel.update_orders([{
        "order_id": "12345",
        "symbol": "BTCUSDT",
        "side": "BUY",
        "quantity": 0.001,
        "price": 64743.68,
        "status": "NEW",
    }])

    assert panel._count.text() == "1 挂单 · 1 最近"
    assert panel._empty.isHidden()
    assert panel._list.count() == 1
    assert app is QApplication.instance()


def test_market_fill_uses_average_execution_price():
    order = normalize_open_order({
        "orderId": 9,
        "symbol": "BTCUSDT",
        "side": "BUY",
        "origQty": "0.001",
        "executedQty": "0.001",
        "cummulativeQuoteQty": "64.75",
        "price": "0",
        "status": "FILLED",
        "type": "MARKET",
    })

    assert order["price"] == 64750
