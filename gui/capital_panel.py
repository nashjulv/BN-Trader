"""
资金概览卡片 — 主界面左侧紧凑卡片
"""

from typing import Dict, List

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QFrame, QPushButton, QGridLayout)
from PyQt6.QtCore import Qt

from gui.styles import Theme


class CapitalPanel(QWidget):
    """资金概览 — 卡片式"""

    def __init__(self, compact: bool = True):
        super().__init__()
        self.compact = compact
        self._init_ui()
        self._refresh_theme()

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        self._card = QFrame()
        self._card.setObjectName("cardFrame")
        layout = QVBoxLayout(self._card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        # 标题
        hdr = QHBoxLayout()
        self._title = QLabel("资金概览")
        self._title.setObjectName("sectionTitle")
        hdr.addWidget(self._title)
        hdr.addStretch()
        self._sync_btn = QPushButton("同步")
        self._sync_btn.setObjectName("textBtn")
        self._sync_btn.setFixedHeight(24)
        self._sync_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        hdr.addWidget(self._sync_btn)
        layout.addLayout(hdr)

        # 总资产
        self.total_value_label = QLabel("10,000.00 USDT")
        self.total_value_label.setObjectName("valueLabel")
        layout.addWidget(self.total_value_label)

        # 四格明细
        grid = QGridLayout()
        grid.setSpacing(8)
        self.available_label = QLabel("0.00")
        self.locked_label = QLabel("0.00")
        self.margin_label = QLabel("0.00")
        self.reserve_label = QLabel("0.00")

        items = [
            ("可用资金", self.available_label, 0, 0),
            ("冻结资金", self.locked_label, 0, 1),
            ("持仓保证金", self.margin_label, 1, 0),
            ("风险准备金", self.reserve_label, 1, 1),
        ]
        self._cap_labels = []
        for name, val_lbl, r, c in items:
            cell = QVBoxLayout()
            cell.setSpacing(2)
            cap = QLabel(name)
            cap.setObjectName("dimLabel")
            val_lbl.setStyleSheet("font-size:13px; font-weight:600;")
            cell.addWidget(cap)
            cell.addWidget(val_lbl)
            grid.addLayout(cell, r, c)
            self._cap_labels.append(cap)
        layout.addLayout(grid)

        # 非紧凑：余额表
        if not self.compact:
            from PyQt6.QtWidgets import QTableWidget, QHeaderView
            self.balance_table = QTableWidget()
            self.balance_table.setColumnCount(3)
            self.balance_table.setHorizontalHeaderLabels(["币种", "可用", "冻结"])
            self.balance_table.horizontalHeader().setSectionResizeMode(
                QHeaderView.ResizeMode.Stretch)
            self.balance_table.setEditTriggers(
                QTableWidget.EditTrigger.NoEditTriggers)
            self.balance_table.verticalHeader().setVisible(False)
            self.balance_table.setMaximumHeight(140)
            layout.addWidget(self.balance_table)
        else:
            self.balance_table = None

        root.addWidget(self._card)

    def _refresh_theme(self):
        t = Theme.colors()
        self._card.setStyleSheet(Theme.card_style())
        self.total_value_label.setStyleSheet(
            f"font-size:22px; font-weight:700; color:{t['text_primary']};")
        self._sync_btn.setStyleSheet(
            f"color:{t['accent']}; background:transparent; border:none; "
            f"font-size:12px; font-weight:600;")

    def update_balances(self, balances: List[Dict], total_usdt: float):
        if total_usdt > 0:
            self.total_value_label.setText(f"{total_usdt:,.2f} USDT")
        if self.balance_table is not None:
            self.balance_table.setRowCount(len(balances))
            from PyQt6.QtWidgets import QTableWidgetItem
            for i, b in enumerate(balances):
                self.balance_table.setItem(i, 0, QTableWidgetItem(b["asset"]))
                self.balance_table.setItem(i, 1, QTableWidgetItem(f"{b['free']:.4f}"))
                self.balance_table.setItem(i, 2, QTableWidgetItem(f"{b['locked']:.4f}"))

    def update_status(self, status: Dict):
        t = Theme.colors()
        total = status.get("total", 0)
        if total > 0:
            self.total_value_label.setText(f"{total:,.2f} USDT")
        self.available_label.setText(f"{status.get('available', 0):,.2f}")
        self.locked_label.setText(f"{status.get('locked', 0):,.2f}")
        self.margin_label.setText(f"{status.get('margin', 0):,.2f}")
        reserve = status.get("reserve", total * 0.2)
        self.reserve_label.setText(f"{reserve:,.2f}")
        for lbl in [self.available_label, self.locked_label,
                     self.margin_label, self.reserve_label]:
            lbl.setStyleSheet(
                f"font-size:13px; font-weight:600; color:{t['text_primary']};")
