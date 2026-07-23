"""
API 设置详情页 — 匹配 UI 设计稿
连接状态 · 连接测试清单 · API 配置 · 安全提示
"""

import hmac
import hashlib
import json
import time
from pathlib import Path
from urllib.parse import urlencode

import requests

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QLineEdit, QPushButton, QFrame, QMessageBox,
                               QScrollArea, QGridLayout, QApplication)
from PyQt6.QtCore import Qt

from gui.styles import Theme
from config import Config
from utils.settings_store import load_json_settings, save_json_settings

SETTINGS_FILE = Config.PREFERENCES_DIR / "api.json"
LEGACY_SETTINGS_FILE = Path.home() / ".bn_trader_api.json"


def load_api_settings() -> dict:
    return load_json_settings(
        SETTINGS_FILE,
        {"api_key": "", "secret_key": "", "testnet": True},
        legacy_paths=[LEGACY_SETTINGS_FILE],
    )


def save_api_settings(api_key: str, secret_key: str, testnet: bool):
    save_json_settings(SETTINGS_FILE, {
        "api_key": api_key, "secret_key": secret_key, "testnet": testnet,
    }, sensitive=True)


class ApiSettingsPage(QWidget):
    """嵌入主窗口的 API 设置页（也可用作对话框内容）"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._check_labels = {}
        self._latency = "—"
        self._connected = False
        self._init_ui()
        self._load_current()
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
        content.setObjectName("apiPageContent")
        content.setMaximumWidth(1080)
        scroll.setWidget(content)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # 标题
        title = QLabel("API 设置")
        title.setStyleSheet("font-size:18px; font-weight:700;")
        layout.addWidget(title)

        # ---- 连接状态卡片 ----
        self._status_card = self._make_card()
        self._status_card.setMaximumWidth(1040)
        sl = QVBoxLayout(self._status_card)
        sl.setContentsMargins(16, 14, 16, 14)
        sl.setSpacing(10)

        sh = QHBoxLayout()
        st = QLabel("API 连接状态")
        st.setObjectName("sectionTitle")
        sh.addWidget(st)
        sh.addStretch()
        self._status_badge = QLabel("未连接")
        sh.addWidget(self._status_badge)
        sl.addLayout(sh)

        grid = QGridLayout()
        grid.setSpacing(12)
        self._server_time_lbl = QLabel("—")
        self._latency_lbl = QLabel("—")
        self._perm_lbl = QLabel("—")
        for i, (cap, val) in enumerate([
            ("服务器时间", self._server_time_lbl),
            ("延迟", self._latency_lbl),
            ("权限", self._perm_lbl),
        ]):
            c = QLabel(cap)
            c.setObjectName("dimLabel")
            grid.addWidget(c, 0, i)
            val.setStyleSheet("font-size:14px; font-weight:600;")
            grid.addWidget(val, 1, i)
        sl.addLayout(grid)

        test_btn = QPushButton("测试连接")
        test_btn.setObjectName("primaryBtn")
        test_btn.setFixedWidth(120)
        test_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        test_btn.clicked.connect(self._test_connection)
        sl.addWidget(test_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        # ---- 连接测试清单 ----
        self._check_card = self._make_card()
        self._check_card.setMaximumWidth(1040)
        cl = QVBoxLayout(self._check_card)
        cl.setContentsMargins(16, 14, 16, 14)
        cl.setSpacing(8)
        ct = QLabel("连接测试")
        ct.setObjectName("sectionTitle")
        cl.addWidget(ct)

        for key, name in [
            ("api_key", "API Key"),
            ("secret", "Secret Key"),
            ("server", "服务器连接"),
            ("perm", "账户权限"),
            ("time", "时间同步"),
        ]:
            row = QHBoxLayout()
            row.addWidget(QLabel(name))
            row.addStretch()
            lbl = QLabel("待检测")
            lbl.setObjectName("dimLabel")
            self._check_labels[key] = lbl
            row.addWidget(lbl)
            cl.addLayout(row)

        retest = QPushButton("重新测试")
        retest.setObjectName("ghostBtn")
        retest.setFixedWidth(100)
        retest.clicked.connect(self._test_connection)
        cl.addWidget(retest, alignment=Qt.AlignmentFlag.AlignLeft)
        top_cards = QHBoxLayout()
        top_cards.setSpacing(12)
        top_cards.addWidget(self._status_card, 1)
        top_cards.addWidget(self._check_card, 1)
        layout.addLayout(top_cards)

        # ---- API 配置 ----
        self._cfg_card = self._make_card()
        self._cfg_card.setMaximumWidth(1040)
        cfg = QVBoxLayout(self._cfg_card)
        cfg.setContentsMargins(16, 14, 16, 14)
        cfg.setSpacing(10)
        cfg.addWidget(self._section("API 配置"))

        cfg.addWidget(self._caption("API Key"))
        key_row = QHBoxLayout()
        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("粘贴你的 API Key")
        self.key_input.setEchoMode(QLineEdit.EchoMode.Password)
        key_row.addWidget(self.key_input, 1)
        self._key_toggle = QPushButton("显示")
        self._key_toggle.setObjectName("textBtn")
        self._key_toggle.setFixedWidth(48)
        self._key_toggle.clicked.connect(
            lambda: self._toggle_echo(self.key_input, self._key_toggle))
        key_row.addWidget(self._key_toggle)
        key_copy = QPushButton("复制")
        key_copy.setObjectName("textBtn")
        key_copy.setFixedWidth(48)
        key_copy.clicked.connect(
            lambda: QApplication.clipboard().setText(self.key_input.text()))
        key_row.addWidget(key_copy)
        cfg.addLayout(key_row)

        cfg.addWidget(self._caption("Secret Key"))
        sec_row = QHBoxLayout()
        self.secret_input = QLineEdit()
        self.secret_input.setPlaceholderText("粘贴你的 Secret Key")
        self.secret_input.setEchoMode(QLineEdit.EchoMode.Password)
        sec_row.addWidget(self.secret_input, 1)
        self._sec_toggle = QPushButton("显示")
        self._sec_toggle.setObjectName("textBtn")
        self._sec_toggle.setFixedWidth(48)
        self._sec_toggle.clicked.connect(
            lambda: self._toggle_echo(self.secret_input, self._sec_toggle))
        sec_row.addWidget(self._sec_toggle)
        sec_copy = QPushButton("复制")
        sec_copy.setObjectName("textBtn")
        sec_copy.setFixedWidth(48)
        sec_copy.clicked.connect(
            lambda: QApplication.clipboard().setText(self.secret_input.text()))
        sec_row.addWidget(sec_copy)
        cfg.addLayout(sec_row)
        layout.addWidget(self._cfg_card)

        # ---- 安全提示 ----
        self._tip = QLabel(
            "⚠ 安全提示\n"
            "· API Key 仅保存在系统用户数据目录，产品升级不会覆盖\n"
            "· 建议仅开启「现货交易」权限，切勿开启「提现」权限\n"
            "· 请勿将 API Key 分享给任何人"
        )
        self._tip.setWordWrap(True)
        self._tip.setMaximumWidth(1040)
        layout.addWidget(self._tip)

        # ---- 底部操作 ----
        btn_row = QHBoxLayout()
        self._del_btn = QPushButton("删除 API")
        self._del_btn.setObjectName("dangerBtn")
        self._del_btn.clicked.connect(self._delete_api)
        btn_row.addWidget(self._del_btn)
        btn_row.addStretch()
        self._cancel_btn = QPushButton("取消")
        self._cancel_btn.setObjectName("ghostBtn")
        btn_row.addWidget(self._cancel_btn)
        self._save_btn = QPushButton("保存")
        self._save_btn.setObjectName("primaryBtn")
        self._save_btn.clicked.connect(self._save)
        btn_row.addWidget(self._save_btn)
        layout.addLayout(btn_row)
        layout.addStretch()

        self.saved = False  # 供外部查询

    # helpers
    def _make_card(self) -> QFrame:
        f = QFrame()
        f.setObjectName("cardFrame")
        return f

    def _section(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("sectionTitle")
        return lbl

    def _caption(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("captionLabel")
        return lbl

    def _toggle_echo(self, inp: QLineEdit, btn: QPushButton):
        if inp.echoMode() == QLineEdit.EchoMode.Password:
            inp.setEchoMode(QLineEdit.EchoMode.Normal)
            btn.setText("隐藏")
        else:
            inp.setEchoMode(QLineEdit.EchoMode.Password)
            btn.setText("显示")

    def _refresh_theme(self):
        t = Theme.colors()
        self._content.setStyleSheet(
            f"QWidget#apiPageContent {{ background:{t['bg_main']}; }}")
        parent = self._content.parentWidget()
        if parent:
            parent.setStyleSheet(
                f"QWidget#{parent.objectName()} {{ background:{t['bg_main']}; }}")
        for card in [self._status_card, self._check_card, self._cfg_card]:
            card.setStyleSheet(Theme.card_style())
        self._tip.setStyleSheet(
            f"font-size:12px; padding:12px 14px; border-radius:6px; "
            f"color:{t['warning']}; background:{t['tip_bg']}; "
            f"border:1px solid {t['tip_border']};")
        self._update_status_badge()

    def _update_status_badge(self):
        t = Theme.colors()
        if self._connected:
            self._status_badge.setText("● 已连接")
            self._status_badge.setStyleSheet(
                f"color:{t['success']}; font-weight:600; font-size:13px; "
                f"background:transparent; padding:2px 10px; border-radius:4px;")
        else:
            self._status_badge.setText("○ 未连接")
            self._status_badge.setStyleSheet(
                f"color:{t['text_secondary']}; font-weight:600; font-size:13px; "
                f"background:{t['divider']}; padding:2px 10px; border-radius:4px;")

    def _set_check(self, key: str, ok: bool, text: str = None):
        t = Theme.colors()
        lbl = self._check_labels.get(key)
        if not lbl:
            return
        if text:
            lbl.setText(text)
        else:
            lbl.setText("✓ 正常" if ok else "✗ 失败")
        lbl.setStyleSheet(
            f"font-size:12px; font-weight:600; color:{t['success'] if ok else t['danger']};")

    def _load_current(self):
        c = load_api_settings()
        self.key_input.setText(c.get("api_key", ""))
        self.secret_input.setText(c.get("secret_key", ""))

    def _save(self):
        ak = self.key_input.text().strip()
        sk = self.secret_input.text().strip()
        if not ak or not sk:
            QMessageBox.warning(self, "提示", "请填写完整的 API Key 和 Secret Key")
            return
        save_api_settings(ak, sk, testnet=False)
        self._write_env(ak, sk)
        self.saved = True
        QMessageBox.information(self, "成功", "API 配置已保存！")

    def _delete_api(self):
        r = QMessageBox.question(self, "确认", "确定删除本地 API 配置？")
        if r != QMessageBox.StandardButton.Yes:
            return
        self.key_input.clear()
        self.secret_input.clear()
        if SETTINGS_FILE.exists():
            SETTINGS_FILE.unlink()
        self._remove_env_keys()
        self._connected = False
        self._update_status_badge()
        QMessageBox.information(self, "已删除", "API 配置已清除")

    def _test_connection(self):
        ak = self.key_input.text().strip()
        sk = self.secret_input.text().strip()
        if not ak or not sk:
            QMessageBox.warning(self, "提示", "请先填写 API Key 和 Secret Key")
            return

        self._set_check("api_key", bool(ak), "✓ 有效" if ak else "✗ 无效")
        self._set_check("secret", bool(sk), "✓ 有效" if sk else "✗ 无效")

        try:
            t0 = time.time()
            params = {"timestamp": int(time.time() * 1000)}
            query = urlencode(params)
            sig = hmac.new(sk.encode(), query.encode(), hashlib.sha256).hexdigest()
            r = requests.get(
                "https://api.binance.com/api/v3/account",
                params={**params, "signature": sig},
                headers={"X-MBX-APIKEY": ak}, timeout=10,
            )
            latency = int((time.time() - t0) * 1000)
            self._latency_lbl.setText(f"{latency} ms")

            if r.status_code == 200:
                account = r.json()
                server = requests.get(
                    "https://api.binance.com/api/v3/time", timeout=10).json()
                server_ms = int(server.get("serverTime", 0))
                drift = abs(server_ms - int(time.time() * 1000))
                self._connected = True
                self._set_check("server", True)
                can_trade = bool(account.get("canTrade", False))
                self._set_check(
                    "perm", can_trade,
                    "✓ 现货交易" if can_trade else "✗ 无交易权限")
                self._set_check(
                    "time", drift <= 1000,
                    f"✓ 偏差 {drift}ms" if drift <= 1000 else f"✗ 偏差 {drift}ms")
                self._perm_lbl.setText(
                    "现货交易 读/写" if can_trade else "只读 / 禁止交易")
                from datetime import datetime
                self._server_time_lbl.setText(
                    datetime.fromtimestamp(server_ms / 1000).strftime(
                        "%Y-%m-%d %H:%M:%S"))
                self._update_status_badge()
                QMessageBox.information(self, "测试结果", f"连接成功！延迟 {latency}ms")
            else:
                self._connected = False
                self._set_check("server", False)
                self._set_check("perm", False)
                self._update_status_badge()
                QMessageBox.warning(self, "测试失败", f"API ({r.status_code}): {r.text[:200]}")
        except Exception as e:
            self._connected = False
            self._set_check("server", False)
            self._update_status_badge()
            QMessageBox.warning(self, "连接失败", str(e))

    def _write_env(self, ak: str, sk: str):
        env = Config.PREFERENCES_DIR / ".env"
        lines = env.read_text(encoding="utf-8").splitlines() if env.exists() else []
        out, rk, rs = [], False, False
        for l in lines:
            if l.startswith("BINANCE_API_KEY="):
                out.append(f"BINANCE_API_KEY={ak}"); rk = True
            elif l.startswith("BINANCE_SECRET_KEY="):
                out.append(f"BINANCE_SECRET_KEY={sk}"); rs = True
            else:
                out.append(l)
        if not rk:
            out.append(f"BINANCE_API_KEY={ak}")
        if not rs:
            out.append(f"BINANCE_SECRET_KEY={sk}")
        env.write_text("\n".join(out) + "\n", encoding="utf-8")
        try:
            env.chmod(0o600)
        except OSError:
            pass

    def _remove_env_keys(self):
        env = Config.PREFERENCES_DIR / ".env"
        if not env.exists():
            return
        lines = [
            line for line in env.read_text().splitlines()
            if not line.startswith(("BINANCE_API_KEY=", "BINANCE_SECRET_KEY="))
        ]
        env.write_text(
            "\n".join(lines) + ("\n" if lines else ""),
            encoding="utf-8",
        )


# 保留对话框包装，兼容旧调用
class ApiSettingsDialog:
    """兼容包装：以独立对话框形式打开 API 设置"""

    DialogCode = type("DC", (), {"Accepted": 1, "Rejected": 0})()

    def __init__(self, parent=None):
        from PyQt6.QtWidgets import QDialog, QVBoxLayout as VL
        self._dlg = QDialog(parent)
        self._dlg.setWindowTitle("API 设置")
        self._dlg.resize(560, 720)
        lay = VL(self._dlg)
        lay.setContentsMargins(0, 0, 0, 0)
        self._page = ApiSettingsPage(self._dlg)
        self._page._cancel_btn.clicked.connect(self._dlg.reject)
        lay.addWidget(self._page)
        t = Theme.colors()
        self._dlg.setStyleSheet(f"background:{t['bg_main']};")

    def exec(self):
        # 覆盖 page 内置的 save 连接，保存成功后关闭对话框
        try:
            self._page._save_btn.clicked.disconnect()
        except TypeError:
            pass
        self._page._save_btn.clicked.connect(self._save_and_close)
        return self._dlg.exec()

    def _save_and_close(self):
        self._page._save()
        if self._page.saved:
            self._dlg.accept()
