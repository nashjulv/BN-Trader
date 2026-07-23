"""
震荡行情策略

高抛低吸：布林带上下轨 + RSI 超买超卖信号。
仅在震荡行情（ADX < 25）中激活。
"""

from typing import Optional

import numpy as np
import pandas as pd

from strategies.base import BaseStrategy, Signal, SignalType
from indicators.technical import rsi, bollinger_bands


class RangingStrategy(BaseStrategy):
    """震荡策略 — 高抛低吸"""

    def __init__(self):
        super().__init__(
            name="震荡策略",
            description="布林带 + RSI，上轨卖出、下轨买入"
        )
        self.params = {
            "bb_period": 20,
            "bb_std": 2.0,
            "rsi_period": 14,
            "rsi_oversold": 30,
            "rsi_overbought": 70,
            "stop_loss_pct": 0.03,
            "take_profit_pct": 0.03,
            "require_boll_touch": True,
        }

    def analyze(self, df: pd.DataFrame, scene) -> Optional[Signal]:
        if not self._is_ready(df, 30):
            return None

        close = df["close"].values.astype(float)

        # ---------- 布林带 ----------
        upper, middle, lower = bollinger_bands(
            close, self.params["bb_period"], self.params["bb_std"]
        )
        if len(upper) < 2:
            return None

        # ---------- RSI ----------
        rsi_vals = rsi(close, self.params["rsi_period"])
        if len(rsi_vals) < 1:
            return None

        current_price = close[-1]
        current_rsi = rsi_vals[-1]
        bb_upper = upper[-1]
        bb_lower = lower[-1]
        bb_middle = middle[-1]

        # ---------- 买入：触及下轨 + RSI超卖 ----------
        near_lower = current_price <= bb_lower * 1.005
        rsi_oversold = current_rsi <= self.params["rsi_oversold"]

        buy_condition = near_lower and rsi_oversold if self.params["require_boll_touch"] else rsi_oversold

        if buy_condition and current_rsi > 0:
            sl = current_price * (1 - self.params["stop_loss_pct"])
            tp = bb_middle  # 目标中轨
            # 确保盈亏比 > 1.5
            if (tp - current_price) < (current_price - sl) * 1.5:
                tp = current_price + (current_price - sl) * 1.5

            self.signal_count += 1
            return Signal(
                type=SignalType.BUY,
                symbol=self._get_symbol(df),
                price=current_price,
                stop_loss=sl,
                take_profit=tp,
                confidence=min(scene.confidence * 0.75, 0.80),
                reason=f"布林带下轨 + RSI超卖({current_rsi:.0f})",
                scene=scene.type,
            )

        # ---------- 卖出：触及上轨 + RSI超买 ----------
        near_upper = current_price >= bb_upper * 0.995
        rsi_overbought = current_rsi >= self.params["rsi_overbought"]

        sell_condition = near_upper and rsi_overbought if self.params["require_boll_touch"] else rsi_overbought

        if sell_condition and current_rsi > 0:
            sl = current_price * (1 + self.params["stop_loss_pct"])
            tp = bb_middle
            if (current_price - tp) < (sl - current_price) * 1.5:
                tp = current_price - (sl - current_price) * 1.5

            self.signal_count += 1
            return Signal(
                type=SignalType.SELL,
                symbol=self._get_symbol(df),
                price=current_price,
                stop_loss=sl,
                take_profit=tp,
                confidence=min(scene.confidence * 0.75, 0.80),
                reason=f"布林带上轨 + RSI超买({current_rsi:.0f})",
                scene=scene.type,
            )

        return None

    @staticmethod
    def _get_symbol(df) -> str:
        return df["symbol"].iloc[-1] if "symbol" in df.columns else "UNKNOWN"
