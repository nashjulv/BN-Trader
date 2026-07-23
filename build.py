#!/usr/bin/env python3
"""
BN-Trader 跨平台构建脚本

用法:
    python build.py              # 构建当前平台的安装包
    python build.py --clean      # 清理后重新构建
    python build.py --onefile    # 构建单文件可执行程序
    python build.py --zip        # 构建并打包为 ZIP 分发包

输出:
    dist/BN-Trader/              # 文件夹形式（开发调试用）
    dist/BN-Trader.app/          # macOS .app 包
    dist/BN-Trader-{version}-{platform}.zip  # 分发包
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent.absolute()
DIST = ROOT / "dist"
BUILD = ROOT / "build"
SPEC = ROOT / "BN-Trader.spec"
VERSION = "1.0.0"


def get_platform_tag() -> str:
    """获取平台标识"""
    system = sys.platform
    if system == "win32":
        return "win64"
    elif system == "darwin":
        import platform
        arch = platform.machine()
        return "mac-arm64" if arch == "arm64" else "mac-x64"
    else:
        return "linux"


def run(cmd, **kwargs):
    """运行命令并打印"""
    print(f"  -> {' '.join(cmd) if isinstance(cmd, list) else cmd}")
    return subprocess.run(cmd, cwd=str(ROOT), **kwargs)


def check_pyinstaller():
    """检查 PyInstaller 是否可用"""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "PyInstaller", "--version"],
            capture_output=True, text=True
        )
        print(f"  PyInstaller {result.stdout.strip()}")
        return True
    except FileNotFoundError:
        print("  [错误] 未安装 PyInstaller，请运行: pip install pyinstaller")
        return False


def clean():
    """清理构建产物"""
    for d in [DIST, BUILD]:
        if d.exists():
            print(f"  清理 {d}")
            shutil.rmtree(d)
    for p in ROOT.glob("*.spec"):
        if p != SPEC:
            p.unlink()
    for ext in [".pyc", ".pyo"]:
        for f in ROOT.rglob(f"*{ext}"):
            f.unlink()


def build(args):
    """构建可执行程序"""
    print("\n" + "=" * 60)
    print(f"  BN-Trader v{VERSION} 构建")
    print(f"  平台: {get_platform_tag()}")
    print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60 + "\n")

    # 步骤 1: 检查环境
    print("[1/4] 检查构建环境...")
    if not check_pyinstaller():
        sys.exit(1)
    print(f"  Python: {sys.version}")
    print("  ✅ 环境就绪\n")

    # 步骤 2: 清理
    if args.clean:
        print("[2/4] 清理旧构建...")
        clean()
        print("  ✅ 清理完成\n")
    else:
        print("[2/4] 跳过清理（加 --clean 强制清理）\n")

    # 步骤 3: PyInstaller 构建
    print("[3/4] 开始 PyInstaller 构建...")
    pyi_cmd = [
        sys.executable, "-m", "PyInstaller",
        str(SPEC),
        "--noconfirm",
        "--distpath", str(DIST),
        "--workpath", str(BUILD),
        "--specpath", str(ROOT),
    ]

    if args.onefile:
        pyi_cmd.append("--onefile")

    result = run(pyi_cmd)
    if result.returncode != 0:
        print("\n  [错误] 构建失败!")
        sys.exit(1)
    print("  ✅ PyInstaller 构建完成\n")

    # 步骤 4: 打包分发
    print("[4/4] 打包分发...")
    platform_tag = get_platform_tag()
    zip_name = f"BN-Trader-v{VERSION}-{platform_tag}"

    if sys.platform == "darwin":
        # macOS: 已经生成 .app bundle
        app_dir = DIST / "BN-Trader.app"
        if app_dir.exists():
            print(f"  macOS .app: {app_dir}")
            # 创建 DMG (需要 create-dmg)
            if shutil.which("create-dmg"):
                dmg_name = f"{zip_name}.dmg"
                run([
                    "create-dmg",
                    "--volname", "BN-Trader",
                    "--window-pos", "200", "120",
                    "--window-size", "600", "400",
                    "--app-drop-link", "425", "120",
                    str(DIST / dmg_name),
                    str(app_dir),
                ])
                print(f"  DMG: {DIST / dmg_name}")
            else:
                # 回退到 ZIP
                shutil.make_archive(
                    str(DIST / zip_name), "zip",
                    str(DIST), "BN-Trader.app"
                )
                print(f"  ZIP: {DIST / zip_name}.zip")

    elif sys.platform == "win32":
        # Windows: 打包文件夹
        app_dir = DIST / "BN-Trader"
        if app_dir.exists():
            shutil.make_archive(
                str(DIST / zip_name), "zip",
                str(DIST), "BN-Trader"
            )
            print(f"  ZIP: {DIST / zip_name}.zip")

    else:
        # Linux
        app_dir = DIST / "BN-Trader"
        if app_dir.exists():
            shutil.make_archive(
                str(DIST / zip_name), "zip",
                str(DIST), "BN-Trader"
            )
            print(f"  ZIP: {DIST / zip_name}.zip")

    # 复制 .env 模板到发布目录
    env_src = ROOT / ".env.example"
    if env_src.exists():
        for app in DIST.glob("BN-Trader*"):
            if app.is_dir():
                dest = app / ".env.example"
                shutil.copy(env_src, dest)
            elif sys.platform == "darwin" and app.suffix == ".app":
                dest = app / "Contents" / "MacOS" / ".env.example"
                shutil.copy(env_src, dest)

    print("  ✅ 打包完成\n")

    # 输出结果
    print("=" * 60)
    print("  构建产物:")
    for item in sorted(DIST.iterdir()):
        if item.is_dir():
            size = sum(f.stat().st_size for f in item.rglob("*"))
        else:
            size = item.stat().st_size
        print(f"    {item.name}  ({_format_size(size)})")
    print("=" * 60)


def _format_size(size: int) -> str:
    """格式化文件大小"""
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}TB"


def main():
    parser = argparse.ArgumentParser(description="BN-Trader 构建脚本")
    parser.add_argument("--clean", action="store_true", help="清理后重新构建")
    parser.add_argument("--onefile", action="store_true", help="构建单文件可执行程序")
    parser.add_argument("--zip", action="store_true", help="仅打包已构建的产物")
    args = parser.parse_args()

    if args.zip:
        # 仅打包
        platform_tag = get_platform_tag()
        zip_name = f"BN-Trader-v{VERSION}-{platform_tag}"

        app_dir = DIST / "BN-Trader.app" if sys.platform == "darwin" else DIST / "BN-Trader"
        if not app_dir.exists():
            print(f"[错误] 未找到构建产物: {app_dir}")
            print("请先运行: python build.py")
            sys.exit(1)

        shutil.make_archive(
            str(DIST / zip_name), "zip",
            str(DIST), app_dir.name
        )
        print(f"打包完成: {DIST / zip_name}.zip")
    else:
        build(args)


if __name__ == "__main__":
    main()
