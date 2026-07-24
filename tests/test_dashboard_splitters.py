from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from gui.main_window import MainWindow


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
