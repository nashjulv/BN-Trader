#!/usr/bin/env python3
"""
BN-Trader 原生安装包打包系统

统一编排 PyInstaller 构建 + 各平台原生安装包生成。

用法:
    python package.py                          # 构建当前平台安装包
    python package.py --platform win64         # 交叉打包 Windows
    python package.py --platform mac-arm64     # 交叉打包 macOS ARM
    python package.py --platform linux         # 交叉打包 Linux
    python package.py --all                    # 构建所有平台(仅限 CI)

输出:
    dist/BN-Trader-Setup-1.0.0.exe             # Windows NSIS 安装程序
    dist/BN-Trader-1.0.0-arm64.dmg             # macOS DMG 镜像
    dist/BN-Trader-1.0.0-x86_64.AppImage       # Linux AppImage
    dist/BN-Trader-1.0.0.deb                   # Linux DEB 包

依赖:
    pip install pyinstaller
    Windows:    安装 NSIS (https://nsis.sourceforge.io/)
    macOS:      brew install create-dmg
    Linux:      sudo apt install appimagetool fpm
"""

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# ---------- 常量 ----------
ROOT = Path(__file__).parent.absolute()
SRC = ROOT
DIST = ROOT / "dist"
BUILD = ROOT / "build"
PACKAGERS = ROOT / "packagers"
ASSETS = ROOT / "assets"
SPEC = ROOT / "BN-Trader.spec"
VERSION = os.getenv("BN_TRADER_VERSION", "1.0.0").removeprefix("v")
APP_NAME = "BN-Trader"
DISPLAY_NAME = "BN-Trader 短线交易系统"
PUBLISHER = "BN-Trader"
WEBSITE = "https://github.com/BN-Trader"

# ---------- 平台元数据 ----------
PLATFORM_META = {
    "win64": {
        "os": "Windows",
        "arch": "x64",
        "ext": ".exe",
        "pyi_target": "win64",
        "formats": ["nsis", "portable"],
    },
    "mac-arm64": {
        "os": "Darwin",
        "arch": "arm64",
        "ext": "",
        "pyi_target": "mac-arm64",
        "formats": ["dmg", "app"],
    },
    "mac-x64": {
        "os": "Darwin",
        "arch": "x64",
        "ext": "",
        "pyi_target": "mac-x64",
        "formats": ["dmg", "app"],
    },
    "linux": {
        "os": "Linux",
        "arch": "x64",
        "ext": "",
        "pyi_target": "linux",
        "formats": ["appimage", "deb"],
    },
}


# ==================================================================
#  工具函数
# ==================================================================

def _sh(cmd, **kw):
    """运行命令，自动打印"""
    flat = " ".join(cmd) if isinstance(cmd, list) else cmd
    print(f"  → {flat}")
    return subprocess.run(cmd, cwd=str(ROOT), shell=isinstance(cmd, str), **kw)


def _fmt_size(size: int) -> str:
    for u in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f} {u}"
        size /= 1024
    return f"{size:.1f} TB"


def _check_tool(name: str, install_hint: str) -> bool:
    ok = shutil.which(name) is not None
    if not ok:
        print(f"  ⚠ 未找到 {name} — {install_hint}")
    return ok


def _require_pyinstaller():
    r = subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--version"],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        print("  ✗ 未安装 PyInstaller → pip install pyinstaller")
        return False
    print(f"  PyInstaller {r.stdout.strip()}")
    return True


# ==================================================================
#  阶段 1：PyInstaller 构建
# ==================================================================

def pyinstaller_build(platform_tag: str, onefile: bool = False) -> Path | None:
    """运行 PyInstaller，返回产物路径"""
    print("\n" + "─" * 60)
    print("  阶段 1/3: PyInstaller 构建")
    print("─" * 60 + "\n")

    if not _require_pyinstaller():
        return None

    print("  同步产品资料与系统帮助...")
    docs_result = _sh([sys.executable, str(ROOT / "tools" / "generate_help_docs.py")])
    if docs_result.returncode != 0:
        print("  ✗ 帮助文档生成失败")
        return None

    # 生成图标（如果没有）
    icon_png = ASSETS / "icon.png"
    if not icon_png.exists():
        print("  生成默认图标...")
        _sh([sys.executable, str(ROOT / "generate_icons.py")])

    pyi_cmd = [
        sys.executable, "-m", "PyInstaller",
        str(SPEC),
        "--noconfirm",
        "--clean",
        "--distpath", str(DIST),
        "--workpath", str(BUILD),
    ]
    if onefile:
        pyi_cmd.append("--onefile")

    r = _sh(pyi_cmd)
    if r.returncode != 0:
        print("\n  ✗ PyInstaller 构建失败!")
        return None

    # 找到构建产物
    candidates = [
        DIST / APP_NAME / f"{APP_NAME}.exe",    # Windows folder
        DIST / f"{APP_NAME}.exe",                # Windows onefile
        DIST / f"{APP_NAME}.app",                # macOS
        DIST / APP_NAME / APP_NAME,              # Linux folder
        DIST / APP_NAME,                         # Linux onefile
    ]
    for c in candidates:
        if c.exists():
            print(f"  ✓ PyInstaller 产物: {c}")
            return c
    return None


# ==================================================================
#  阶段 2：额外文件（.env, README 等）
# ==================================================================

def prepare_payload(app_dir: Path):
    """将配置文件、README 复制到安装目录"""
    print("\n" + "─" * 60)
    print("  阶段 2/3: 准备发布文件")
    print("─" * 60 + "\n")

    # 读写文件映射 (src → dst)
    extras = {
        ROOT / ".env.example": ".env.example",
        ROOT / "README.md": "README.txt",
    }

    # 如果是 .app 包，复制到 Contents/Resources/
    if app_dir.suffix == ".app":
        resources = app_dir / "Contents" / "Resources"
        resources.mkdir(exist_ok=True)
        for src, name in extras.items():
            if src.exists():
                shutil.copy2(src, resources / name)
                print(f"  ✓ {name} → Resources/")
    else:
        # 普通文件夹
        for src, name in extras.items():
            if src.exists():
                shutil.copy2(src, app_dir.parent / name if app_dir.is_file() else app_dir / name)
                print(f"  ✓ {name}")


# ==================================================================
#  阶段 3a：Windows — NSIS 安装程序
# ==================================================================

def build_windows_installer(app_dir: Path) -> Path | None:
    """生成 BN-Trader-Setup.exe"""
    print("\n" + "─" * 60)
    print("  阶段 3/3: Windows NSIS 安装程序")
    print("─" * 60 + "\n")

    # 检查 NSIS
    nsis_paths = [
        r"C:\Program Files (x86)\NSIS\makensis.exe",
        r"C:\Program Files\NSIS\makensis.exe",
    ]
    makensis = None
    for p in nsis_paths:
        if Path(p).exists():
            makensis = p
            break
    if not makensis:
        makensis = shutil.which("makensis")

    if not makensis:
        print("  ✗ 未找到 NSIS (makensis)")
        print("  下载: https://nsis.sourceforge.io/Download")
        print("  跳过 NSIS 打包，生成便携版 ZIP...")
        return _make_portable_zip(app_dir, "win64")

    # 确保是文件夹形式（NSIS 需要文件夹）
    if app_dir.is_file():
        app_dir = app_dir.parent / APP_NAME
        if not app_dir.exists():
            print("  ✗ NSIS 需要文件夹形式的构建产物，请不加 --onefile 重新构建")
            return None

    # 写入 NSIS 脚本
    nsi_path = BUILD / "installer.nsi"
    _write_nsis_script(nsi_path, app_dir)

    print(f"  执行 makensis...")
    r = subprocess.run(
        [makensis, "/V2", str(nsi_path)],
        capture_output=True, text=True, cwd=str(ROOT)
    )
    if r.returncode != 0:
        print(f"  ✗ NSIS 错误:\n{r.stderr}")
        return None

    setup_exe = DIST / f"BN-Trader-Setup-{VERSION}.exe"
    if setup_exe.exists():
        size = setup_exe.stat().st_size
        print(f"  ✓ {setup_exe.name} ({_fmt_size(size)})")
        return setup_exe
    return None


def _write_nsis_script(nsi_path: Path, app_dir: Path):
    """生成 NSIS 安装脚本"""
    # 用 NSIS Modern UI 2
    nsi = rf'''; BN-Trader NSIS 安装脚本
; 自动生成于 {datetime.now()}

!include "MUI2.nsh"
!include "FileFunc.nsh"

; ---------- 基本信息 ----------
Name "{DISPLAY_NAME}"
OutFile "{DIST / f'BN-Trader-Setup-{VERSION}.exe'}"
InstallDir "$PROGRAMFILES\{APP_NAME}"
InstallDirRegKey HKLM "Software\{PUBLISHER}\{APP_NAME}" "InstallDir"
RequestExecutionLevel admin
SetCompressor /SOLID lzma

; ---------- Modern UI 配置 ----------
!define MUI_ABORTWARNING
!define MUI_ICON "{app_dir / 'icon.ico'}"
!define MUI_UNICON "{app_dir / 'icon.ico'}"

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "{ROOT / 'README.md'}"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "SimpChinese"
!insertmacro MUI_LANGUAGE "English"

; ---------- 安装段 ----------
Section "Install"
    SetOutPath "$INSTDIR"

    ; 复制所有程序文件
    File /r "{app_dir}\*.*"

    ; 创建开始菜单快捷方式
    CreateDirectory "$SMPROGRAMS\{APP_NAME}"
    CreateShortCut "$SMPROGRAMS\{APP_NAME}\{APP_NAME}.lnk" "$INSTDIR\{APP_NAME}.exe" "" "$INSTDIR\icon.ico"
    CreateShortCut "$SMPROGRAMS\{APP_NAME}\Uninstall.lnk" "$INSTDIR\uninstall.exe"

    ; 创建桌面快捷方式
    CreateShortCut "$DESKTOP\{APP_NAME}.lnk" "$INSTDIR\{APP_NAME}.exe" "" "$INSTDIR\icon.ico"

    ; 写入卸载信息
    WriteUninstaller "$INSTDIR\uninstall.exe"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\{APP_NAME}" "DisplayName" "{DISPLAY_NAME}"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\{APP_NAME}" "UninstallString" "$INSTDIR\uninstall.exe"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\{APP_NAME}" "DisplayVersion" "{VERSION}"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\{APP_NAME}" "Publisher" "{PUBLISHER}"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\{APP_NAME}" "DisplayIcon" "$INSTDIR\icon.ico"
    WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\{APP_NAME}" "NoModify" 1
    WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\{APP_NAME}" "NoRepair" 1

    ; 估算大小
    ${{GetSize}} "$INSTDIR" "/S=0K" $0 $1 $2
    WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\{APP_NAME}" "EstimatedSize" $0
SectionEnd

; ---------- 卸载段 ----------
Section "Uninstall"
    ; 删除程序文件
    RMDir /r "$INSTDIR"

    ; 删除快捷方式
    Delete "$SMPROGRAMS\{APP_NAME}\{APP_NAME}.lnk"
    Delete "$SMPROGRAMS\{APP_NAME}\Uninstall.lnk"
    RMDir "$SMPROGRAMS\{APP_NAME}"
    Delete "$DESKTOP\{APP_NAME}.lnk"

    ; 删除注册表
    DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\{APP_NAME}"
    DeleteRegKey HKLM "Software\{PUBLISHER}\{APP_NAME}"
SectionEnd
'''
    nsi_path.parent.mkdir(parents=True, exist_ok=True)
    nsi_path.write_text(nsi, encoding="utf-8")
    print(f"  生成 NSIS 脚本: {nsi_path}")


# ==================================================================
#  阶段 3b：macOS — DMG 镜像
# ==================================================================

def build_macos_dmg(app_dir: Path, arch: str) -> Path | None:
    """生成 macOS .dmg 安装镜像"""
    print("\n" + "─" * 60)
    print("  阶段 3/3: macOS DMG 镜像")
    print("─" * 60 + "\n")

    if not app_dir.suffix == ".app":
        print("  ✗ macOS 需要 .app bundle, 请不加 --onefile 重新构建")
        return None

    # 检查 create-dmg
    if not _check_tool("create-dmg", "brew install create-dmg"):
        print("  回退到 ZIP...")
        return _make_portable_zip(app_dir, f"mac-{arch}")

    # 对 .app 签名（如果证书存在）
    code_sign(app_dir)

    dmg_name = f"BN-Trader-{VERSION}-{arch}.dmg"
    dmg_path = DIST / dmg_name

    dmg_cmd = [
        "create-dmg",
        "--volname", f"BN-Trader {VERSION}",
        "--window-pos", "200", "120",
        "--window-size", "600", "400",
        "--icon-size", "100",
        "--icon", f"{APP_NAME}.app", "180", "170",
        "--app-drop-link", "420", "170",
        "--hide-extension", f"{APP_NAME}.app",
    ]
    icon_path = ASSETS / "icon.icns"
    background_path = PACKAGERS / "dmg_background.png"
    if icon_path.exists():
        dmg_cmd.extend(["--volicon", str(icon_path)])
    if background_path.exists():
        dmg_cmd.extend(["--background", str(background_path)])
    dmg_cmd.extend([str(dmg_path), str(app_dir)])

    r = _sh(dmg_cmd)

    if r.returncode == 0 and dmg_path.exists():
        size = dmg_path.stat().st_size
        print(f"  ✓ {dmg_path.name} ({_fmt_size(size)})")
        return dmg_path
    return None


def code_sign(app_dir: Path):
    """对 macOS .app 进行代码签名"""
    identity = os.getenv("APPLE_IDENTITY", "")
    if not identity:
        print("  ⚠ 未设置 APPLE_IDENTITY 环境变量，跳过代码签名")
        print("  export APPLE_IDENTITY='Developer ID Application: Your Name (XXXX)'")
        return

    print(f"  代码签名: {identity}")
    for cmd in [
        ["codesign", "--deep", "--force", "--verify", "--verbose",
         "--options", "runtime",
         "--entitlements", str(PACKAGERS / "entitlements.plist"),
         "--sign", identity, str(app_dir)],
        ["codesign", "--verify", "--verbose", str(app_dir)],
    ]:
        r = _sh(cmd)
        if r.returncode != 0:
            print(f"  ⚠ 签名命令失败: {' '.join(cmd)}")

    # 公证（如果设置了）
    apple_id = os.getenv("APPLE_ID", "")
    apple_password = os.getenv("APPLE_APP_PASSWORD", "")
    if apple_id and apple_password:
        print("  提交公证...")
        _sh([
            "xcrun", "notarytool", "submit",
            str(app_dir.parent / f"{app_dir.name}.zip"),
            "--apple-id", apple_id,
            "--password", apple_password,
            "--team-id", os.getenv("APPLE_TEAM_ID", ""),
            "--wait",
        ])


# ==================================================================
#  阶段 3c：Linux — AppImage + DEB
# ==================================================================

def build_linux_packages(app_dir: Path) -> list[Path]:
    """生成 Linux AppImage 和 DEB"""
    print("\n" + "─" * 60)
    print("  阶段 3/3: Linux 安装包")
    print("─" * 60 + "\n")

    results = []

    # AppImage
    appimage = _build_appimage(app_dir)
    if appimage:
        results.append(appimage)

    # DEB
    deb = _build_deb(app_dir)
    if deb:
        results.append(deb)

    if not results:
        results.append(_make_portable_zip(app_dir, "linux"))

    return results


def _build_appimage(app_dir: Path) -> Path | None:
    """构建 AppImage"""
    if not _check_tool("appimagetool", "sudo apt install appimagetool"):
        return None

    # 创建 AppDir 结构
    appdir = BUILD / "AppDir"
    if appdir.exists():
        shutil.rmtree(appdir)
    appdir.mkdir(parents=True)

    # 复制程序文件
    for item in app_dir.iterdir():
        dest = appdir / item.name
        if item.is_dir():
            shutil.copytree(item, dest)
        else:
            shutil.copy2(item, dest)

    # 创建 .desktop 文件
    desktop = appdir / f"{APP_NAME}.desktop"
    desktop.write_text(f"""[Desktop Entry]
Type=Application
Name={DISPLAY_NAME}
Exec={APP_NAME}
Icon={APP_NAME}
Categories=Finance;Office;
Comment=本地短线交易系统
""")

    # 创建图标
    icon_src = ASSETS / "icon.png"
    if icon_src.exists():
        shutil.copy2(icon_src, appdir / f"{APP_NAME}.png")

    # 创建 AppRun
    apprun = appdir / "AppRun"
    apprun.write_text(f"""#!/bin/bash
HERE="$(dirname "$(readlink -f "${{0}}")")"
export PATH="$HERE:$PATH"
exec "$HERE/{APP_NAME}" "$@"
""")
    apprun.chmod(0o755)

    arch = platform.machine()
    out = DIST / f"BN-Trader-{VERSION}-{arch}.AppImage"

    r = _sh([
        "appimagetool", str(appdir), str(out),
        "--no-appstream",
    ])
    if r.returncode == 0 and out.exists():
        out.chmod(0o755)
        size = out.stat().st_size
        print(f"  ✓ {out.name} ({_fmt_size(size)})")
        return out
    return None


def _build_deb(app_dir: Path) -> Path | None:
    """构建 DEB 包"""
    if not _check_tool("fpm", "gem install fpm 或 sudo apt install ruby-fpm"):
        return None

    # 创建安装目录结构
    pkgroot = BUILD / "deb-root"
    if pkgroot.exists():
        shutil.rmtree(pkgroot)

    installdir = pkgroot / "opt" / APP_NAME
    installdir.mkdir(parents=True)

    for item in app_dir.iterdir():
        dest = installdir / item.name
        if item.is_dir():
            shutil.copytree(item, dest)
        else:
            shutil.copy2(item, dest)

    # 创建桌面快捷方式
    appsdir = pkgroot / "usr" / "share" / "applications"
    appsdir.mkdir(parents=True)
    (appsdir / f"{APP_NAME}.desktop").write_text(f"""[Desktop Entry]
Type=Application
Name={DISPLAY_NAME}
Exec=/opt/{APP_NAME}/{APP_NAME}
Icon=/opt/{APP_NAME}/icon.png
Categories=Finance;
""")

    # 创建 /usr/local/bin 软链接
    bindir = pkgroot / "usr" / "local" / "bin"
    bindir.mkdir(parents=True)
    (bindir / APP_NAME).symlink_to(f"/opt/{APP_NAME}/{APP_NAME}")

    arch_map = {"x86_64": "amd64", "aarch64": "arm64"}
    deb_arch = arch_map.get(platform.machine(), "amd64")
    out = DIST / f"BN-Trader_{VERSION}_{deb_arch}.deb"

    r = _sh([
        "fpm", "-s", "dir", "-t", "deb",
        "-n", APP_NAME.lower(),
        "-v", VERSION,
        "-a", deb_arch,
        "-p", str(out),
        "-C", str(pkgroot),
        "--description", "BN-Trader 本地短线交易系统",
        "--url", WEBSITE,
        "--maintainer", PUBLISHER,
        "--license", "MIT",
        ".",
    ])
    if r.returncode == 0 and out.exists():
        size = out.stat().st_size
        print(f"  ✓ {out.name} ({_fmt_size(size)})")
        return out
    return None


# ==================================================================
#  便携版 ZIP
# ==================================================================

def _make_portable_zip(app_dir: Path, platform_tag: str) -> Path:
    """制作便携版 ZIP 压缩包"""
    if app_dir.suffix == ".app":
        zip_name = f"BN-Trader-v{VERSION}-{platform_tag}-portable"
        shutil.make_archive(str(DIST / zip_name), "zip", str(DIST), app_dir.name)
    else:
        zip_name = f"BN-Trader-v{VERSION}-{platform_tag}-portable"
        base_dir = app_dir.parent if app_dir.is_file() else app_dir
        arcname = app_dir.name if app_dir.is_dir() else APP_NAME
        # 如果是单文件 exe，先放到一个文件夹里
        if app_dir.is_file():
            tmp = BUILD / "portable"
            tmp.mkdir(parents=True, exist_ok=True)
            shutil.copy2(app_dir, tmp / app_dir.name)
            shutil.make_archive(str(DIST / zip_name), "zip", str(tmp))
        else:
            shutil.make_archive(str(DIST / zip_name), "zip", str(base_dir.parent), arcname)

    zip_path = DIST / f"{zip_name}.zip"
    size = zip_path.stat().st_size if zip_path.exists() else 0
    print(f"  ✓ 便携版: {zip_path.name} ({_fmt_size(size)})")
    return zip_path


# ==================================================================
#  环境检测
# ==================================================================

def detect_current_platform() -> str:
    """检测当前运行平台"""
    system = sys.platform
    if system == "win32":
        return "win64"
    elif system == "darwin":
        arch = platform.machine()
        return "mac-arm64" if arch == "arm64" else "mac-x64"
    return "linux"


# ==================================================================
#  主入口
# ==================================================================

def main():
    parser = argparse.ArgumentParser(
        description="BN-Trader 原生安装包打包",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python package.py                              # 自动检测当前平台
  python package.py --platform win64             # 构建 Windows 安装包
  python package.py --platform mac-arm64         # 构建 macOS ARM DMG
  python package.py --all --clean                # 清理构建所有平台
  python package.py --portable                   # 仅构建便携版 ZIP
        """
    )
    parser.add_argument("--platform", type=str,
                       choices=["win64", "mac-arm64", "mac-x64", "linux"],
                       help="目标平台")
    parser.add_argument("--all", action="store_true",
                       help="构建所有平台（CI 模式）")
    parser.add_argument("--clean", action="store_true",
                       help="清理后重新构建")
    parser.add_argument("--onefile", action="store_true",
                       help="构建单文件可执行程序")
    parser.add_argument("--portable", action="store_true",
                       help="仅构建便携版 ZIP")
    parser.add_argument("--skip-pyinstaller", action="store_true",
                       help="跳过 PyInstaller 构建（已有产物时）")
    args = parser.parse_args()

    # 清理
    if args.clean:
        for d in [DIST, BUILD]:
            if d.exists():
                print(f"清理 {d}")
                shutil.rmtree(d)

    # 确定平台
    platforms = []
    if args.all:
        platforms = list(PLATFORM_META.keys())
    elif args.platform:
        platforms = [args.platform]
    else:
        platforms = [detect_current_platform()]

    print("\n" + "=" * 60)
    print(f"  {DISPLAY_NAME} v{VERSION} 安装包打包")
    print(f"  目标平台: {', '.join(platforms)}")
    print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 当前平台只能构建同平台（除非有交叉编译工具）
    current = detect_current_platform()
    for target in platforms:
        print(f"\n{'=' * 60}")
        print(f"  目标: {target}")
        print(f"{'=' * 60}")

        meta = PLATFORM_META[target]

        if not args.skip_pyinstaller:
            app_dir = pyinstaller_build(target, onefile=args.onefile)
            if not app_dir:
                continue
        else:
            app_dir = _find_existing_build()
            if not app_dir:
                print("  ✗ 未找到已有构建产物")
                continue

        prepare_payload(app_dir)

        if args.portable:
            _make_portable_zip(app_dir, target)
            continue

        # 调用平台特定打包
        result = None
        if target.startswith("win"):
            result = build_windows_installer(app_dir)
        elif target.startswith("mac"):
            result = build_macos_dmg(app_dir, meta["arch"])
        else:
            result = build_linux_packages(app_dir)

    # 最终输出
    print("\n\n" + "=" * 60)
    print("  构建产物:")
    print("=" * 60)
    for item in sorted(DIST.rglob("*"), key=lambda x: x.stat().st_size if x.is_file() else 0, reverse=True):
        if item.is_file() and not item.name.startswith("."):
            print(f"  {_fmt_size(item.stat().st_size):>10s}    {item.name}")
    print("=" * 60)


def _find_existing_build() -> Path | None:
    """查找已有的构建产物"""
    candidates = [
        DIST / APP_NAME / f"{APP_NAME}.exe",
        DIST / f"{APP_NAME}.exe",
        DIST / f"{APP_NAME}.app",
        DIST / APP_NAME / APP_NAME,
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


if __name__ == "__main__":
    main()
