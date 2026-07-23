@echo off
chcp 65001 >nul
REM BN-Trader Windows 一键打包
REM 自动: 生成图标 → 构建程序 → 打包 NSIS 安装程序

echo ============================================
echo   BN-Trader Windows 打包工具
echo ============================================
echo.

REM 检查 Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到 Python!
    pause
    exit /b 1
)

REM 检查 NSIS (可选)
where makensis >nul 2>&1
if %errorlevel% neq 0 (
    echo [提示] 未检测到 NSIS，将跳过安装程序生成，仅生成便携版 ZIP
    echo 下载 NSIS: https://nsis.sourceforge.io/Download
    echo.
    set NSIS_MODE=portable
) else (
    for /f "tokens=*" %%i in ('makensis /VERSION') do echo NSIS: %%i
    set NSIS_MODE=full
)

echo.

REM 生成图标
if not exist "assets\icon.png" (
    echo [1/3] 生成图标...
    python generate_icons.py
    echo.
) else (
    echo [1/3] 图标已存在，跳过
    echo.
)

REM 构建 + 打包
echo [2/3] 构建程序并打包...
python package.py --clean
if %errorlevel% neq 0 (
    echo [错误] 打包失败!
    pause
    exit /b 1
)

echo.
echo [3/3] 完成!
echo.
echo 产物在 dist\ 目录:
dir /b dist\

echo.
pause
