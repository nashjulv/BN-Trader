"""
风控状态卡片 — 主界面左侧紧凑卡片
"""

from typing import Dict

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QFrame, QProgressBar, QPushButton)
from PyQt6.QtCore import Qt

from gui.styles import Theme


class RiskPanel(QWidget):

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

        hdr = QHBoxLayout()
        self._title = QLabel("风控状态")
        self._title.setObjectName("sectionTitle")
        hdr.addWidget(self._title)
        hdr.addStretch()
        self.status_label = QLabel("正常")
        hdr.addWidget(self.status_label)
        layout.addLayout(hdr)

        self.daily_loss_label = QLabel("日亏损额度")
        self.daily_loss_bar = QProgressBar()
        self.daily_loss_bar.setMaximum(100)
        self.daily_loss_bar.setTextVisible(False)
        self._daily_pct = QLabel("0%")

        self.daily_trades_label = QLabel("日交易次数")
        self.daily_trades_bar = QProgressBar()
        self.daily_trades_bar.setMaximum(100)
        self.daily_trades_bar.setTextVisible(False)
        self._trades_pct = QLabel("0%")

        self.drawdown_label = QLabel("账户回撤")
        self.drawdown_bar = QProgressBar()
        self.drawdown_bar.setMaximum(100)
        self.drawdown_bar.setTextVisible(False)
        self._dd_pct = QLabel("0%")

        for lbl, bar, pct in [
            (self.daily_loss_label, self.daily_loss_bar, self._daily_pct),
            (self.daily_trades_label, self.daily_trades_bar, self._trades_pct),
            (self.drawdown_label, self.drawdown_bar, self._dd_pct),
        ]:
            row = QHBoxLayout()
            row.setSpacing(6)
            lbl.setObjectName("captionLabel")
            lbl.setFixedWidth(72)
            pct.setObjectName("dimLabel")
            pct.setFixedWidth(36)
            pct.setAlignment(Qt.AlignmentFlag.AlignRight)
            row.addWidget(lbl)
            row.addWidget(bar, 1)
            row.addWidget(pct)
            layout.addLayout(row)

        if not self.compact:
            self.consecutive_label = QLabel("连续亏损: 0/3")
            self.cooldown_label = QLabel("冷却: 无")
            self.reserve_label = QLabel("准备金: 20%")
            for lbl in [self.consecutive_label, self.cooldown_label, self.reserve_label]:
                lbl.setObjectName("captionLabel")
                layout.addWidget(lbl)
            self.review_btn = QPushButton("交易复盘")
            self.review_btn.setObjectName("ghostBtn")
            layout.addWidget(self.review_btn)
        else:
            self.consecutive_label = None
            self.cooldown_label = None
            self.reserve_label = None
            self.review_btn = None

        root.addWidget(self._card)

    def _refresh_theme(self):
        t = Theme.colors()
        self._card.setStyleSheet(Theme.card_style())
        self.status_label.setStyleSheet(
            f"font-size:12px; font-weight:600; color:{t['success']}; "
            f"background:transparent; padding:2px 8px; border-radius:4px;")
        bar_style = (
            f"QProgressBar {{ background:{t['progress_bg']}; border:none; "
            f"border-radius:4px; min-height:8px; max-height:8px; }} "
            f"QProgressBar::chunk {{ background:{t['accent']}; border-radius:4px; }}"
        )
        for bar in [self.daily_loss_bar, self.daily_trades_bar, self.drawdown_bar]:
            bar.setStyleSheet(bar_style)

    def update_risk(self, risk_data: Dict):
        if not risk_data:
            return
        t = Theme.colors()
        is_allowed = risk_data.get("is_trading_allowed", True)
        review = risk_data.get("review_required", False)
        if not is_allowed and review:
            self.status_label.setText("强制复盘")
            c = t["danger"]
        elif not is_allowed:
            self.status_label.setText("交易禁止")
            c = t["danger"]
        else:
            self.status_label.setText("正常")
            c = t["success"]
        self.status_label.setStyleSheet(
            f"font-size:12px; font-weight:600; color:{c}; "
            f"background:transparent; padding:2px 8px; border-radius:4px;")

        dlr = abs(risk_data.get("daily_loss_ratio", 0))
        daily_pct = min(int(dlr / 0.05 * 100), 100)
        self.daily_loss_bar.setValue(daily_pct)
        self._daily_pct.setText(f"{daily_pct}%")

        dt = risk_data.get("daily_trades", 0)
        trades_pct = min(int(dt / 20 * 100), 100)
        self.daily_trades_bar.setValue(trades_pct)
        self._trades_pct.setText(f"{trades_pct}%")

        dd = risk_data.get("total_drawdown", 0)
        dd_pct = min(int(dd / 0.20 * 100), 100)
        self.drawdown_bar.setValue(dd_pct)
        self._dd_pct.setText(f"{dd_pct}%")

        for bar, pct in [
            (self.daily_loss_bar, daily_pct),
            (self.daily_trades_bar, trades_pct),
            (self.drawdown_bar, dd_pct),
        ]:
            color = t["danger"] if pct >= 80 else (
                t["warning"] if pct >= 60 else t["accent"])
            bar.setStyleSheet(
                f"QProgressBar {{ background:{t['progress_bg']}; border:none; "
                f"border-radius:4px; min-height:8px; max-height:8px; }} "
                f"QProgressBar::chunk {{ background:{color}; border-radius:4px; }}")

        if self.consecutive_label:
            cl = risk_data.get("consecutive_loss", 0)
            self.consecutive_label.setText(f"连续亏损: {cl}/3")
            co = risk_data.get("cooldown_remaining", 0)
            self.cooldown_label.setText(f"冷却: {co}s" if co > 0 else "冷却: 无")
