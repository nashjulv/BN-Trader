"""
BN-Trader UI Design System
匹配 docs/UI设计.png — 浅色 Ant Design 风格 + 可选暗色主题
"""

from PyQt6.QtGui import QColor

# ====================================================================
#  Design Tokens
# ====================================================================
R_PANEL  = "8px"
R_BUTTON = "6px"
R_INPUT  = "4px"
R_CARD   = "8px"

FONT_SYSTEM = (
    '"Inter", "SF Pro Text", "PingFang SC", "Microsoft YaHei UI", '
    '"Segoe UI", "Helvetica Neue", sans-serif'
)
FONT_NUMBER = (
    '"SF Mono", "JetBrains Mono", "Cascadia Code", '
    '"DIN Alternate", "Consolas", monospace'
)

# ====================================================================
#  Light Theme — 主界面设计稿（默认）
# ====================================================================
LIGHT = {
    "name": "light",
    "bg_main":    "#F5F7FA",
    "bg_surface": "#FFFFFF",
    "bg_card":    "#FFFFFF",
    "bg_input":   "#FFFFFF",
    "bg_hover":   "#F1F3F5",
    "bg_pressed": "#E5E8EC",
    "hover_border": "#C9CED6",
    "bg_sidebar": "#FFFFFF",

    "text_primary":   "#262626",
    "text_secondary": "#8C8C8C",
    "text_dim":       "#BFBFBF",
    "text_sidebar":   "#FFFFFF",
    "text_sidebar_dim": "#7D8998",

    "accent":       "#1890FF",
    "accent_dim":   "#096DD9",
    "accent_glow":  "#40A9FF",
    "accent_light": "#E6F4FF",
    "secondary":    "#597EF7",
    "ai_purple":    "#722ED1",

    "success": "#52C41A",
    "danger":  "#FF4D4F",
    "warning": "#FAAD14",
    "info":    "#1890FF",

    "border":       "#E4E7EB",
    "divider":      "#EEF0F2",
    "border_focus": "#1890FF",
    "border_active":"#096DD9",

    "buy":  "#52C41A",
    "sell": "#FF4D4F",

    "scrollbar_bg":     "#F5F7FA",
    "scrollbar_handle": "#D9D9D9",

    "pnlbar_bg":     "#FFFFFF",
    "pnlbar_border": "#E8E8E8",

    "tab_active":    "#1890FF",
    "tab_active_bg": "#FFFFFF",

    "chart_bg":   "#FFFFFF",
    "chart_grid": "#F0F0F0",

    "progress_bg":    "#F0F0F0",
    "progress_chunk": "#1890FF",

    "tag_trade":  "#1890FF",
    "tag_risk":   "#FA8C16",
    "tag_system": "#595959",
    "tip_bg":     "#FFFBE6",
    "tip_border": "#FFE58F",
}

# ====================================================================
#  Dark Theme — 可选
# ====================================================================
DARK = {
    "name": "dark",
    "bg_main":    "#0D1117",
    "bg_surface": "#161B22",
    "bg_card":    "#1C2333",
    "bg_input":   "#1C2333",
    "bg_hover":   "#252D3A",
    "bg_pressed": "#303947",
    "hover_border": "#4A5565",
    "bg_sidebar": "#0A0E14",

    "text_primary":   "#E6EDF3",
    "text_secondary": "#8B949E",
    "text_dim":       "#586274",
    "text_sidebar":   "#E6EDF3",
    "text_sidebar_dim": "#586274",

    "accent":       "#1890FF",
    "accent_dim":   "#096DD9",
    "accent_glow":  "#40A9FF",
    "accent_light": "#111D2C",
    "secondary":    "#4A6CFF",
    "ai_purple":    "#A855F7",

    "success": "#3FB950",
    "danger":  "#F85149",
    "warning": "#D29922",
    "info":    "#58A6FF",

    "border":       "#30363D",
    "divider":      "#21262D",
    "border_focus": "#1890FF",
    "border_active":"#096DD9",

    "buy":  "#3FB950",
    "sell": "#F85149",

    "scrollbar_bg":     "#0D1117",
    "scrollbar_handle": "#30363D",

    "pnlbar_bg":     "#161B22",
    "pnlbar_border": "#30363D",

    "tab_active":    "#1890FF",
    "tab_active_bg": "#1C2333",

    "chart_bg":   "#0D1117",
    "chart_grid": "#21262D",

    "progress_bg":    "#21262D",
    "progress_chunk": "#1890FF",

    "tag_trade":  "#1890FF",
    "tag_risk":   "#D29922",
    "tag_system": "#8B949E",
    "tip_bg":     "#2A2111",
    "tip_border": "#5C4A1A",
}

# ====================================================================
#  Scene Colors
# ====================================================================
SCENE_COLORS = {
    "TRENDING":  "#52C41A",
    "RANGING":   "#1890FF",
    "BREAKOUT":  "#FAAD14",
    "REVERSAL":  "#722ED1",
    "EXTREME":   "#FF4D4F",
}

SCENE_INFO = {
    "TRENDING":  {"name": "趋势行情", "icon": "↗", "color": "#52C41A", "tip": "顺势交易 · 移动止损"},
    "RANGING":   {"name": "震荡行情", "icon": "⇋", "color": "#1890FF", "tip": "高抛低吸 · 区间边界"},
    "BREAKOUT":  {"name": "突破行情", "icon": "↑", "color": "#FAAD14", "tip": "突破跟进 · 确认放量"},
    "REVERSAL":  {"name": "反转行情", "icon": "↺", "color": "#722ED1", "tip": "逆势试探 · 严格止损"},
    "EXTREME":   {"name": "极端行情", "icon": "⚡", "color": "#FF4D4F", "tip": "观望为主 · 耐心等待"},
}


# ====================================================================
#  Theme Manager
# ====================================================================
class Theme:
    _active = "light"

    @classmethod
    def set(cls, name: str):
        if name in ("dark", "light"):
            cls._active = name

    @classmethod
    def toggle(cls) -> str:
        cls._active = "light" if cls._active == "dark" else "dark"
        return cls._active

    @classmethod
    def current_name(cls) -> str:
        return cls._active

    @classmethod
    def is_dark(cls) -> bool:
        return cls._active == "dark"

    @classmethod
    def colors(cls) -> dict:
        return DARK if cls._active == "dark" else LIGHT

    @classmethod
    def c(cls, key: str) -> str:
        return cls.colors().get(key, "")

    @classmethod
    def stylesheet(cls, theme_name: str = None) -> str:
        t = DARK if (theme_name or cls._active) == "dark" else LIGHT
        return _stylesheet(t)

    @classmethod
    def chart_colors(cls):
        t = cls.colors()
        return {
            "background": t["chart_bg"],
            "foreground": t["text_primary"],
            "grid": t["chart_grid"],
            "candle_up":   QColor("#52C41A"),
            "candle_down": QColor("#FF4D4F"),
        }

    @classmethod
    def card_style(cls) -> str:
        t = cls.colors()
        return (
            f"QFrame#cardFrame {{ background:{t['bg_card']}; "
            f"border:1px solid {t['border']}; border-radius:{R_CARD}; }}"
        )


# ====================================================================
#  QSS Builder
# ====================================================================
def _stylesheet(t: dict) -> str:
    return f"""
    QMainWindow {{
        background-color: {t["bg_main"]};
    }}
    QWidget {{
        color: {t["text_primary"]};
        font-size: 12px;
        font-family: {FONT_SYSTEM};
    }}

    QGroupBox {{
        background-color: {t["bg_card"]};
        border: 1px solid {t["border"]};
        border-radius: {R_PANEL};
        margin-top: 12px;
        padding: 16px 12px 10px 12px;
        font-size: 12px;
        font-weight: 600;
        color: {t["text_primary"]};
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 12px;
        padding: 0 6px;
        color: {t["text_primary"]};
        background-color: transparent;
    }}

    QPushButton {{
        background-color: {t["bg_input"]};
        color: {t["text_primary"]};
        border: 1px solid {t["border"]};
        border-radius: {R_BUTTON};
        padding: 4px 12px;
        min-height: 28px;
        font-size: 12px;
        font-weight: 500;
    }}
    QPushButton:hover  {{ background-color: {t["bg_hover"]}; border-color: {t["hover_border"]}; color: {t["text_primary"]}; }}
    QPushButton:pressed {{ background-color: {t["bg_pressed"]}; }}
    QPushButton:disabled {{ color: {t["text_dim"]}; background: {t["divider"]}; }}

    QPushButton#primaryBtn {{
        background-color: {t["accent"]};
        color: #fff; border: none; font-weight: 600;
        min-height: 36px; padding: 6px 20px;
    }}
    QPushButton#primaryBtn:hover {{ background-color: #1677E8; color:#fff; }}

    QPushButton#buyBtn {{
        background-color: {t["buy"]};
        color: #fff; border: none;
        font-size: 15px; font-weight: 700;
        min-height: 44px; border-radius: {R_BUTTON};
    }}
    QPushButton#buyBtn:hover {{ background-color: #49B817; color:#fff; }}

    QPushButton#sellBtn {{
        background-color: {t["sell"]};
        color: #fff; border: none;
        font-size: 15px; font-weight: 700;
        min-height: 44px; border-radius: {R_BUTTON};
    }}
    QPushButton#sellBtn:hover {{ background-color: #EF4547; color:#fff; }}

    QPushButton#dangerBtn {{
        background-color: transparent; color: {t["danger"]};
        border: 1px solid {t["danger"]};
    }}
    QPushButton#dangerBtn:hover {{
        background-color: {t["danger"]}; color: #fff;
    }}

    QPushButton#ghostBtn {{
        background: transparent; color: {t["text_secondary"]};
        border: 1px solid {t["border"]};
    }}

    QPushButton#textBtn {{
        background: transparent; color: {t["accent"]};
        border: none; min-height: 28px; padding: 2px 8px;
    }}
    QPushButton#textBtn:hover {{ color: {t["accent_glow"]}; }}

    QLabel {{ color: {t["text_primary"]}; font-size: 12px; }}
    QLabel#titleLabel   {{ font-size: 13px; font-weight: 700; color: {t["text_primary"]}; }}
    QLabel#sectionTitle {{ font-size: 12px; font-weight: 600; color: {t["text_primary"]}; }}
    QLabel#valueLabel   {{ font-size: 19px; font-weight: 700; font-family: {FONT_NUMBER}; }}
    QLabel#pnlPositive  {{ color: {t["success"]}; font-family: {FONT_NUMBER}; }}
    QLabel#pnlNegative  {{ color: {t["danger"]};  font-family: {FONT_NUMBER}; }}
    QLabel#captionLabel {{ font-size: 12px; color: {t["text_secondary"]}; }}
    QLabel#dimLabel     {{ font-size: 11px; color: {t["text_dim"]}; }}

    QLineEdit, QDoubleSpinBox, QSpinBox, QComboBox {{
        background-color: {t["bg_input"]};
        color: {t["text_primary"]};
        border: 1px solid {t["border"]};
        border-radius: {R_INPUT};
        padding: 3px 8px;
        min-height: 28px;
        font-size: 12px;
    }}
    QLineEdit:focus, QDoubleSpinBox:focus, QSpinBox:focus, QComboBox:focus {{
        border-color: {t["border_focus"]};
    }}
    QComboBox::drop-down  {{ border: none; width: 20px; }}
    QComboBox QAbstractItemView {{
        background-color: {t["bg_surface"]};
        color: {t["text_primary"]};
        selection-background-color: {t["bg_hover"]};
        selection-color: {t["text_primary"]};
        border: 1px solid {t["border"]};
        border-radius: {R_INPUT};
        font-size: 13px;
    }}

    QScrollArea, QAbstractScrollArea {{
        background-color: {t["bg_main"]};
        border: none;
    }}
    QWidget#qt_scrollarea_viewport {{
        background-color: {t["bg_main"]};
    }}

    QTableWidget {{
        background-color: {t["bg_card"]};
        color: {t["text_primary"]};
        border: 1px solid {t["border"]};
        border-radius: {R_PANEL};
        gridline-color: {t["divider"]};
        font-size: 12px;
    }}
    QTableWidget::item {{ padding: 6px 8px; border: none; }}
    QTableWidget::item:selected {{
        background: {t["bg_hover"]}; color: {t["text_primary"]};
    }}
    QHeaderView::section {{
        background-color: {t["bg_main"]};
        color: {t["text_secondary"]};
        border: none;
        border-bottom: 1px solid {t["border"]};
        padding: 8px;
        font-size: 12px;
        font-weight: 600;
    }}

    QSplitter::handle {{
        background-color: {t["divider"]};
    }}
    QSplitter::handle:horizontal {{ width: 1px; }}
    QSplitter::handle:vertical   {{ height: 1px; }}
    QSplitter::handle:hover      {{ background-color: {t["hover_border"]}; }}

    QScrollBar:vertical  {{ background: transparent; width: 6px; margin: 0; }}
    QScrollBar::handle:vertical {{ background: {t["scrollbar_handle"]}; border-radius: 3px; min-height: 24px; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QScrollBar:horizontal {{ background: transparent; height: 6px; }}
    QScrollBar::handle:horizontal {{ background: {t["scrollbar_handle"]}; border-radius: 3px; }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

    QTabWidget::pane {{
        border: 1px solid {t["border"]};
        background-color: {t["bg_card"]};
        border-radius: 0 0 {R_PANEL} {R_PANEL};
        top: -1px;
    }}
    QTabBar::tab {{
        background: transparent;
        color: {t["text_secondary"]};
        border: none;
        border-bottom: 2px solid transparent;
        padding: 10px 20px;
        margin-right: 0;
        font-size: 13px;
        font-weight: 500;
    }}
    QTabBar::tab:selected {{
        color: {t["accent"]};
        border-bottom: 2px solid {t["accent"]};
        font-weight: 600;
    }}
    QTabBar::tab:hover {{ color: {t["text_primary"]}; background:{t["bg_hover"]}; }}

    QProgressBar {{
        background-color: {t["progress_bg"]};
        border: none;
        border-radius: 4px;
        text-align: center;
        color: {t["text_primary"]};
        font-size: 10px;
        min-height: 8px;
        max-height: 8px;
    }}
    QProgressBar::chunk {{
        background-color: {t["accent"]};
        border-radius: 4px;
    }}

    QToolTip {{
        background-color: {t["bg_card"]};
        color: {t["text_primary"]};
        border: 1px solid {t["border"]};
        padding: 6px 10px;
        border-radius: {R_INPUT};
        font-size: 12px;
    }}

    QMenuBar {{
        background: {t["bg_surface"]}; color: {t["text_primary"]};
        border-bottom: 1px solid {t["border"]}; padding: 2px 0;
    }}
    QMenuBar::item:selected {{ background: {t["bg_hover"]}; }}
    QMenu {{
        background: {t["bg_surface"]}; color: {t["text_primary"]};
        border: 1px solid {t["border"]}; border-radius: {R_INPUT}; padding: 6px;
    }}
    QMenu::item {{ padding: 6px 28px 6px 12px; font-size: 13px; border-radius: 4px; }}
    QMenu::item:selected {{ background: {t["bg_hover"]}; color: {t["text_primary"]}; }}
    QMenu::separator {{ height: 1px; background: {t["divider"]}; margin: 4px 6px; }}

    QStatusBar {{
        background: {t["bg_surface"]};
        color: {t["text_secondary"]};
        border-top: 1px solid {t["border"]};
        font-size: 12px;
        padding: 2px 12px;
    }}

    QCheckBox {{ spacing: 6px; font-size: 13px; }}
    QCheckBox::indicator {{
        width: 16px; height: 16px;
        border: 1px solid {t["border"]};
        border-radius: 3px;
        background: {t["bg_input"]};
    }}
    QCheckBox::indicator:checked {{
        background: {t["accent"]}; border-color: {t["accent"]};
    }}

    QRadioButton {{ font-size: 13px; spacing: 6px; }}
    QRadioButton::indicator {{
        width: 16px; height: 16px;
        border: 1px solid {t["border"]};
        border-radius: 8px;
        background: {t["bg_input"]};
    }}
    QRadioButton::indicator:checked {{
        background: {t["accent"]}; border-color: {t["accent"]};
    }}

    QFrame#cardFrame {{
        background: {t["bg_card"]};
        border: 1px solid {t["border"]};
        border-radius: {R_CARD};
    }}
    QFrame#separator {{ background: {t["divider"]}; max-height: 1px; }}
    """
