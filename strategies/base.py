"""
策略基类

所有交易策略的抽象基类，定义统一接口。
"""

from abc import ABC, abstractmethod
from typing import Dict, Optional
from dataclasses import dataclass
from enum import Enum

import numpy as np
import pandas as pd


class SignalType(Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    CLOSE = "CLOSE"


@dataclass
class Signal:
    type: SignalType
    symbol: str
    price: float
    stop_loss: float
    take_profit: float
    confidence: float
    reason: str
    scene: str


class BaseStrategy(ABC):
    """策略基类 — 所有策略必须实现 analyze 方法"""

    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
        self.params: Dict = {}
        self.signal_count = 0

    def set_params(self, **kwargs):
        """动态设置策略参数"""
        self.params.update(kwargs)

    @abstractmethod
    def analyze(self, df: pd.DataFrame, scene) -> Optional[Signal]:
        """
        分析行情数据，生成交易信号

        Args:
            df: 包含OHLCV和技术指标的DataFrame
            scene: 当前行情场景对象

        Returns:
            Signal 或 None（不交易）
        """
        ...

    def get_info(self) -> Dict:
        """获取策略信息"""
        return {
            "name": self.name,
            "description": self.description,
            "params": self.params,
            "signal_count": self.signal_count,
        }

    def _is_ready(self, df: pd.DataFrame, min_bars: int = 30) -> bool:
        """检查数据是否足够"""
        return len(df) >= min_bars and not df.empty
