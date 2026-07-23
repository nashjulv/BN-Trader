#!/bin/bash
# BN-Trader 依赖安装脚本
# 请在终端中运行此脚本: bash install.sh

echo "=== BN-Trader 依赖安装 ==="
echo ""

# 创建虚拟环境
echo "[1/3] 创建虚拟环境..."
python3 -m venv .venv
source .venv/bin/activate

# 安装依赖
echo "[2/3] 安装Python依赖..."
pip install PyQt6>=6.4.0 \
           pyqtgraph>=0.13.0 \
           requests>=2.28.0 \
           websocket-client>=1.4.0 \
           numpy>=1.23.0 \
           pandas>=1.5.0 \
           SQLAlchemy>=2.0.0 \
           python-dotenv>=0.21.0 \
           pytest>=7.2.0

# 验证安装
echo "[3/3] 验证安装..."
python -c "
import PyQt6; print('PyQt6:', PyQt6.QtCore.PYQT_VERSION_STR)
import numpy; print('NumPy:', numpy.__version__)
import pandas; print('Pandas:', pandas.__version__)
import sqlalchemy; print('SQLAlchemy:', sqlalchemy.__version__)
import requests; print('Requests:', requests.__version__)
print('所有依赖安装成功!')
"

echo ""
echo "=== 安装完成 ==="
echo "运行方式: source .venv/bin/activate && python main.py"
