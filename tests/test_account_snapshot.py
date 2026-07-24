from PyQt6.QtWidgets import QApplication

from gui.capital_panel import CapitalPanel
from services.account_sync import fetch_account_snapshot


class FakeAccountClient:
    def get_nonzero_balances(self):
        return [
            {"asset": "USDT", "free": 900.0, "locked": 20.0},
            {"asset": "BTC", "free": 0.001, "locked": 0.0005},
            {"asset": "UNKNOWN", "free": 2.0, "locked": 0.0},
        ]

    def get_symbol_price(self, symbol):
        if symbol == "BTCUSDT":
            return 60_000.0
        raise RuntimeError("no USDT market")


def _app():
    return QApplication.instance() or QApplication([])


def test_account_snapshot_uses_one_consistent_usdt_valuation():
    snapshot = fetch_account_snapshot(FakeAccountClient())

    assert snapshot["total_value_usdt"] == 1010.0
    assert snapshot["free_value_usdt"] == 960.0
    assert snapshot["locked_value_usdt"] == 50.0
    assert snapshot["available_usdt"] == 900.0
    assert snapshot["non_usdt_value_usdt"] == 90.0
    assert snapshot["unpriced_assets"] == ["UNKNOWN"]
    assert snapshot["updated_at"] > 0


def test_capital_panel_labels_real_values_and_source():
    app = _app()
    panel = CapitalPanel()
    snapshot = fetch_account_snapshot(FakeAccountClient())

    panel.update_exchange_snapshot(snapshot, reserve_ratio=0.20)

    assert panel.total_value_label.text() == "1,010.00 USDT"
    assert panel.available_label.text() == "900.00"
    assert panel.locked_label.text() == "50.00"
    assert panel.margin_label.text() == "90.00"
    assert panel.reserve_label.text() == "202.00"
    assert panel.source_label.text().startswith("币安 · ")
    assert [label.text() for label in panel._cap_labels.values()] == [
        "可用 USDT",
        "冻结资产",
        "非 USDT 资产",
        "计划准备金",
    ]
    assert "UNKNOWN" in panel.source_label.toolTip()
    assert app is QApplication.instance()
