#!/usr/bin/env python3
"""
BN-Trader 跨平台安裝腳本

支援 Windows / macOS / Linux
用法: python install.py
"""

import subprocess
import sys
import os
import platform
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
VENV_DIR = PROJECT_ROOT / ".venv"

REQUIREMENTS = [
    "PyQt6>=6.4.0",
    "pyqtgraph>=0.13.0",
    "requests>=2.28.0",
    "websocket-client>=1.4.0",
    "numpy>=1.23.0",
    "pandas>=1.5.0",
    "SQLAlchemy>=2.0.0",
    "python-dotenv>=0.21.0",
    "pytest>=7.2.0",
    "pyinstaller>=5.0.0",
]


def get_python() -> str:
    """取得可用的 Python 直譯器"""
    candidates = ["python3", "python"]
    for cmd in candidates:
        try:
            result = subprocess.run(
                [cmd, "--version"], capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                return cmd
        except FileNotFoundError:
            continue
    print("[錯誤] 未找到 Python，請安裝 Python 3.10+")
    print("下載: https://www.python.org/downloads/")
    sys.exit(1)


def get_activate_cmd() -> str:
    """取得虛擬環境啟動命令"""
    system = platform.system()
    if system == "Windows":
        return str(VENV_DIR / "Scripts" / "activate")
    return f"source {VENV_DIR / 'bin' / 'activate'}"


def run_cmd(cmd: str | list, shell: bool = False) -> int:
    """執行命令"""
    print(f"  執行: {cmd}")
    if isinstance(cmd, list):
        return subprocess.run(cmd).returncode
    return subprocess.run(cmd, shell=shell, executable="/bin/bash" if platform.system() != "Windows" else None).returncode


def verify_installation() -> bool:
    """驗證安裝"""
    checks = [
        ("PyQt6", "import PyQt6; print('  PyQt6:', PyQt6.QtCore.PYQT_VERSION_STR)"),
        ("NumPy", "import numpy; print('  NumPy:', numpy.__version__)"),
        ("Pandas", "import pandas; print('  Pandas:', pandas.__version__)"),
        ("SQLAlchemy", "import sqlalchemy; print('  SQLAlchemy:', sqlalchemy.__version__)"),
        ("Requests", "import requests; print('  Requests:', requests.__version__)"),
    ]
    ok = True
    for name, code in checks:
        try:
            subprocess.run([sys.executable, "-c", code], check=True)
        except subprocess.CalledProcessError:
            print(f"  [FAIL] {name}")
            ok = False
    return ok


def main():
    system = platform.system()
    print("=== BN-Trader 跨平台安裝 ===")
    print(f"操作系統: {system} {platform.release()}")
    print(f"Python: {sys.version}")
    print()

    # Step 1: 建立虛擬環境
    print("[1/3] 建立虛擬環境...")
    if VENV_DIR.exists():
        print(f"  虚擬環境已存在: {VENV_DIR}")
    else:
        rc = run_cmd([sys.executable, "-m", "venv", str(VENV_DIR)])
        if rc != 0:
            print("[錯誤] 虚擬環境建立失敗")
            sys.exit(1)

    # Step 2: 安裝依賴
    print("[2/3] 安裝依賴...")
    pip = str(VENV_DIR / ("Scripts" if system == "Windows" else "bin") / "pip")
    for pkg in REQUIREMENTS:
        run_cmd([pip, "install", pkg])

    # Step 3: 驗證
    print("[3/3] 驗證安裝...")
    # 切換到 venv 的 python
    venv_python = str(VENV_DIR / ("Scripts" if system == "Windows" else "bin") / "python")
    # Temporarily switch sys.executable for verification
    old_exe = sys.executable
    sys.executable = venv_python
    ok = verify_installation()
    sys.executable = old_exe

    print()
    if ok:
        print("=== 安裝成功! ===")
        activate = get_activate_cmd()
        print(f"\n啟動方式:")
        if system == "Windows":
            print(f"  {VENV_DIR}\\Scripts\\activate")
        else:
            print(f"  source {VENV_DIR}/bin/activate")
        print("  python main.py")
    else:
        print("=== 安裝出現問題，請檢查上方輸出 ===")


if __name__ == "__main__":
    main()
