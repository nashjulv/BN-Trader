import os
import sys
from pathlib import Path

# ---------- 打包後資料目錄 ----------
# PyInstaller 打包後，可執行檔所在目錄作為基準
# 開發時用專案根目錄
def _get_app_dir() -> Path:
    """取得應用程式資料目錄（打包後也正確）"""
    if getattr(sys, "frozen", False):
        # PyInstaller 打包：使用者資料放可執行檔旁邊的 data/ 目錄
        exe_dir = Path(sys.executable).parent
    else:
        exe_dir = Path(__file__).parent
    return exe_dir


def _get_user_data_dir() -> Path:
    """取得使用者資料目錄（開發時用目前目錄，打包後用系統標準目錄）"""
    # PyInstaller 打包後：使用系統標準目錄
    if getattr(sys, "frozen", False):
        system = sys.platform
        if system == "win32":
            base = Path(os.getenv("APPDATA", Path.home() / "AppData" / "Roaming"))
        elif system == "darwin":
            base = Path.home() / "Library" / "Application Support"
        else:
            base = Path(os.getenv("XDG_DATA_HOME", Path.home() / ".local" / "share"))
        data_dir = base / "BN-Trader"
        try:
            data_dir.mkdir(parents=True, exist_ok=True)
        except (PermissionError, OSError):
            data_dir = Path.cwd()
        return data_dir

    # 開發模式：直接用當前目錄，足夠簡單
    return Path.cwd()


APP_DIR = _get_app_dir()
USER_DATA_DIR = _get_user_data_dir()

# 載入 .env（優先打包目錄，其次使用者目錄）
_env_paths = [
    APP_DIR / ".env",
    USER_DATA_DIR / ".env",
]
for _p in _env_paths:
    if _p.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(_p)
        except ImportError:
            pass
        break


class Config:
    """应用配置类"""

    # 应用信息
    APP_NAME = "BN-Trader"
    APP_VERSION = "1.0.0"

    # 路徑
    APP_DIR = APP_DIR
    USER_DATA_DIR = USER_DATA_DIR

    # 数据库
    DATABASE_URL = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{(USER_DATA_DIR / 'bn_trader.db').as_posix()}"
    )

    # 币安API — 启动时加载，reload() 可动态刷新
    BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")
    BINANCE_SECRET_KEY = os.getenv("BINANCE_SECRET_KEY", "")
    BINANCE_BASE_URL = "https://api.binance.com"
    BINANCE_WS_URL = "wss://stream.binance.com:9443/ws"

    @classmethod
    def reload_api_keys(cls):
        """动态重载 API Key（用户在运行时保存后调用）"""
        from dotenv import load_dotenv
        for _p in _env_paths:
            if _p.exists():
                load_dotenv(_p, override=True)
        cls.BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")
        cls.BINANCE_SECRET_KEY = os.getenv("BINANCE_SECRET_KEY", "")

    # 交易配置
    DEFAULT_SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "USDCUSDT"]
    DEFAULT_TIMEFRAME = "15m"  # 默认K线周期

    # 风控配置
    DEFAULT_TOTAL_CAPITAL = 10000.0  # 默认总资金
    RESERVE_RATIO = 0.20  # 风险准备金比例
    MAX_SINGLE_TRADE_RATIO = 0.30  # 单笔最大仓位比例
    DAILY_LOSS_LIMIT = 0.05  # 日亏损上限
    MAX_CONSECUTIVE_LOSS = 3  # 最大连续亏损次数
    MAX_DRAWDOWN = 0.20  # 最大回撤
    COOLDOWN_SECONDS = 300  # 连续亏损后冷却时间

    # 单笔风控
    MAX_LOSS_PER_TRADE = 0.02  # 单笔最大亏损2%
    MAX_PROFIT_PER_TRADE = 0.05  # 单笔止盈目标5%
    MAX_HOLD_TIME = 3600  # 最大持仓时间1小时
    MAX_DAILY_TRADES = 20  # 日最大交易次数

    # 场景识别
    SCENE_DETECTION_INTERVAL = 60  # 场景识别间隔(秒)
    MIN_KLINES_FOR_DETECTION = 100  # 场景识别最少K线数

    # UI配置
    UPDATE_INTERVAL = 1000  # UI刷新间隔(ms)
    CHART_UPDATE_INTERVAL = 5000  # 图表刷新间隔(ms)

    # 日志
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE = str(USER_DATA_DIR / "bn_trader.log")
