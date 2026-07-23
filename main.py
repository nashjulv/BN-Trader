"""
BN-Trader 本地短线交易系统

主入口文件，初始化应用并启动主窗口。
"""

import sys
import logging
import platform
from pathlib import Path

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from gui.main_window import MainWindow
from core.database import init_database
from utils.logger import setup_logger
from config import Config


def _get_system_font() -> QFont:
    """根据操作系统自动选择合适的中文字体（安全回退）"""
    system = platform.system()

    if system == "Windows":
        candidates = ["Microsoft YaHei", "SimHei", "SimSun", "Arial"]
    elif system == "Darwin":
        candidates = ["PingFang SC", "Heiti SC", "STHeiti",
                       "Songti SC", "Helvetica", "Arial"]
    else:
        candidates = ["Noto Sans CJK SC", "WenQuanYi Micro Hei",
                       "DejaVu Sans", "Sans", "Arial"]

    # 使用 QFont 构造函数尝试每个字体，看是否能成功设置
    for name in candidates:
        font = QFont(name, 10)
        # 如果系统不支持该字体，QFont 会自动回退，family() 返回不同于请求的名称
        actual = font.family()
        if actual == name or actual != candidates[-1]:
            # 只要不是最后一个兜底字体被回退，就认为匹配成功
            return font

    return QFont("Arial", 10)


def main():
    """应用主入口"""
    # 设置日志
    setup_logger(Config.LOG_LEVEL, Config.LOG_FILE)
    logger = logging.getLogger(__name__)
    logger.info(f"启动 {Config.APP_NAME} v{Config.APP_VERSION}")
    logger.info(f"操作系统: {platform.system()} {platform.release()}")
    logger.info(f"Python: {sys.version}")

    # 初始化数据库
    init_database()
    logger.info("数据库初始化完成")

    # 创建Qt应用
    app = QApplication(sys.argv)
    app.setApplicationName(Config.APP_NAME)
    app.setApplicationVersion(Config.APP_VERSION)

    # 设置全局字体（自动适配系统）
    font = _get_system_font()
    app.setFont(font)
    logger.info(f"字体: {font.family()}")

    # 启用高DPI支持（兼容不同Qt6版本）
    try:
        app.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )
    except AttributeError:
        logger.info("HighDpiScaleFactorRoundingPolicy 不可用，使用默认DPI策略")

    # 创建主窗口
    window = MainWindow()
    window.show()

    logger.info("主窗口已显示")

    # 运行应用
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
