"""
左侧图标导航栏 — 匹配 UI 设计稿
主页 / 策略 / 资金 / 风控 / 持仓 / 日志 / 回测 / 设置
"""

from typing import Dict, List, Tuple

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QToolButton, QLabel, QFrame, QApplication, QStyle
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QIcon, QPainter

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
    ("settings",  "⚙",  "API / 设置"),
]

NAV_LABELS = {
    "dashboard": "行情", "strategy": "策略", "capital": "资金",
    "risk": "风控", "position": "持仓", "logs": "日志",
    "backtest": "复盘", "settings": "设置",
}

NAV_ICONS = {
    "dashboard": QStyle.StandardPixmap.SP_ComputerIcon,
    "strategy": QStyle.StandardPixmap.SP_FileDialogDetailedView,
    "capital": QStyle.StandardPixmap.SP_DriveHDIcon,
    "risk": QStyle.StandardPixmap.SP_MessageBoxWarning,
    "position": QStyle.StandardPixmap.SP_DirHomeIcon,
    "logs": QStyle.StandardPixmap.SP_FileDialogListView,
    "backtest": QStyle.StandardPixmap.SP_BrowserReload,
    "settings": QStyle.StandardPixmap.SP_FileDialogContentsView,
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
            btn.setIcon(QApplication.style().standardIcon(NAV_ICONS[key]))
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
            btn.setIcon(self._tinted_icon(
                NAV_ICONS[key], t["accent"] if active else t["text_sidebar_dim"]))
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
    def _tinted_icon(icon_type, color: str) -> QIcon:
        pixmap = QApplication.style().standardIcon(icon_type).pixmap(16, 16)
        painter = QPainter(pixmap)
        painter.setCompositionMode(
            QPainter.CompositionMode.CompositionMode_SourceIn)
        painter.fillRect(pixmap.rect(), QColor(color))
        painter.end()
        return QIcon(pixmap)
