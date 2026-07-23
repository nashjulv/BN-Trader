#!/bin/bash
# BN-Trader Linux 一键打包
# 自动: 生成图标 → 构建程序 → 打包 AppImage / DEB

set -e

echo "============================================"
echo "  BN-Trader Linux 打包工具"
echo "============================================"
echo ""

ARCH=$(uname -m)
echo "架构: $ARCH"
echo ""

# 检查基础依赖
if ! command -v python3 &> /dev/null; then
    echo "[错误] 未找到 python3"
    exit 1
fi

# 生成图标
if [ ! -f "assets/icon.png" ]; then
    echo "[1/4] 生成图标..."
    python3 generate_icons.py
    echo ""
else
    echo "[1/4] 图标已存在，跳过"
    echo ""
fi

# PyInstaller
if ! python3 -c "import PyInstaller" 2>/dev/null; then
    echo "[2/4] 安装 PyInstaller..."
    pip3 install pyinstaller
fi
echo "[2/4] PyInstaller 就绪"
echo ""

# 构建
echo "[3/4] PyInstaller 构建..."
python3 -m PyInstaller --noconfirm --distpath dist --workpath build BN-Trader.spec
echo ""

# 打包 AppImage
echo "[4/4] 生成安装包..."

if command -v appimagetool &> /dev/null; then
    echo "  → AppImage..."
    python3 package.py --skip-pyinstaller
else
    echo "  [提示] 未安装 appimagetool，跳过 AppImage"
    echo "  安装: sudo apt install appimagetool"
    # 至少生成便携版
    python3 package.py --skip-pyinstaller --portable
fi

echo ""
echo "============================================"
echo "  完成!"
echo "============================================"
ls -lh dist/ 2>/dev/null || echo "产物在 dist/ 目录"
echo ""
