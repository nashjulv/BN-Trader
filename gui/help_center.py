"""应用内可搜索帮助中心。"""

import html
import json
import sys
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from config import Config
from gui.styles import Theme


def _content_path() -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
    return base / "docs" / "help_content.json"


def load_help_content() -> dict:
    return json.loads(_content_path().read_text(encoding="utf-8"))


class HelpCenterPage(QWidget):
    """内容优先、支持键盘与即时搜索的帮助页面。"""

    def __init__(self):
        super().__init__()
        self._data = load_help_content()
        self._chapters = self._data["chapters"]
        self._build_ui()
        self._populate_navigation()
        self._refresh_theme()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 24)
        root.setSpacing(16)

        header = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(3)
        title = QLabel("帮助中心")
        title.setObjectName("helpTitle")
        subtitle = QLabel(f"BN-Trader v{Config.APP_VERSION} · 使用指南与问题排查")
        subtitle.setObjectName("captionLabel")
        titles.addWidget(title)
        titles.addWidget(subtitle)
        header.addLayout(titles)
        header.addStretch()

        self.search = QLineEdit()
        self.search.setPlaceholderText("搜索功能、设置或问题…")
        self.search.setClearButtonEnabled(True)
        self.search.setAccessibleName("搜索帮助内容")
        self.search.setFixedWidth(320)
        self.search.setMinimumHeight(36)
        self.search.textChanged.connect(self._on_search)
        header.addWidget(self.search)
        root.addLayout(header)

        content = QFrame()
        content.setObjectName("helpSurface")
        body = QHBoxLayout(content)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        self.navigation = QListWidget()
        self.navigation.setObjectName("helpNavigation")
        self.navigation.setFixedWidth(220)
        self.navigation.setSpacing(2)
        self.navigation.setAccessibleName("帮助章节")
        self.navigation.currentRowChanged.connect(self._show_chapter)
        body.addWidget(self.navigation)

        self.reader = QTextBrowser()
        self.reader.setObjectName("helpReader")
        self.reader.setOpenExternalLinks(True)
        self.reader.setAccessibleName("帮助正文")
        body.addWidget(self.reader, 1)
        root.addWidget(content, 1)

    def _populate_navigation(self, chapters=None):
        chapters = chapters or self._chapters
        self.navigation.blockSignals(True)
        self.navigation.clear()
        for chapter in chapters:
            item = QListWidgetItem(chapter["title"])
            item.setData(Qt.ItemDataRole.UserRole, chapter["id"])
            item.setToolTip(chapter["summary"])
            self.navigation.addItem(item)
        self.navigation.blockSignals(False)
        if self.navigation.count():
            self.navigation.setCurrentRow(0)
            self._show_chapter(0)

    def _chapter_by_id(self, chapter_id: str):
        return next((c for c in self._chapters if c["id"] == chapter_id), None)

    def _show_chapter(self, row: int):
        item = self.navigation.item(row)
        if not item:
            return
        chapter = self._chapter_by_id(item.data(Qt.ItemDataRole.UserRole))
        if chapter:
            self.reader.setHtml(self._chapter_html(chapter))

    def _on_search(self, text: str):
        query = text.strip().casefold()
        if not query:
            self._populate_navigation()
            return
        matches = [
            chapter for chapter in self._chapters
            if query in json.dumps(chapter, ensure_ascii=False).casefold()
        ]
        self.navigation.blockSignals(True)
        self.navigation.clear()
        for chapter in matches:
            item = QListWidgetItem(chapter["title"])
            item.setData(Qt.ItemDataRole.UserRole, chapter["id"])
            self.navigation.addItem(item)
        self.navigation.blockSignals(False)
        if matches:
            self.navigation.setCurrentRow(0)
            self.reader.setHtml(
                self._search_html(query, matches)
            )
        else:
            self.reader.setHtml(self._empty_html(text))

    def _chapter_html(self, chapter: dict) -> str:
        parts = [
            f"<h1>{html.escape(chapter['title'])}</h1>",
            f"<p class='lead'>{html.escape(chapter['summary'])}</p>",
        ]
        for section in chapter["sections"]:
            parts.append(f"<h2>{html.escape(section['title'])}</h2>")
            if section.get("body"):
                parts.append(f"<p>{html.escape(section['body'])}</p>")
            if section.get("items"):
                parts.append("<ul>")
                parts.extend(f"<li>{html.escape(item)}</li>" for item in section["items"])
                parts.append("</ul>")
            if section.get("steps"):
                parts.append("<ol>")
                parts.extend(f"<li>{html.escape(step)}</li>" for step in section["steps"])
                parts.append("</ol>")
            if section.get("note"):
                parts.append(
                    f"<div class='note'><b>安全提示</b><br>{html.escape(section['note'])}</div>"
                )
        return self._document("".join(parts))

    def _search_html(self, query: str, chapters: list) -> str:
        parts = [
            f"<h1>搜索结果</h1><p class='lead'>找到 {len(chapters)} 个相关章节</p>"
        ]
        for chapter in chapters:
            parts.append(
                f"<h2>{html.escape(chapter['title'])}</h2>"
                f"<p>{html.escape(chapter['summary'])}</p>"
            )
        return self._document("".join(parts))

    def _empty_html(self, query: str) -> str:
        return self._document(
            "<h1>没有找到结果</h1>"
            f"<p class='lead'>未找到与“{html.escape(query)}”相关的帮助内容。</p>"
            "<p>可以尝试搜索：API、风控、下单、暗色主题或日志。</p>"
        )

    def _document(self, body: str) -> str:
        t = Theme.colors()
        return f"""
        <html><head><style>
        body {{ color:{t['text_primary']}; font-family:'SF Pro Text','PingFang SC',
               'Microsoft YaHei UI',sans-serif; font-size:14px; line-height:1.7;
               margin:28px 36px; max-width:780px; }}
        h1 {{ font-size:26px; font-weight:650; margin:0 0 8px; }}
        h2 {{ font-size:17px; font-weight:600; margin:26px 0 8px; }}
        p {{ margin:7px 0; }} .lead {{ color:{t['text_secondary']}; font-size:15px; }}
        li {{ margin:7px 0; }} ul,ol {{ margin:8px 0 8px 20px; padding-left:12px; }}
        .note {{ background:{t['accent_light']}; color:{t['text_primary']};
                 border-radius:10px; padding:13px 15px; margin-top:16px; }}
        </style></head><body>{body}</body></html>
        """

    def _refresh_theme(self):
        t = Theme.colors()
        self.setStyleSheet(f"""
            QWidget {{ background:{t['bg_main']}; }}
            QLabel#helpTitle {{
                color:{t['text_primary']}; font-size:24px; font-weight:650;
            }}
            QLabel#captionLabel {{
                color:{t['text_secondary']}; background:transparent;
            }}
            QLineEdit {{
                background:{t['bg_input']}; color:{t['text_primary']};
                border:1px solid {t['border']}; border-radius:8px;
                padding:0 12px; selection-background-color:{t['accent']};
            }}
            QLineEdit:hover {{
                background:{t['bg_hover']}; border-color:{t['hover_border']};
            }}
            QLineEdit:focus {{ border-color:{t['border_focus']}; }}
            QFrame#helpSurface {{
                background:{t['bg_card']}; border:1px solid {t['border']};
                border-radius:12px;
            }}
            QListWidget#helpNavigation {{
                background:{t['bg_surface']}; color:{t['text_secondary']};
                border:none; border-right:1px solid {t['divider']};
                padding:12px 8px; outline:none; font-size:13px;
            }}
            QListWidget#helpNavigation::item {{
                border-radius:8px; min-height:38px; padding:0 12px;
            }}
            QListWidget#helpNavigation::item:hover {{
                background:{t['bg_hover']}; color:{t['text_primary']};
            }}
            QListWidget#helpNavigation::item:selected {{
                background:{t['accent_light']}; color:{t['accent']};
                font-weight:600;
            }}
            QTextBrowser#helpReader {{
                background:{t['bg_card']}; border:none;
                border-radius:12px;
            }}
        """)
        row = self.navigation.currentRow()
        if row >= 0:
            self._show_chapter(row)
