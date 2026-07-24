from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from gui.main_window import (
    MAX_PARALLEL_AUTOMATION_EVALUATIONS,
    MainWindow,
)
from services.automation_manager import RUNNING


def _app():
    return QApplication.instance() or QApplication([])


def test_dashboard_splitters_have_draggable_hit_areas(monkeypatch):
    app = _app()
    monkeypatch.setattr(MainWindow, "_start_data_worker", lambda self: None)
    monkeypatch.setattr(MainWindow, "_test_api_connection", lambda self: None)
    monkeypatch.setattr(QTimer, "singleShot", lambda *args: None)

    window = MainWindow()
    window.update_timer.stop()
    window.automation_timer.stop()
    window.open_orders_timer.stop()
    window.account_sync_timer.stop()

    assert window.body_splitter.handleWidth() == 7
    assert window.center_splitter.handleWidth() == 7
    assert window.left_scroll.minimumWidth() == 200
    assert window.left_scroll.maximumWidth() == 420
    assert "左右拖动" in window.body_splitter.handle(1).toolTip()
    assert "上下拖动" in window.center_splitter.handle(1).toolTip()

    window.close()
    assert app is QApplication.instance()


def test_automation_signals_are_deduplicated_in_order_queue(monkeypatch):
    app = _app()
    monkeypatch.setattr(MainWindow, "_start_data_worker", lambda self: None)
    monkeypatch.setattr(MainWindow, "_test_api_connection", lambda self: None)
    monkeypatch.setattr(QTimer, "singleShot", lambda *args: None)

    window = MainWindow()
    window.update_timer.stop()
    window.automation_timer.stop()
    window.automation_order_timer.stop()
    window.open_orders_timer.stop()
    window.account_sync_timer.stop()
    task = window.automation_manager.tasks[0]
    task.status = RUNNING
    signal = {
        "symbol": task.symbol,
        "side": "BUY",
        "price": 100.0,
        "reason": "test",
    }
    key = ("BUY", 100.0, "test")

    window._enqueue_automation_signal(task, {}, signal, key)
    window._enqueue_automation_signal(task, {}, signal, key)

    assert len(window._automation_order_queue) == 1
    assert len(window._queued_auto_signal_keys) == 1
    assert MAX_PARALLEL_AUTOMATION_EVALUATIONS == 3
    window.close()
    assert app is QApplication.instance()
