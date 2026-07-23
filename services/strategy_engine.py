"""
策略引擎 — 管理不同行情场景下的交易策略。

使用 strategies/ 目录下的独立策略实现。
"""

import logging
from typing import Dict, List, Optional

from strategies.base import BaseStrategy, Signal, SignalType
from strategies.trending import TrendingStrategy
from strategies.ranging import RangingStrategy
from strategies.breakout import BreakoutStrategy
from strategies.reversal import ReversalStrategy
from strategies.extreme import ExtremeStrategy

logger = logging.getLogger(__name__)


class StrategyEngine:
    """策略引擎"""

    def __init__(self):
        self.strategies: Dict[str, BaseStrategy] = {
            "TRENDING": TrendingStrategy(),
            "RANGING": RangingStrategy(),
            "BREAKOUT": BreakoutStrategy(),
            "REVERSAL": ReversalStrategy(),
            "EXTREME": ExtremeStrategy(),
        }

        self.active_signals: List[Signal] = []
        self.signal_history: List[Signal] = []

        logger.info("策略引擎初始化完成")

    def generate_signal(self, df: pd.DataFrame, scene: Scene) -> Optional[Signal]:
        """
        根据场景生成交易信号

        Args:
            df: K线数据
            scene: 当前场景

        Returns:
            Signal or None
        """
        strategy = self.strategies.get(scene.type)
        if not strategy:
            logger.warning(f"未知场景类型: {scene.type}")
            return None

        signal = strategy.analyze(df, scene)

        if signal:
            self.active_signals.append(signal)
            self.signal_history.append(signal)

            logger.info(
                f"生成信号: {signal.type.value} {signal.symbol} "
                f"@{signal.price:.2f} (置信度: {signal.confidence:.2f})"
            )

        return signal

    def get_strategy_info(self, scene_type: str) -> Dict:
        """获取策略信息"""
        strategy = self.strategies.get(scene_type)
        if not strategy:
            return {}

        return {
            "name": strategy.name,
            "params": strategy.params,
        }

    def get_signal_stats(self) -> Dict:
        """获取信号统计"""
        if not self.signal_history:
            return {"total": 0, "buy": 0, "sell": 0, "hold": 0}

        buy_count = sum(1 for s in self.signal_history if s.type == SignalType.BUY)
        sell_count = sum(1 for s in self.signal_history if s.type == SignalType.SELL)
        hold_count = sum(1 for s in self.signal_history if s.type == SignalType.HOLD)

        return {
            "total": len(self.signal_history),
            "buy": buy_count,
            "sell": sell_count,
            "hold": hold_count,
            "active": len(self.active_signals)
        }
