@echo off
chcp 65001 >nul
REM BN-Trader 依赖安装脚本 (Windows)
REM 双击运行或在命令行中运行: install.bat

echo === BN-Trader 依赖安装 (Windows) ===
echo.

REM 检查 Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到 Python，请先安装 Python 3.10+
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [1/3] 创建虚拟环境...
python -m venv .venv
call .venv\Scripts\activate.bat

echo [2/3] 安装 Python 依赖...
pip install ^
    PyQt6>=6.4.0 ^
    pyqtgraph>=0.13.0 ^
    requests>=2.28.0 ^
    websocket-client>=1.4.0 ^
    numpy>=1.23.0 ^
    pandas>=1.5.0 ^
    SQLAlchemy>=2.0.0 ^
    python-dotenv>=0.21.0 ^
    pytest>=7.2.0

echo [3/3] 验证安装...
python -c "import PyQt6; print('PyQt6:', PyQt6.QtCore.PYQT_VERSION_STR); import numpy; print('NumPy:', numpy.__version__); import pandas; print('Pandas:', pandas.__version__); import sqlalchemy; print('SQLAlchemy:', sqlalchemy.__version__); print('所有依赖安装成功!')"

echo.
echo === 安装完成 ===
echo 运行方式:
echo   .venv\Scripts\activate
echo   python main.py
echo.
pause
