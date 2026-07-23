"""
行情场景卡片 — 主界面左侧紧凑卡片
"""

from typing import Dict

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QFrame, QProgressBar)
from PyQt6.QtCore import Qt

from gui.styles import Theme, SCENE_COLORS, SCENE_INFO


class ScenePanel(QWidget):

    def __init__(self, compact: bool = True):
        super().__init__()
        self.compact = compact
        self.current_scene = "RANGING"
        self._init_ui()
        self._refresh_theme()

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._card = QFrame()
        self._card.setObjectName("cardFrame")
        layout = QVBoxLayout(self._card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        # 标题行
        hdr = QHBoxLayout()
        self._title = QLabel("当前行情场景")
        self._title.setObjectName("sectionTitle")
        hdr.addWidget(self._title)
        hdr.addStretch()
        layout.addLayout(hdr)

        # 场景名称 + 置信度
        row = QHBoxLayout()
        self.scene_name_label = QLabel("--")
        self.scene_name_label.setStyleSheet("font-size:16px; font-weight:700;")
        row.addWidget(self.scene_name_label)
        row.addStretch()
        self.confidence_label = QLabel("--")
        self.confidence_label.setStyleSheet("font-size:18px; font-weight:700;")
        row.addWidget(self.confidence_label)
        layout.addLayout(row)

        self.confidence_bar = QProgressBar()
        self.confidence_bar.setMaximum(100)
        self.confidence_bar.setTextVisible(False)
        self.confidence_bar.setFixedHeight(6)
        layout.addWidget(self.confidence_bar)

        self.action_label = QLabel("建议: --")
        self.action_label.setObjectName("captionLabel")
        self.action_label.setWordWrap(True)
        layout.addWidget(self.action_label)

        # 场景快捷切换
        btn_row = QHBoxLayout()
        btn_row.setSpacing(4)
        self.scene_buttons = {}
        for st, info in SCENE_INFO.items():
            btn = QPushButton(info["name"][:2])
            btn.setCheckable(True)
            btn.setFixedHeight(26)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(info["name"])
            btn.clicked.connect(lambda _, s=st: self._on_scene_clicked(s))
            self.scene_buttons[st] = btn
            btn_row.addWidget(btn)
        layout.addLayout(btn_row)

        # 详情（非紧凑模式）
        if not self.compact:
            self.trend_label = QLabel("趋势: --")
            self.volatility_label = QLabel("波动率: --")
            self.volume_label = QLabel("成交量: --")
            for lbl in [self.trend_label, self.volatility_label, self.volume_label]:
                lbl.setObjectName("captionLabel")
                layout.addWidget(lbl)
        else:
            self.trend_label = self.volatility_label = self.volume_label = None

        root.addWidget(self._card)

    def _refresh_theme(self):
        t = Theme.colors()
        self._card.setStyleSheet(Theme.card_style())
        color = SCENE_COLORS.get(self.current_scene, t["accent"])
        self.scene_name_label.setStyleSheet(
            f"font-size:16px; font-weight:700; color:{color};")
        self.confidence_label.setStyleSheet(
            f"font-size:18px; font-weight:700; color:{color};")
        self.confidence_bar.setStyleSheet(
            f"QProgressBar {{ background:{t['progress_bg']}; border:none; "
            f"border-radius:3px; }} "
            f"QProgressBar::chunk {{ background:{color}; border-radius:3px; }}")
        for st, btn in self.scene_buttons.items():
            c = SCENE_COLORS.get(st, "#888")
            active = st == self.current_scene
            if active:
                btn.setStyleSheet(
                    f"background:{c}; color:#fff; border:none; "
                    f"border-radius:4px; font-size:11px; font-weight:600; padding:2px 6px;")
            else:
                btn.setStyleSheet(
                    f"background:transparent; color:{t['text_secondary']}; "
                    f"border:1px solid {t['border']}; border-radius:4px; "
                    f"font-size:11px; padding:2px 6px;")

    def update_scene(self, scene_data: Dict):
        if not scene_data:
            return
        self.current_scene = scene_data.get("type", "RANGING")
        info = SCENE_INFO.get(self.current_scene, SCENE_INFO["RANGING"])
        conf = scene_data.get("confidence", 0)
        self.scene_name_label.setText(f"{info['icon']} {info['name']}")
        self.confidence_label.setText(f"{conf:.0%}")
        self.confidence_bar.setValue(int(conf * 100))
        self.action_label.setText(f"建议: {info['tip']}")
        if self.trend_label:
            self.trend_label.setText(f"趋势: {scene_data.get('trend_strength', 0):.2f}")
            self.volatility_label.setText(f"波动率: {scene_data.get('volatility', 0):.2f}")
            self.volume_label.setText(f"成交量变化: {scene_data.get('volume_change', 0):.2%}")
        self._refresh_theme()

    def _on_scene_clicked(self, st: str):
        info = SCENE_INFO.get(st, {})
        self.current_scene = st
        self.scene_name_label.setText(f"{info.get('icon','')} {info.get('name','')}")
        self.action_label.setText(f"手动: {info.get('tip', '')}")
        self._refresh_theme()
