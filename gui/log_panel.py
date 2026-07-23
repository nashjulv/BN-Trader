"""
交易日志面板 — 主界面迷你版 + 详情页表格版
"""

from datetime import datetime
from typing import List, Dict

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QTextEdit, QPushButton, QFrame,
                               QTableWidget, QTableWidgetItem, QHeaderView,
                               QAbstractItemView)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from gui.styles import Theme


CATEGORIES = ["全部", "交易", "风控", "系统"]

LEVEL_MAP = {
    "INFO": "成功",
    "SUCCESS": "成功",
    "WARNING": "警告",
    "CRITICAL": "失败",
    "ERROR": "失败",
}


class LogPanel(QWidget):
    """主界面下方迷你日志"""

    def __init__(self, detail_mode: bool = False):
        super().__init__()
        self.detail_mode = detail_mode
        self.log_entries: List[Dict] = []
        self._active_filter = "全部"
        self._filter_btns: Dict[str, QPushButton] = {}
        self._page = 0
        self._page_size = 20
        self._init_ui()
        self._refresh_theme()

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        self._card = QFrame()
        self._card.setObjectName("cardFrame")
        layout = QVBoxLayout(self._card)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(6)

        # 标题栏
        header = QHBoxLayout()
        title = QLabel("交易日志" if not self.detail_mode else "日志详情")
        title.setObjectName("sectionTitle")
        header.addWidget(title)
        header.addSpacing(12)

        for cat in CATEGORIES:
            btn = QPushButton(cat)
            btn.setCheckable(True)
            btn.setChecked(cat == "全部")
            btn.setFixedHeight(24)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, c=cat: self._set_filter(c))
            self._filter_btns[cat] = btn
            header.addWidget(btn)

        header.addStretch()
        self.clear_btn = QPushButton("清空日志")
        self.clear_btn.setObjectName("ghostBtn")
        self.clear_btn.setFixedHeight(24)
        self.clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_btn.clicked.connect(self._clear_logs)
        header.addWidget(self.clear_btn)
        layout.addLayout(header)

        if self.detail_mode:
            self.table = QTableWidget()
            self.table.setColumnCount(4)
            self.table.setHorizontalHeaderLabels(["时间", "类型", "状态", "内容"])
            self.table.horizontalHeader().setSectionResizeMode(
                0, QHeaderView.ResizeMode.ResizeToContents)
            self.table.horizontalHeader().setSectionResizeMode(
                1, QHeaderView.ResizeMode.ResizeToContents)
            self.table.horizontalHeader().setSectionResizeMode(
                2, QHeaderView.ResizeMode.ResizeToContents)
            self.table.horizontalHeader().setSectionResizeMode(
                3, QHeaderView.ResizeMode.Stretch)
            self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            self.table.setSelectionBehavior(
                QAbstractItemView.SelectionBehavior.SelectRows)
            self.table.verticalHeader().setVisible(False)
            self.table.setAlternatingRowColors(True)
            layout.addWidget(self.table)

            # 分页
            page_row = QHBoxLayout()
            page_row.addStretch()
            self._page_info = QLabel("共 0 条")
            self._page_info.setObjectName("dimLabel")
            page_row.addWidget(self._page_info)
            self._prev_btn = QPushButton("上一页")
            self._prev_btn.setFixedHeight(28)
            self._prev_btn.clicked.connect(self._prev_page)
            self._next_btn = QPushButton("下一页")
            self._next_btn.setFixedHeight(28)
            self._next_btn.clicked.connect(self._next_page)
            page_row.addWidget(self._prev_btn)
            page_row.addWidget(self._next_btn)
            layout.addLayout(page_row)

            self.log_text = None
        else:
            self.log_text = QTextEdit()
            self.log_text.setReadOnly(True)
            self.log_text.setMaximumHeight(180)
            layout.addWidget(self.log_text)
            self.table = None

        root.addWidget(self._card)

    def _set_filter(self, category: str):
        self._active_filter = category
        self._page = 0
        for cat, btn in self._filter_btns.items():
            btn.setChecked(cat == category)
        self._refresh_filter_btns()
        self._refresh_display()

    def active_filter(self) -> str:
        return self._active_filter

    def add_log(self, message: str, level: str = "INFO", category: str = "系统"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        full_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.log_entries.append({
            "time": timestamp,
            "full_time": full_time,
            "message": message,
            "level": level,
            "category": category,
        })
        if len(self.log_entries) > 1000:
            self.log_entries = self.log_entries[-1000:]
        self._refresh_display()

    def add_trade_log(self, message: str, level: str = "INFO"):
        self.add_log(message, level, "交易")

    def add_risk_log(self, message: str, level: str = "WARNING"):
        self.add_log(message, level, "风控")

    def add_system_log(self, message: str, level: str = "INFO"):
        self.add_log(message, level, "系统")

    def _filtered(self) -> List[Dict]:
        if self._active_filter == "全部":
            return self.log_entries
        return [e for e in self.log_entries if e["category"] == self._active_filter]

    def _refresh_display(self):
        entries = self._filtered()
        if self.detail_mode and self.table is not None:
            self._refresh_table(entries)
        elif self.log_text is not None:
            self._refresh_text(entries)

    def _refresh_text(self, entries: List[Dict]):
        t = Theme.colors()
        lines = []
        for entry in entries[-80:]:
            color = {
                "INFO": t["text_primary"],
                "WARNING": t["warning"],
                "CRITICAL": t["danger"],
                "ERROR": t["danger"],
                "SUCCESS": t["success"],
            }.get(entry["level"], t["text_primary"])
            tag_c = {
                "交易": t["tag_trade"],
                "风控": t["tag_risk"],
                "系统": t["tag_system"],
            }.get(entry["category"], t["text_secondary"])
            lines.append(
                f'<span style="color:{t["text_dim"]}">[{entry["time"]}]</span> '
                f'<span style="color:{tag_c};font-weight:600">[{entry["category"]}]</span> '
                f'<span style="color:{color}">{entry["message"]}</span>'
            )
        self.log_text.setHtml("<br>".join(lines))
        sb = self.log_text.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _refresh_table(self, entries: List[Dict]):
        t = Theme.colors()
        total = len(entries)
        start = self._page * self._page_size
        page_entries = list(reversed(entries))[start:start + self._page_size]
        self.table.setRowCount(len(page_entries))

        for i, entry in enumerate(page_entries):
            self.table.setItem(i, 0, QTableWidgetItem(entry.get("full_time", entry["time"])))

            cat_item = QTableWidgetItem(entry["category"])
            tag_c = {
                "交易": t["tag_trade"], "风控": t["tag_risk"], "系统": t["tag_system"],
            }.get(entry["category"], t["text_secondary"])
            cat_item.setForeground(QColor(tag_c))
            self.table.setItem(i, 1, cat_item)

            status = LEVEL_MAP.get(entry["level"], entry["level"])
            status_item = QTableWidgetItem(status)
            sc = {
                "成功": t["success"], "警告": t["warning"], "失败": t["danger"],
            }.get(status, t["text_secondary"])
            status_item.setForeground(QColor(sc))
            self.table.setItem(i, 2, status_item)

            self.table.setItem(i, 3, QTableWidgetItem(entry["message"]))

        if self._page_info:
            pages = max(1, (total + self._page_size - 1) // self._page_size)
            self._page_info.setText(
                f"共 {total} 条 · 第 {self._page + 1}/{pages} 页")

    def _prev_page(self):
        if self._page > 0:
            self._page -= 1
            self._refresh_display()

    def _next_page(self):
        entries = self._filtered()
        max_page = max(0, (len(entries) - 1) // self._page_size)
        if self._page < max_page:
            self._page += 1
            self._refresh_display()

    def _clear_logs(self):
        self.log_entries.clear()
        self._page = 0
        if self.log_text:
            self.log_text.clear()
        if self.table:
            self.table.setRowCount(0)
        self.add_system_log("日志已清空")

    def get_logs(self) -> List[Dict]:
        return self.log_entries

    def sync_from(self, other: "LogPanel"):
        """从另一个 LogPanel 同步条目（详情页用）"""
        self.log_entries = list(other.log_entries)
        self._refresh_display()

    def _refresh_theme(self):
        t = Theme.colors()
        self._card.setStyleSheet(Theme.card_style())
        if self.log_text:
            self.log_text.setStyleSheet(
                f"background:{t['bg_main']}; color:{t['text_primary']}; "
                f"border:1px solid {t['border']}; border-radius:4px; "
                f"font-family:'SF Mono','Consolas',monospace; font-size:12px;")
        self._refresh_filter_btns()

    def _refresh_filter_btns(self):
        t = Theme.colors()
        for cat, btn in self._filter_btns.items():
            if cat == self._active_filter:
                btn.setStyleSheet(
                    f"color:{t['accent']}; font-size:12px; font-weight:600; "
                    f"border:none; border-bottom:2px solid {t['accent']}; "
                    f"border-radius:0; padding:2px 10px; background:transparent;")
            else:
                btn.setStyleSheet(
                    f"color:{t['text_secondary']}; font-size:12px; "
                    f"border:none; border-bottom:2px solid transparent; "
                    f"border-radius:0; padding:2px 10px; background:transparent;")
