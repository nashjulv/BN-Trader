"""
交易对观察列表 — 紧凑专业风格
"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView, QLabel)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from gui.styles import Theme


class WatchlistWidget(QWidget):

    symbol_clicked = None  # 预留

    def __init__(self):
        super().__init__()
        self._init_ui()
        self._refresh_theme()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["交易对", "最新价", "涨跌"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)

    def _refresh_theme(self):
        t = Theme.colors()
        self.table.setStyleSheet(
            f"QTableWidget {{ background-color:{t['bg_main']}; border:none; font-size:11px; "
            f"color:{t['text_primary']}; alternate-background-color:{t['bg_card']}; }}"
            f"QTableWidget::item {{ padding:2px 6px; border:none; }}"
            f"QHeaderView::section {{ background:{t['bg_main']}; color:{t['text_dim']}; "
            f"border:none; border-bottom:1px solid {t['border']}; "
            f"padding:2px 6px; font-size:10px; font-weight:bold; }}"
            f"QTableWidget::item:selected {{ background:{t['bg_hover']}; }}"
        )

    def update_data(self, pairs: list):
        """pairs: [{"symbol":"BTCUSDT","price":68400,"change":2.35}, ...]"""
        self.table.setRowCount(len(pairs))
        t = Theme.colors()
        for i, p in enumerate(pairs):
            sym = QTableWidgetItem(p["symbol"].replace("USDT","/USDT"))
            self.table.setItem(i, 0, sym)
            price = QTableWidgetItem(f"{p['price']:,.2f}")
            self.table.setItem(i, 1, price)
            chg = p.get("change", 0)
            chg_item = QTableWidgetItem(f"{chg:+.2f}%")
            chg_item.setForeground(QColor(t["success"] if chg >= 0 else t["danger"]))
            self.table.setItem(i, 2, chg_item)
