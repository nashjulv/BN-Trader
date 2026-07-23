"""
反转交易策略

检测顶背离/底背离信号，逆势试探性开仓。
小仓位、严格止损，等待趋势反转确认。
"""

from typing import Optional

import numpy as np
import pandas as pd

from strategies.base import BaseStrategy, Signal, SignalType
from indicators.technical import rsi


class ReversalStrategy(BaseStrategy):
    """反转策略 — 背离交易"""

    def __init__(self):
        super().__init__(
            name="反转策略",
            description="顶/底背离检测，逆势试探，严格止损"
        )
        self.params = {
            "rsi_period": 14,
            "rsi_oversold": 25,           # 极度超卖
            "rsi_overbought": 75,         # 极度超买
            "divergence_lookback": 10,    # 背离检测窗口
            "stop_loss_pct": 0.02,        # 止损 2%
            "take_profit_pct": 0.04,      # 止盈 4%
            "min_rsi_divergence": 5,      # RSI背离最小差值
        }

    def analyze(self, df: pd.DataFrame, scene) -> Optional[Signal]:
        if not self._is_ready(df, 35):
            return None

        close = df["close"].values.astype(float)
        high = df["high"].values.astype(float)
        low = df["low"].values.astype(float)

        rsi_vals = rsi(close, self.params["rsi_period"])
        if len(rsi_vals) < self.params["divergence_lookback"]:
            return None

        current_price = close[-1]
        current_rsi = rsi_vals[-1]
        lb = self.params["divergence_lookback"]

        # ---------- 顶背离：价格新高，RSI 不创新高 ----------
        price_window = high[-lb:]
        rsi_window = rsi_vals[-lb:]

        price_peak = np.max(price_window)
        rsi_peak = np.max(rsi_window)

        near_price_peak = current_price >= price_peak * 0.995
        rsi_divergence_down = rsi_peak - current_rsi >= self.params["min_rsi_divergence"]

        if near_price_peak and rsi_divergence_down and current_rsi >= self.params["rsi_overbought"]:
            sl = current_price * (1 + self.params["stop_loss_pct"])
            tp = current_price * (1 - self.params["take_profit_pct"])

            self.signal_count += 1
            return Signal(
                type=SignalType.SELL,
                symbol=self._get_symbol(df),
                price=current_price,
                stop_loss=sl,
                take_profit=tp,
                confidence=min(scene.confidence * 0.55, 0.60),
                reason=f"顶背离(价格新高 RSI{current_rsi:.0f}<RSI峰{rsi_peak:.0f})",
                scene=scene.type,
            )

        # ---------- 底背离：价格新低，RSI 不创新低 ----------
        price_low = np.min(low[-lb:])
        rsi_low = np.min(rsi_vals[-lb:])

        near_price_low = current_price <= price_low * 1.005
        rsi_divergence_up = current_rsi - rsi_low >= self.params["min_rsi_divergence"]

        if near_price_low and rsi_divergence_up and current_rsi <= self.params["rsi_oversold"]:
            sl = current_price * (1 - self.params["stop_loss_pct"])
            tp = current_price * (1 + self.params["take_profit_pct"])

            self.signal_count += 1
            return Signal(
                type=SignalType.BUY,
                symbol=self._get_symbol(df),
                price=current_price,
                stop_loss=sl,
                take_profit=tp,
                confidence=min(scene.confidence * 0.55, 0.60),
                reason=f"底背离(价格新低 RSI{current_rsi:.0f}>RSI谷{rsi_low:.0f})",
                scene=scene.type,
            )

        return None

    @staticmethod
    def _get_symbol(df) -> str:
        return df["symbol"].iloc[-1] if "symbol" in df.columns else "UNKNOWN"
