"""
策略设置详情页 — 匹配 UI 设计稿
趋势 / 震荡 / 突破 / 反转 / 极端 策略参数
"""

import json
from pathlib import Path
from typing import Dict

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QTabWidget, QScrollArea, QPushButton,
                               QDoubleSpinBox, QSpinBox, QFrame,
                               QFormLayout, QMessageBox, QCheckBox, QGridLayout)
from PyQt6.QtCore import Qt, pyqtSignal

from gui.styles import Theme, SCENE_COLORS, SCENE_INFO
from config import Config
from utils.settings_store import load_json_settings, save_json_settings

SETTINGS_PATH = Config.PREFERENCES_DIR / "strategies.json"
LEGACY_SETTINGS_PATH = Path.home() / ".bn_trader_strategies.json"

DEFAULT_PARAMS = {
    "TRENDING": {
        "enabled": True, "fast_ma": 5, "slow_ma": 20,
        "macd_fast": 12, "macd_slow": 26, "macd_signal": 9,
        "adx_threshold": 25, "stop_loss_pct": 2.0,
        "take_profit_pct": 5.0, "trailing_stop": 1.5,
    },
    "RANGING": {
        "enabled": True, "bb_period": 20, "bb_std": 2.0,
        "rsi_period": 14, "rsi_oversold": 30, "rsi_overbought": 70,
        "stop_loss_pct": 3.0, "take_profit_pct": 3.0,
    },
    "BREAKOUT": {
        "enabled": True, "lookback": 20, "volume_threshold": 1.5,
        "breakout_pct": 0.8, "atr_period": 14, "atr_filter": 1.5,
        "stop_loss_pct": 1.5, "risk_reward": 2.0,
    },
    "REVERSAL": {
        "enabled": False,
        "rsi_period": 14, "rsi_oversold": 25, "rsi_overbought": 75,
        "divergence_lookback": 10, "min_rsi_divergence": 5,
        "stop_loss_pct": 2.0, "take_profit_pct": 4.0,
    },
    "EXTREME": {
        "enabled": False,
        "atr_multiplier": 3.0, "volume_spike": 3.0,
        "hold_time": 300, "stop_loss_pct": 1.0, "take_profit_pct": 2.0,
    },
}


def load_strategy_settings() -> dict:
    return load_json_settings(
        SETTINGS_PATH,
        DEFAULT_PARAMS,
        legacy_paths=[LEGACY_SETTINGS_PATH],
    )


def save_strategy_settings(settings: dict):
    save_json_settings(SETTINGS_PATH, settings)


def _param_label(key: str) -> str:
    mapping = {
        "fast_ma": "快线周期", "slow_ma": "慢线周期",
        "macd_fast": "MACD 快线", "macd_slow": "MACD 慢线", "macd_signal": "MACD 信号",
        "adx_threshold": "ADX 阈值", "trailing_stop": "移动止损 %",
        "stop_loss_pct": "止损比例 %", "take_profit_pct": "止盈比例 %",
        "bb_period": "布林带周期", "bb_std": "布林带标准差",
        "rsi_period": "RSI 周期", "rsi_oversold": "RSI 超卖线", "rsi_overbought": "RSI 超买线",
        "lookback": "回看周期", "volume_threshold": "成交量倍数",
        "breakout_pct": "突破阈值 %", "atr_period": "ATR 周期",
        "atr_filter": "ATR 过滤倍", "atr_multiplier": "ATR 倍数",
        "risk_reward": "盈亏比", "volume_spike": "成交量激增倍",
        "divergence_lookback": "背离回看", "min_rsi_divergence": "RSI 背离差值",
        "hold_time": "持仓时间(秒)",
    }
    return mapping.get(key, key)


# 参数分组（趋势策略按设计稿分组）
PARAM_GROUPS = {
    "TRENDING": [
        ("均线参数", ["fast_ma", "slow_ma"]),
        ("MACD 参数", ["macd_fast", "macd_slow", "macd_signal", "adx_threshold"]),
        ("交易参数", ["stop_loss_pct", "take_profit_pct", "trailing_stop"]),
    ],
}


class StrategyParamPanel(QWidget):
    def __init__(self, scene_type: str):
        super().__init__()
        self.scene_type = scene_type
        self._fields: Dict[str, object] = {}
        self._init_ui()

    def _init_ui(self):
        info = SCENE_INFO.get(self.scene_type, SCENE_INFO["RANGING"])
        color = SCENE_COLORS.get(self.scene_type, "#888")
        t = Theme.colors()

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(4, 4, 4, 4)

        hdr = QHBoxLayout()
        icon_lbl = QLabel(f"{info['icon']} {info['name']}")
        icon_lbl.setStyleSheet(f"font-size:15px; font-weight:700; color:{color};")
        hdr.addWidget(icon_lbl)
        hdr.addStretch()
        self._enabled_cb = QCheckBox("启用此策略")
        self._enabled_cb.setChecked(True)
        hdr.addWidget(self._enabled_cb)
        layout.addLayout(hdr)

        desc = QLabel(info["tip"])
        desc.setObjectName("captionLabel")
        layout.addWidget(desc)

        params = DEFAULT_PARAMS[self.scene_type]
        groups = PARAM_GROUPS.get(self.scene_type)

        if groups:
            for gname, keys in groups:
                card = QFrame()
                card.setObjectName("cardFrame")
                card.setStyleSheet(Theme.card_style())
                fl = QGridLayout(card)
                fl.setContentsMargins(14, 14, 14, 10)
                fl.setHorizontalSpacing(12)
                fl.setVerticalSpacing(8)
                title = QLabel(gname)
                title.setObjectName("sectionTitle")
                fl.addWidget(title, 0, 0, 1, 6)
                for index, key in enumerate(keys):
                    if key not in params:
                        continue
                    sp = self._make_spin(params[key])
                    row = index // 3 + 1
                    col = (index % 3) * 2
                    fl.addWidget(QLabel(_param_label(key)), row, col)
                    fl.addWidget(sp, row, col + 1)
                    self._fields[key] = sp
                layout.addWidget(card)
            # leftover keys
            used = {k for _, keys in groups for k in keys}
            leftover = [k for k in params if k != "enabled" and k not in used]
            if leftover:
                card = QFrame()
                card.setObjectName("cardFrame")
                card.setStyleSheet(Theme.card_style())
                fl = QGridLayout(card)
                fl.setContentsMargins(14, 14, 14, 10)
                for index, key in enumerate(leftover):
                    sp = self._make_spin(params[key])
                    row = index // 3
                    col = (index % 3) * 2
                    fl.addWidget(QLabel(_param_label(key)), row, col)
                    fl.addWidget(sp, row, col + 1)
                    self._fields[key] = sp
                layout.addWidget(card)
        else:
            card = QFrame()
            card.setObjectName("cardFrame")
            card.setStyleSheet(Theme.card_style())
            fl = QGridLayout(card)
            fl.setContentsMargins(14, 14, 14, 10)
            fl.setHorizontalSpacing(12)
            fl.setVerticalSpacing(8)
            visible = [(key, val) for key, val in params.items() if key != "enabled"]
            for index, (key, val) in enumerate(visible):
                if key == "enabled":
                    continue
                sp = self._make_spin(val)
                row = index // 3
                col = (index % 3) * 2
                fl.addWidget(QLabel(_param_label(key)), row, col)
                fl.addWidget(sp, row, col + 1)
                self._fields[key] = sp
            layout.addWidget(card)

        layout.addStretch()

    def _make_spin(self, val):
        if isinstance(val, float) and val < 10:
            sp = QDoubleSpinBox()
            sp.setRange(0.1, 1000)
            sp.setDecimals(2)
            sp.setValue(val)
            sp.setSingleStep(0.1)
        elif isinstance(val, float):
            sp = QDoubleSpinBox()
            sp.setRange(0, 9999)
            sp.setDecimals(1)
            sp.setValue(val)
        else:
            sp = QSpinBox()
            sp.setRange(1, 9999)
            sp.setValue(int(val))
        sp.setFixedWidth(140)
        return sp

    def get_values(self) -> dict:
        vals = {"enabled": self._enabled_cb.isChecked()}
        for key, widget in self._fields.items():
            vals[key] = widget.value()
        return vals

    def set_values(self, data: dict):
        self._enabled_cb.setChecked(data.get("enabled", True))
        for key, widget in self._fields.items():
            if key in data:
                widget.setValue(data[key])


class StrategySettingsPage(QWidget):
    """嵌入主窗口的策略设置页"""
    settings_saved = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._panels: Dict[str, StrategyParamPanel] = {}
        self._init_ui()
        self._load()
        self._refresh_theme()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)
        self.setMaximumWidth(980)

        title = QLabel("策略设置")
        title.setStyleSheet("font-size:18px; font-weight:700;")
        layout.addWidget(title)

        sub = QLabel("调整各行情场景的策略参数，保存后可启用自动交易")
        sub.setObjectName("captionLabel")
        layout.addWidget(sub)

        self._tabs = QTabWidget()
        for st in ["TRENDING", "RANGING", "BREAKOUT", "REVERSAL", "EXTREME"]:
            info = SCENE_INFO[st]
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QScrollArea.Shape.NoFrame)
            panel = StrategyParamPanel(st)
            panel.setObjectName("strategyPanel")
            scroll.setWidget(panel)
            self._panels[st] = panel
            self._tabs.addTab(scroll, info["name"])
        layout.addWidget(self._tabs, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        reset_btn = QPushButton("恢复默认")
        reset_btn.setObjectName("ghostBtn")
        reset_btn.clicked.connect(self._reset_defaults)
        btn_row.addWidget(reset_btn)
        self._save_btn = QPushButton("保存并应用")
        self._save_btn.setObjectName("primaryBtn")
        self._save_btn.clicked.connect(self._save)
        btn_row.addWidget(self._save_btn)
        layout.addLayout(btn_row)

    def _refresh_theme(self):
        t = Theme.colors()
        self.setStyleSheet("")
        for panel in self._panels.values():
            panel.setStyleSheet(
                f"QWidget#strategyPanel {{ background:{t['bg_main']}; }}")
            parent = panel.parentWidget()
            if parent:
                parent.setStyleSheet(
                    f"QWidget#{parent.objectName()} {{ background:{t['bg_main']}; }}")

    def _load(self):
        data = load_strategy_settings()
        for st, panel in self._panels.items():
            panel.set_values(data.get(st, DEFAULT_PARAMS[st]))

    def _reset_defaults(self):
        r = QMessageBox.question(self, "确认", "恢复所有策略参数为默认值？")
        if r == QMessageBox.StandardButton.Yes:
            for st, panel in self._panels.items():
                panel.set_values(DEFAULT_PARAMS[st])

    def _save(self):
        all_settings = {}
        enabled_count = 0
        for st, panel in self._panels.items():
            vals = panel.get_values()
            all_settings[st] = vals
            if vals.get("enabled"):
                enabled_count += 1
        if enabled_count == 0:
            QMessageBox.warning(self, "提示", "请至少启用一个策略")
            return
        save_strategy_settings(all_settings)
        QMessageBox.information(
            self, "已保存",
            f"策略参数已保存！已启用 {enabled_count} 个策略。")
        self.settings_saved.emit()


class StrategySettingsDialog:
    """兼容旧对话框调用"""
    DialogCode = type("DC", (), {"Accepted": 1, "Rejected": 0})()

    def __init__(self, parent=None):
        from PyQt6.QtWidgets import QDialog, QVBoxLayout as VL
        self._dlg = QDialog(parent)
        self._dlg.setWindowTitle("策略参数设定")
        self._dlg.resize(560, 640)
        lay = VL(self._dlg)
        lay.setContentsMargins(0, 0, 0, 0)
        self._page = StrategySettingsPage(self._dlg)
        self._page.settings_saved.connect(self._dlg.accept)
        lay.addWidget(self._page)
        t = Theme.colors()
        self._dlg.setStyleSheet(f"background:{t['bg_main']};")

    def exec(self):
        return self._dlg.exec()
