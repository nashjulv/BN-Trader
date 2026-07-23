"""
极端行情策略 — 反向或观望
"""

from typing import Optional
import numpy as np
import pandas as pd

from strategies.base import BaseStrategy, Signal, SignalType


class ExtremeStrategy(BaseStrategy):
    """极端策略 — 快进快出反向操作"""

    def __init__(self):
        super().__init__(
            name="极端行情策略",
            description="高波动率反向操作，极小仓位快进快出"
        )
        self.params = {
            "atr_multiplier": 3.0,
            "volume_spike": 3.0,
            "hold_time": 300,
            "stop_loss_pct": 0.01,
            "take_profit_pct": 0.02,
        }

    def analyze(self, df: pd.DataFrame, scene) -> Optional[Signal]:
        if not self._is_ready(df, 20):
            return None

        close = df["close"].values.astype(float)
        high = df["high"].values.astype(float)
        low = df["low"].values.astype(float)

        atr_val = self._compute_atr(high, low, close, 14)
        if atr_val is None:
            return None

        current_price = close[-1]
        price_change = abs(close[-1] - close[-2]) / close[-2] if len(close) >= 2 and close[-2] > 0 else 0
        atr_ratio = atr_val / current_price if current_price > 0 else 0

        if price_change > atr_ratio * self.params["atr_multiplier"]:
            sl_pct = self.params["stop_loss_pct"]
            tp_pct = self.params["take_profit_pct"]

            if close[-1] > close[-2]:
                self.signal_count += 1
                return Signal(type=SignalType.SELL, symbol=self._get_symbol(df),
                              price=current_price,
                              stop_loss=current_price * (1 + sl_pct),
                              take_profit=current_price * (1 - tp_pct),
                              confidence=min(scene.confidence * 0.5, 0.55),
                              reason="极端行情反向操作", scene=scene.type)
            else:
                self.signal_count += 1
                return Signal(type=SignalType.BUY, symbol=self._get_symbol(df),
                              price=current_price,
                              stop_loss=current_price * (1 - sl_pct),
                              take_profit=current_price * (1 + tp_pct),
                              confidence=min(scene.confidence * 0.5, 0.55),
                              reason="极端行情反向操作", scene=scene.type)

        return Signal(type=SignalType.HOLD, symbol=self._get_symbol(df),
                      price=current_price, stop_loss=0, take_profit=0,
                      confidence=scene.confidence, reason="极端行情，建议观望", scene=scene.type)

    @staticmethod
    def _compute_atr(high, low, close, period):
        if len(high) < period + 1:
            return None
        tr = np.maximum(high[1:] - low[1:],
                        np.maximum(np.abs(high[1:] - close[:-1]),
                                   np.abs(low[1:] - close[:-1])))
        return float(np.mean(tr[-period:]))

    @staticmethod
    def _get_symbol(df) -> str:
        return str(df["symbol"].iloc[-1]) if "symbol" in df.columns else "UNKNOWN"
