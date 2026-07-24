from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from gui.scene_panel import ScenePanel, _BUTTON_KEYS, _RadarWidget


def _app():
    return QApplication.instance() or QApplication([])


def test_scene_buttons_follow_requested_display_order():
    app = _app()
    panel = ScenePanel()

    button_texts = [
        panel.scene_buttons[key].text()
        for key in _BUTTON_KEYS
    ]

    assert _BUTTON_KEYS == [
        "TRENDING",
        "RANGING",
        "BREAKOUT",
        "REVERSAL",
        "EXTREME",
    ]
    assert button_texts == ["趋势", "震荡", "突破", "反转", "极端"]
    assert app is QApplication.instance()


def test_radar_labels_use_fixed_corner_slots():
    width, height = 220, 180

    trend, trend_align = _RadarWidget._label_slot(
        "TRENDING", width, height
    )
    ranging, ranging_align = _RadarWidget._label_slot(
        "RANGING", width, height
    )
    breakout, breakout_align = _RadarWidget._label_slot(
        "BREAKOUT", width, height
    )
    reversal, reversal_align = _RadarWidget._label_slot(
        "REVERSAL", width, height
    )
    extreme, extreme_align = _RadarWidget._label_slot(
        "EXTREME", width, height
    )

    assert trend.center().x() == width / 2
    assert trend.top() == 2
    assert ranging.left() == reversal.left() == 2
    assert breakout.right() == extreme.right() == width - 2
    assert ranging.top() == breakout.top()
    assert reversal.bottom() == extreme.bottom() == height - 2
    assert trend_align == Qt.AlignmentFlag.AlignHCenter
    assert ranging_align == reversal_align == Qt.AlignmentFlag.AlignLeft
    assert breakout_align == extreme_align == Qt.AlignmentFlag.AlignRight
