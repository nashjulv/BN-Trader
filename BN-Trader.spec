# -*- mode: python ; coding: utf-8 -*-
"""
BN-Trader PyInstaller spec 文件
构建独立可执行程序

用法:
    pyinstaller BN-Trader.spec          # 构建当前平台
    pyinstaller --clean BN-Trader.spec  # 清理构建
"""

import sys
import os
from pathlib import Path

# ---------- 基础路径 ----------
ROOT = Path(__file__).parent.absolute()
ENTRY = str(ROOT / "main.py")
NAME = "BN-Trader"
ICON_WIN = str(ROOT / "assets" / "icon.ico")
ICON_MAC = str(ROOT / "assets" / "icon.icns")

# ---------- 隐藏导入 ----------
# 列出所有需要 PyInstaller 显式收集的模块
hidden_imports = [
    # 项目内部模块
    "core", "core.app", "core.database",
    "models", "models.capital", "models.trade", "models.risk", "models.scene",
    "services", "services.binance_client", "services.scene_detector",
    "services.capital_pool", "services.risk_manager", "services.strategy_engine",
    "strategies", "strategies.base", "strategies.trending",
    "strategies.ranging", "strategies.breakout", "strategies.reversal",
    "indicators", "indicators.technical",
    "gui", "gui.main_window", "gui.chart_widget", "gui.trade_panel",
    "gui.capital_panel", "gui.scene_panel", "gui.risk_panel",
    "gui.position_panel", "gui.log_panel", "gui.review_dialog", "gui.styles",
    "utils", "utils.logger", "utils.helpers",
    # 第三方库
    "PyQt6", "PyQt6.QtCore", "PyQt6.QtGui", "PyQt6.QtWidgets",
    "pyqtgraph",
    "numpy", "numpy._core", "numpy.linalg",
    "pandas", "pandas._libs",
    "sqlalchemy", "sqlalchemy.dialects.sqlite",
    "requests", "urllib3",
    "websocket",
    "dotenv",
]

# ---------- 排除项 ----------
excludes = [
    "tkinter", "matplotlib", "scipy", "PIL",
    "pytest", "setuptools", "pip",
]

# ---------- Platform-specific ----------
platform_specific = []
icon_path = None

if sys.platform == "darwin":
    platform_specific = [
        ("--osx-bundle-identifier", "com.bntrader.app"),
    ]
    icon_path = ICON_MAC if os.path.exists(ICON_MAC) else None
elif sys.platform == "win32":
    icon_path = ICON_WIN if os.path.exists(ICON_WIN) else None

# ==================== PyInstaller Analysis ====================
a = Analysis(
    [ENTRY],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        # 配置文件模板
        (str(ROOT / ".env.example"), "."),
        # 图标文件（给 NSIS 等打包工具用）
        (str(ROOT / "assets" / "icon.png"), "assets"),
        (str(ROOT / "assets" / "icon.ico"), "."),
        (str(ROOT / "README.md"), "."),
    ],
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)

# ==================== Filter unnecessary Qt stuff ====================
pyz = PYZ(a.pure)

# ==================== Single-folder bundle ====================
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,  # macOS 签名前不要 strip
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # 不显示控制台
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_path,
)

# ==================== Directory bundle ====================
# Windows/Linux 安装程序需要完整目录，macOS BUNDLE 也基于该目录构建。
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name=NAME,
)

# ==================== macOS .app bundle ====================
if sys.platform == "darwin":
    _ent = str(ROOT / "packagers" / "entitlements.plist")
    app = BUNDLE(
        coll,
        name=f"{NAME}.app",
        icon=icon_path,
        bundle_identifier="com.bntrader.app",
        entitlements_file=_ent if os.path.exists(_ent) else None,
        info_plist={
            "NSPrincipalClass": "NSApplication",
            "NSHighResolutionCapable": "True",
            "CFBundleName": NAME,
            "CFBundleDisplayName": "BN-Trader 短线交易系统",
            "CFBundleShortVersionString": "1.0.0",
            "CFBundleVersion": "1.0.0",
            "CFBundlePackageType": "APPL",
            "LSMinimumSystemVersion": "10.15",
            "NSHumanReadableCopyright": "BN-Trader",
        },
    )

# ==================== Cleanup ====================
# 单文件夹模式：dist/BN-Trader/ 下即可运行
# macOS: dist/BN-Trader.app
# Windows: dist/BN-Trader/BN-Trader.exe
