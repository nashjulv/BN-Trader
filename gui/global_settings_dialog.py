"""
风控设置 / 持仓设置 / 全局参数 — 匹配 UI 设计稿详情页
"""

import json
from pathlib import Path
from typing import Dict, Callable, Optional

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QDoubleSpinBox, QSpinBox,
                               QFrame, QFormLayout, QMessageBox, QScrollArea,
                               QGridLayout)
from PyQt6.QtCore import pyqtSignal

from gui.styles import Theme
from config import Config
from utils.settings_store import load_json_settings, save_json_settings

SETTINGS_PATH = Config.PREFERENCES_DIR / "global.json"
LEGACY_SETTINGS_PATH = Path.home() / ".bn_trader_global.json"

DEFAULTS = {
    "capital": {
        "total_capital": 10000.0, "reserve_ratio": 0.20,
        "max_single_trade_ratio": 0.30, "daily_loss_limit": 0.05,
    },
    "risk": {
        "max_loss_per_trade": 0.02, "max_profit_per_trade": 0.05,
        "max_hold_time": 3600, "max_daily_trades": 20,
        "max_consecutive_loss": 3, "max_drawdown": 0.20,
        "cooldown_seconds": 300,
        "min_reserve_ratio": 0.10,
    },
    "position": {
        "position_multiplier": 1.0, "trailing_stop_pct": 1.5,
        "min_risk_reward": 1.5, "auto_close_timeout": 0,
        "initial_position_ratio": 0.20, "scale_in_ratio": 0.50,
        "max_position_ratio": 0.50, "take_profit_trigger": 4.0,
        "breakeven_stop": 0.50,
    },
}

LABELS = {
    "total_capital": "初始总资金", "reserve_ratio": "准备金比例",
    "max_single_trade_ratio": "单笔最大仓位", "daily_loss_limit": "日亏损上限",
    "max_loss_per_trade": "单笔最大亏损 %", "max_profit_per_trade": "单笔止盈 %",
    "max_hold_time": "最大持仓时间(秒)", "max_daily_trades": "最多日交易次数",
    "max_consecutive_loss": "最大连续亏损", "max_drawdown": "最大回撤比例",
    "cooldown_seconds": "冷却时间(秒)", "position_multiplier": "仓位倍数",
    "trailing_stop_pct": "移动止损 %", "min_risk_reward": "最低盈亏比",
    "auto_close_timeout": "超时自动平仓(秒)",
    "min_reserve_ratio": "准备金最低比例",
    "initial_position_ratio": "初始仓位比例",
    "scale_in_ratio": "加仓仓位比例",
    "max_position_ratio": "最大仓位比例",
    "take_profit_trigger": "止盈触发比例 %",
    "breakeven_stop": "保本止损 %",
}

# 设计稿分组
RISK_GROUPS = [
    ("单笔风控", ["max_loss_per_trade", "max_profit_per_trade", "max_hold_time"]),
    ("日度风控", ["max_daily_trades", "max_consecutive_loss", "cooldown_seconds"]),
    ("账户风控", ["max_drawdown", "min_reserve_ratio"]),
]

POSITION_GROUPS = [
    ("仓位管理", ["position_multiplier", "initial_position_ratio",
                 "scale_in_ratio", "max_position_ratio"]),
    ("止盈止损", ["trailing_stop_pct", "min_risk_reward",
                 "take_profit_trigger"]),
    ("持仓管理", ["auto_close_timeout", "breakeven_stop"]),
]

CAPITAL_GROUPS = [
    ("资金池", ["total_capital", "reserve_ratio",
               "max_single_trade_ratio", "daily_loss_limit"]),
]


def load_global_settings() -> dict:
    return load_json_settings(
        SETTINGS_PATH,
        DEFAULTS,
        legacy_paths=[LEGACY_SETTINGS_PATH],
    )


def save_global_settings(settings: dict):
    save_json_settings(SETTINGS_PATH, settings)


def _make_spin(val):
    if isinstance(val, float) and val < 10:
        sp = QDoubleSpinBox()
        sp.setRange(0.001, 9999)
        sp.setDecimals(4)
        sp.setValue(val)
        sp.setSingleStep(0.01)
    elif isinstance(val, float):
        sp = QDoubleSpinBox()
        sp.setRange(0, 999999)
        sp.setDecimals(2)
        sp.setValue(val)
        sp.setSingleStep(100)
    else:
        sp = QSpinBox()
        sp.setRange(0, 99999)
        sp.setValue(int(val))
    sp.setFixedWidth(140)
    return sp


class SettingsFormPage(QWidget):
    """通用分组表单设置页"""
    settings_saved = pyqtSignal(dict)

    def __init__(self, title: str, section_key: str,
                 groups: list, parent=None):
        super().__init__(parent)
        self.section_key = section_key
        self.groups_def = groups
        self._fields: Dict[str, object] = {}
        self._title_text = title
        self._init_ui()
        self._load()
        self._refresh_theme()

    def _init_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        outer.addWidget(scroll)

        content = QWidget()
        self._content = content
        content.setObjectName("settingsPageContent")
        scroll.setWidget(content)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        title = QLabel(self._title_text)
        title.setStyleSheet("font-size:18px; font-weight:700;")
        layout.addWidget(title)

        defaults = DEFAULTS[self.section_key]
        for gname, keys in self.groups_def:
            card = QFrame()
            card.setObjectName("cardFrame")
            card.setMaximumWidth(900)
            fl = QGridLayout(card)
            fl.setContentsMargins(16, 14, 16, 12)
            fl.setHorizontalSpacing(12)
            fl.setVerticalSpacing(8)
            gt = QLabel(gname)
            gt.setObjectName("sectionTitle")
            fl.addWidget(gt, 0, 0, 1, 6)
            for index, key in enumerate(keys):
                if key not in defaults:
                    continue
                sp = _make_spin(defaults[key])
                row = index // 3 + 1
                col = (index % 3) * 2
                fl.addWidget(QLabel(LABELS.get(key, key)), row, col)
                fl.addWidget(sp, row, col + 1)
                self._fields[key] = sp
            layout.addWidget(card)
            self._cards = getattr(self, "_cards", [])
            self._cards.append(card)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        reset_btn = QPushButton("恢复默认")
        reset_btn.setObjectName("ghostBtn")
        reset_btn.clicked.connect(self._reset)
        btn_row.addWidget(reset_btn)
        save_btn = QPushButton("保存并应用")
        save_btn.setObjectName("primaryBtn")
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)
        layout.addStretch()

    def _refresh_theme(self):
        t = Theme.colors()
        self.setStyleSheet("")
        self._content.setStyleSheet(
            f"QWidget#settingsPageContent {{ background:{t['bg_main']}; }}")
        parent = self._content.parentWidget()
        if parent:
            parent.setStyleSheet(
                f"QWidget#{parent.objectName()} {{ background:{t['bg_main']}; }}")
        for card in getattr(self, "_cards", []):
            card.setStyleSheet(Theme.card_style())

    def _load(self):
        data = load_global_settings().get(self.section_key, DEFAULTS[self.section_key])
        for key, widget in self._fields.items():
            widget.setValue(data.get(key, DEFAULTS[self.section_key][key]))

    def _reset(self):
        r = QMessageBox.question(self, "确认", "恢复为默认值？")
        if r == QMessageBox.StandardButton.Yes:
            for key, widget in self._fields.items():
                widget.setValue(DEFAULTS[self.section_key][key])

    def _save(self):
        all_data = load_global_settings()
        section = {key: widget.value() for key, widget in self._fields.items()}
        all_data[self.section_key] = {
            **DEFAULTS[self.section_key], **section
        }
        save_global_settings(all_data)
        QMessageBox.information(self, "已保存", f"{self._title_text}已保存并应用。")
        self.settings_saved.emit(all_data)


class RiskSettingsPage(SettingsFormPage):
    def __init__(self, parent=None):
        super().__init__("风控设置", "risk", RISK_GROUPS, parent)


class PositionSettingsPage(SettingsFormPage):
    def __init__(self, parent=None):
        super().__init__("持仓设置", "position", POSITION_GROUPS, parent)


class CapitalSettingsPage(SettingsFormPage):
    def __init__(self, parent=None):
        super().__init__("资金设置", "capital", CAPITAL_GROUPS, parent)


# 兼容旧 GlobalSettingsDialog
class GlobalSettingsDialog:
    DialogCode = type("DC", (), {"Accepted": 1, "Rejected": 0})()

    def __init__(self, parent=None):
        from PyQt6.QtWidgets import QDialog, QVBoxLayout as VL, QTabWidget
        self._dlg = QDialog(parent)
        self._dlg.setWindowTitle("全局参数设定")
        self._dlg.resize(520, 560)
        lay = VL(self._dlg)
        tabs = QTabWidget()
        self._risk = RiskSettingsPage()
        self._pos = PositionSettingsPage()
        self._cap = CapitalSettingsPage()
        tabs.addTab(self._cap, "资金池")
        tabs.addTab(self._risk, "风控")
        tabs.addTab(self._pos, "持仓")
        lay.addWidget(tabs)
        for p in [self._risk, self._pos, self._cap]:
            p.settings_saved.connect(lambda _: self._dlg.accept())
        t = Theme.colors()
        self._dlg.setStyleSheet(f"background:{t['bg_main']};")

    def exec(self):
        return self._dlg.exec()

    def get_all_settings(self) -> dict:
        return load_global_settings()
