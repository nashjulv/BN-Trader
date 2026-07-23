"""
日志工具模块
"""

import logging
import sys
from pathlib import Path


def setup_logger(level: str = "INFO", log_file: str = "bn_trader.log") -> None:
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 文件处理器（写入失败则跳过）
    file_handler = None
    try:
        file_handler = logging.FileHandler(str(log_path), encoding="utf-8")
        file_handler.setFormatter(formatter)
    except (PermissionError, OSError) as e:
        print(f"[WARN] 无法写入日志文件: {log_path} ({e})")

    # 控制台处理器始终可用
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))
    if file_handler:
        root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
