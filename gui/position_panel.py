"""
当前持仓卡片 — 主界面左侧紧凑列表
"""

from typing import Dict, List

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QFrame, QPushButton, QScrollArea)
from PyQt6.QtCore import Qt, pyqtSignal

from gui.styles import Theme


class PositionPanel(QWidget):
    close_requested = pyqtSignal(str)  # symbol

    def __init__(self, compact: bool = True):
        super().__init__()
        self.compact = compact
        self.positions: List[Dict] = []
        self._init_ui()
        self._refresh_theme()

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        self._card = QFrame()
        self._card.setObjectName("cardFrame")
        layout = QVBoxLayout(self._card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        hdr = QHBoxLayout()
        self._title = QLabel("当前持仓")
        self._title.setObjectName("sectionTitle")
        hdr.addWidget(self._title)
        hdr.addStretch()
        self.total_pnl_label = QLabel("总盈亏: 0.00")
        hdr.addWidget(self.total_pnl_label)
        layout.addLayout(hdr)

        self._list = QVBoxLayout()
        self._list.setSpacing(6)
        layout.addLayout(self._list)

        self._empty = QLabel("暂无持仓")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.setObjectName("dimLabel")
        layout.addWidget(self._empty)

        if not self.compact:
            self._close_btn = QPushButton("平仓选中")
            self._close_btn.setObjectName("dangerBtn")
            layout.addWidget(self._close_btn)
        else:
            self._close_btn = None

        root.addWidget(self._card)

    def _refresh_theme(self):
        t = Theme.colors()
        self._card.setStyleSheet(Theme.card_style())
        self.total_pnl_label.setStyleSheet(
            f"font-size:12px; font-weight:600; color:{t['text_secondary']};")

    def update_positions(self, positions: List[Dict]):
        self.positions = positions or []
        # 清空列表
        while self._list.count():
            item = self._list.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        t = Theme.colors()
        total_pnl = 0.0
        self._empty.setVisible(len(self.positions) == 0)

        for pos in self.positions:
            pnl = pos.get("pnl", 0)
            total_pnl += pnl
            row = self._make_row(pos, t)
            self._list.addWidget(row)

        c = t["success"] if total_pnl >= 0 else t["danger"]
        self.total_pnl_label.setText(f"总盈亏: {total_pnl:+.2f}")
        self.total_pnl_label.setStyleSheet(f"font-size:12px; font-weight:600; color:{c};")

    def _make_row(self, pos: Dict, t: dict) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(
            f"background:{t['bg_main']}; border-radius:6px; border:none;")
        lay = QHBoxLayout(frame)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(8)

        # 左：交易对 + 方向
        left = QVBoxLayout()
        left.setSpacing(2)
        sym = QLabel(pos.get("symbol", ""))
        sym.setStyleSheet(f"font-size:13px; font-weight:700; color:{t['text_primary']};")
        side = pos.get("side", "BUY")
        side_c = t["buy"] if side == "BUY" else t["sell"]
        side_lbl = QLabel("多" if side == "BUY" else "空")
        side_lbl.setStyleSheet(
            f"font-size:11px; font-weight:600; color:{side_c};")
        left.addWidget(sym)
        left.addWidget(side_lbl)
        lay.addLayout(left)

        lay.addStretch()

        # 中：数量 / 入场价
        mid = QVBoxLayout()
        mid.setSpacing(2)
        qty = QLabel(f"{pos.get('quantity', 0):.4f}")
        qty.setStyleSheet(f"font-size:12px; color:{t['text_primary']};")
        qty.setAlignment(Qt.AlignmentFlag.AlignRight)
        entry = QLabel(f"@{pos.get('entry_price', 0):,.2f}")
        entry.setStyleSheet(f"font-size:11px; color:{t['text_secondary']};")
        entry.setAlignment(Qt.AlignmentFlag.AlignRight)
        mid.addWidget(qty)
        mid.addWidget(entry)
        lay.addLayout(mid)

        # 右：盈亏
        pnl = pos.get("pnl", 0)
        pnl_ratio = pos.get("pnl_ratio", 0)
        pnl_c = t["success"] if pnl >= 0 else t["danger"]
        right = QVBoxLayout()
        right.setSpacing(2)
        pnl_lbl = QLabel(f"{pnl:+.2f}")
        pnl_lbl.setStyleSheet(f"font-size:13px; font-weight:700; color:{pnl_c};")
        pnl_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        ratio_lbl = QLabel(f"{pnl_ratio:+.2%}")
        ratio_lbl.setStyleSheet(f"font-size:11px; color:{pnl_c};")
        ratio_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        right.addWidget(pnl_lbl)
        right.addWidget(ratio_lbl)
        lay.addLayout(right)

        return frame
