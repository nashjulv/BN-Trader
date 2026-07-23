"""
左侧图标导航栏 — 匹配 UI 设计稿
主页 / 策略 / 资金 / 风控 / 持仓 / 日志 / 回测 / 设置
"""

from typing import Dict, List, Tuple

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QToolButton, QLabel, QFrame
)
from PyQt6.QtCore import Qt, QSize, QRectF, QPointF, pyqtSignal
from PyQt6.QtGui import (
    QFont, QColor, QIcon, QPainter, QPixmap, QPen, QPainterPath
)

from gui.styles import Theme


# (key, icon_char, tooltip)
NAV_ITEMS: List[Tuple[str, str, str]] = [
    ("dashboard", "⌂",  "主界面"),
    ("strategy",  "◈",  "策略设置"),
    ("capital",   "◎",  "资金概览"),
    ("risk",      "⬡",  "风控设置"),
    ("position",  "▣",  "持仓设置"),
    ("logs",      "☰",  "日志详情"),
    ("backtest",  "▷",  "回测"),
    ("help",      "?",  "帮助中心"),
    ("settings",  "⚙",  "API / 设置"),
]

NAV_LABELS = {
    "dashboard": "行情", "strategy": "策略", "capital": "资金",
    "risk": "风控", "position": "持仓", "logs": "日志",
    "backtest": "复盘", "help": "帮助", "settings": "设置",
}

class SideBar(QWidget):
    """窄图标侧栏"""

    navigated = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setFixedWidth(56)
        self._btns: Dict[str, QToolButton] = {}
        self._active = "dashboard"
        self._init_ui()
        self._apply_theme()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 12, 0, 12)
        layout.setSpacing(4)

        # Logo
        logo = QLabel("BN")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setFixedHeight(36)
        font = QFont()
        font.setBold(True)
        font.setPointSize(11)
        logo.setFont(font)
        self._logo = logo
        layout.addWidget(logo)

        line = QFrame()
        line.setFixedHeight(1)
        line.setObjectName("separator")
        self._sep = line
        layout.addWidget(line)
        layout.addSpacing(8)

        for key, icon, tip in NAV_ITEMS:
            btn = QToolButton()
            btn.setText(NAV_LABELS[key])
            btn.setIconSize(QSize(16, 16))
            btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            btn.setCheckable(True)
            btn.setFixedSize(48, 48)
            btn.setToolTip(tip)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, k=key: self._on_click(k))
            self._btns[key] = btn
            layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignHCenter)

        layout.addStretch()
        self._btns["dashboard"].setChecked(True)

    def _on_click(self, key: str):
        self.set_active(key)
        self.navigated.emit(key)

    def set_active(self, key: str):
        self._active = key
        for k, btn in self._btns.items():
            btn.setChecked(k == key)
        self._apply_theme()

    def _apply_theme(self):
        t = Theme.colors()
        self.setStyleSheet(f"background:{t['bg_sidebar']};")
        self._logo.setStyleSheet(
            f"color:{t['accent']}; background:transparent;")
        self._sep.setStyleSheet(
            f"background:{t['border']}; max-height:1px; border:none;")

        for key, btn in self._btns.items():
            active = key == self._active
            btn.setIcon(self._line_icon(
                key, t["accent"] if active else t["text_sidebar_dim"]))
            if active:
                btn.setStyleSheet(
                    f"QToolButton {{"
                    f"  background:{t['accent_light']}; color:{t['accent']};"
                    f"  border:none; border-radius:8px;"
                    f"  font-size:11px; font-weight:600; padding:2px;"
                    f"}}"
                    f"QToolButton:hover {{ background:{t['bg_hover']}; color:{t['accent']}; }}"
                )
            else:
                btn.setStyleSheet(
                    f"QToolButton {{"
                    f"  background:transparent; color:{t['text_sidebar_dim']};"
                    f"  border:none; border-radius:8px;"
                    f"  font-size:11px; padding:2px;"
                    f"}}"
                    f"QToolButton:hover {{"
                    f"  background:{t['bg_hover']}; color:{t['text_primary']};"
                    f"}}"
                )

    @staticmethod
    def _line_icon(key: str, color: str) -> QIcon:
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

        if key == "dashboard":
            painter.drawLine(QPointF(3, 16), QPointF(17, 16))
            painter.drawRoundedRect(QRectF(4, 10, 2.5, 5), 1, 1)
            painter.drawRoundedRect(QRectF(8.8, 6, 2.5, 9), 1, 1)
            painter.drawRoundedRect(QRectF(13.5, 3, 2.5, 12), 1, 1)
        elif key == "strategy":
            path = QPainterPath(QPointF(3, 14))
            path.lineTo(7, 10)
            path.lineTo(10, 12)
            path.lineTo(16, 5)
            painter.drawPath(path)
            painter.drawLine(QPointF(12.5, 5), QPointF(16, 5))
            painter.drawLine(QPointF(16, 5), QPointF(16, 8.5))
        elif key == "capital":
            painter.drawRoundedRect(QRectF(2.5, 5, 15, 11), 2.5, 2.5)
            painter.drawLine(QPointF(3, 8), QPointF(17, 8))
            painter.drawEllipse(QPointF(14, 12), 1, 1)
        elif key == "risk":
            path = QPainterPath(QPointF(10, 2.5))
            path.lineTo(16, 5)
            path.lineTo(15, 12)
            path.quadTo(13.5, 16, 10, 17.5)
            path.quadTo(6.5, 16, 5, 12)
            path.lineTo(4, 5)
            path.closeSubpath()
            painter.drawPath(path)
        elif key == "position":
            painter.drawRoundedRect(QRectF(3, 4, 14, 12), 2, 2)
            painter.drawLine(QPointF(3, 8), QPointF(17, 8))
            painter.drawLine(QPointF(7, 4), QPointF(7, 16))
        elif key == "logs":
            painter.drawRoundedRect(QRectF(4, 2.5, 12, 15), 2, 2)
            for y in (7, 10.5, 14):
                painter.drawLine(QPointF(7, y), QPointF(13, y))
        elif key == "backtest":
            painter.drawArc(QRectF(3, 3, 14, 14), 40 * 16, 285 * 16)
            painter.drawLine(QPointF(3.6, 5.5), QPointF(3.4, 2.5))
            painter.drawLine(QPointF(3.4, 2.5), QPointF(6.3, 3.4))
            painter.drawLine(QPointF(10, 6), QPointF(10, 10))
            painter.drawLine(QPointF(10, 10), QPointF(13, 12))
        elif key == "help":
            painter.drawEllipse(QRectF(3, 3, 14, 14))
            path = QPainterPath(QPointF(7.2, 7.4))
            path.cubicTo(7.5, 5.4, 11.9, 5.2, 12.5, 7.5)
            path.cubicTo(13, 9.4, 10.1, 9.7, 10.1, 12)
            painter.drawPath(path)
            painter.drawPoint(QPointF(10.1, 14.5))
        else:
            for y, knob in ((5, 7), (10, 13), (15, 9)):
                painter.drawLine(QPointF(3, y), QPointF(17, y))
                painter.drawEllipse(QPointF(knob, y), 1.8, 1.8)
        painter.end()
        return QIcon(pixmap)
