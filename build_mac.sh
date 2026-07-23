#!/bin/bash
# BN-Trader macOS 一键打包
# 自动: 生成图标 → 构建程序 → 打包 DMG

set -e

echo "============================================"
echo "  BN-Trader macOS 打包工具"
echo "============================================"
echo ""

# 检查依赖
check_tool() {
    if ! command -v "$1" &> /dev/null; then
        echo "[错误] 未找到 $1"
        echo "  安装: $2"
        exit 1
    fi
}

check_tool python3 "brew install python"
check_tool pip3 "python3 -m ensurepip"

# create-dmg 是可选的
if ! command -v create-dmg &> /dev/null; then
    echo "[提示] 未安装 create-dmg，将生成 ZIP 而非 DMG"
    echo "  安装: brew install create-dmg"
    echo ""
    SKIP_DMG=1
fi

# 生成图标
if [ ! -f "assets/icon.png" ]; then
    echo "[1/3] 生成图标..."
    python3 generate_icons.py
    echo ""
else
    echo "[1/3] 图标已存在，跳过"
    echo ""
fi

# 安装 PyInstaller（如果需要）
if ! python3 -c "import PyInstaller" 2>/dev/null; then
    echo "安装 PyInstaller..."
    pip3 install pyinstaller
fi

# 构建 + 打包
echo "[2/3] 构建程序并打包..."
python3 package.py --clean

# 如果 create-dmg 可用且没有被跳过
if [ -z "$SKIP_DMG" ] && [ -d "dist/BN-Trader.app" ]; then
    echo ""
    echo "[3/3] 生成 DMG 安装镜像..."
    ARCH=$(uname -m)
    VERSION=$(python3 -c "from config import Config; print(Config.APP_VERSION)")
    create-dmg \
        --volname "BN-Trader $VERSION" \
        --window-pos 200 120 \
        --window-size 600 400 \
        --icon-size 100 \
        --icon "BN-Trader.app" 180 170 \
        --app-drop-link 420 170 \
        "dist/BN-Trader-${VERSION}-${ARCH}.dmg" \
        "dist/BN-Trader.app"
fi

echo ""
echo "============================================"
echo "  完成!"
echo "============================================"
ls -lh dist/
echo ""
