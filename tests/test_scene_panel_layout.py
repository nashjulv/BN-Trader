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


def test_radar_labels_stay_near_the_five_outer_vertices():
    width, height = 220, 180
    radius = 62
    slots = {
        key: _RadarWidget._label_slot(
            key, width, height, radius=radius
        )
        for key in [
            "TRENDING", "RANGING", "BREAKOUT", "REVERSAL", "EXTREME"
        ]
    }

    trend, trend_align = slots["TRENDING"]
    ranging, ranging_align = slots["RANGING"]
    breakout, breakout_align = slots["BREAKOUT"]
    reversal, reversal_align = slots["REVERSAL"]
    extreme, extreme_align = slots["EXTREME"]

    assert trend.center().x() == width / 2
    assert trend.center().y() < height / 2
    assert ranging.center().x() < width / 2
    assert breakout.center().x() > width / 2
    assert reversal.center().x() < width / 2
    assert extreme.center().x() > width / 2
    assert reversal.center().y() > height / 2
    assert extreme.center().y() > height / 2
    for rect, _alignment in slots.values():
        assert rect.left() >= 2
        assert rect.top() >= 2
        assert rect.right() <= width - 2
        assert rect.bottom() <= height - 2
    assert trend_align == Qt.AlignmentFlag.AlignHCenter
    assert ranging_align == reversal_align == Qt.AlignmentFlag.AlignLeft
    assert breakout_align == extreme_align == Qt.AlignmentFlag.AlignRight
