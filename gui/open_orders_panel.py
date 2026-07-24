"""主界面右侧的币安现货挂单记录。"""

from typing import Dict, List

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

from gui.styles import Theme


class OpenOrdersPanel(QWidget):
    refresh_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.orders: List[Dict] = []
        self._build_ui()
        self._refresh_theme()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        self._card = QFrame()
        self._card.setObjectName("cardFrame")
        layout = QVBoxLayout(self._card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(7)

        header = QHBoxLayout()
        self._title = QLabel("挂单记录")
        self._title.setObjectName("sectionTitle")
        header.addWidget(self._title)
        self._count = QLabel("0")
        self._count.setObjectName("dimLabel")
        header.addWidget(self._count)
        header.addStretch()
        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.setObjectName("ghostBtn")
        self.refresh_btn.setFixedHeight(26)
        self.refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_btn.setAccessibleName("刷新挂单记录")
        self.refresh_btn.clicked.connect(self.refresh_requested)
        header.addWidget(self.refresh_btn)
        layout.addLayout(header)

        self._list = QVBoxLayout()
        self._list.setSpacing(6)
        layout.addLayout(self._list)

        self._empty = QLabel("暂无挂单")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.setObjectName("dimLabel")
        self._empty.setMinimumHeight(42)
        layout.addWidget(self._empty)
        root.addWidget(self._card)

    def set_loading(self, loading: bool):
        self.refresh_btn.setEnabled(not loading)
        self.refresh_btn.setText("同步中…" if loading else "刷新")

    def update_orders(self, orders: List[Dict]):
        self.orders = list(orders or [])
        while self._list.count():
            item = self._list.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        open_count = sum(
            order.get("status") in ("NEW", "PARTIALLY_FILLED")
            for order in self.orders
        )
        self._count.setText(f"{open_count} 挂单 · {len(self.orders)} 最近")
        self._empty.setVisible(not self.orders)
        t = Theme.colors()
        for order in self.orders[:5]:
            self._list.addWidget(self._make_row(order, t))

    def _make_row(self, order: Dict, t: dict) -> QFrame:
        row = QFrame()
        row.setStyleSheet(
            f"QFrame {{ background:{t['bg_main']}; border:none; "
            "border-radius:6px; }"
        )
        layout = QHBoxLayout(row)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(7)

        left = QVBoxLayout()
        left.setSpacing(1)
        symbol = QLabel(str(order.get("symbol", "")))
        symbol.setStyleSheet(
            f"font-size:12px; font-weight:600; color:{t['text_primary']};"
        )
        side = str(order.get("side", "BUY")).upper()
        side_label = QLabel("买入" if side == "BUY" else "卖出")
        side_label.setStyleSheet(
            f"font-size:11px; color:{t['buy'] if side == 'BUY' else t['sell']};"
        )
        left.addWidget(symbol)
        left.addWidget(side_label)
        layout.addLayout(left)
        layout.addStretch()

        right = QVBoxLayout()
        right.setSpacing(1)
        quantity = float(order.get("quantity", 0) or 0)
        price = float(order.get("price", 0) or 0)
        value = QLabel(f"{quantity:g} @ {price:,.2f}")
        value.setAlignment(Qt.AlignmentFlag.AlignRight)
        value.setStyleSheet(
            f"font-size:11px; color:{t['text_primary']};"
            "font-family:'SF Mono','Consolas',monospace;"
        )
        raw_status = str(order.get("status", "NEW"))
        status_text = {
            "NEW": "等待成交",
            "PARTIALLY_FILLED": "部分成交",
            "FILLED": "已成交",
            "CANCELED": "已撤销",
            "EXPIRED": "已失效",
            "REJECTED": "已拒绝",
        }.get(raw_status, raw_status)
        status = QLabel(status_text)
        status.setAlignment(Qt.AlignmentFlag.AlignRight)
        status_color = (
            t["warning"]
            if raw_status in ("NEW", "PARTIALLY_FILLED")
            else t["success"]
            if raw_status == "FILLED"
            else t["text_secondary"]
        )
        status.setStyleSheet(
            f"font-size:10px; color:{status_color}; font-weight:600;"
        )
        right.addWidget(value)
        right.addWidget(status)
        layout.addLayout(right)
        return row

    def _refresh_theme(self):
        self._card.setStyleSheet(Theme.card_style())
        self.update_orders(self.orders)
