"""
突破交易策略

当价格突破关键支撑/阻力位且成交量放大时跟进。
设置假突破止损（突破位回撤），目标1:2盈亏比。
"""

from typing import Optional

import numpy as np
import pandas as pd

from strategies.base import BaseStrategy, Signal, SignalType


class BreakoutStrategy(BaseStrategy):
    """突破策略 — 突破跟进"""

    def __init__(self):
        super().__init__(
            name="突破策略",
            description="关键价位突破 + 成交量确认，顺势跟进"
        )
        self.params = {
            "lookback": 20,               # 回看周期
            "volume_threshold": 1.5,      # 成交量放大倍数
            "breakout_pct": 0.008,        # 突破阈值 0.8%
            "atr_period": 14,             # ATR周期
            "atr_filter": 1.5,            # ATR过滤（突破幅度 > 1.5 ATR）
            "stop_loss_pct": 0.015,       # 止损比例
            "risk_reward": 2.0,           # 目标盈亏比
        }

    def analyze(self, df: pd.DataFrame, scene) -> Optional[Signal]:
        if not self._is_ready(df, self.params["lookback"] + 10):
            return None

        high = df["high"].values.astype(float)
        low = df["low"].values.astype(float)
        close = df["close"].values.astype(float)
        volume = df["volume"].values.astype(float)

        lb = self.params["lookback"]

        # 关键价位（排除最后一根）
        resistance = np.max(high[-lb:-1])
        support = np.min(low[-lb:-1])

        current_price = close[-1]
        current_high = high[-1]
        current_low = low[-1]

        # 成交量确认
        avg_vol = np.mean(volume[-lb:-1])
        vol_ratio = volume[-1] / avg_vol if avg_vol > 0 else 0

        # ATR 过滤
        atr_val = self._compute_atr(high, low, close, self.params["atr_period"])
        if atr_val is None:
            return None

        price_range = resistance - support
        breakout_strength = (
            (current_high - resistance) / atr_val
            if current_high > resistance
            else (support - current_low) / atr_val
        )

        # ---------- 向上突破 ----------
        if current_high > resistance * (1 + self.params["breakout_pct"]):
            if vol_ratio >= self.params["volume_threshold"]:
                sl = resistance  # 突破位止损
                tp = current_price + (current_price - sl) * self.params["risk_reward"]

                self.signal_count += 1
                return Signal(
                    type=SignalType.BUY,
                    symbol=self._get_symbol(df),
                    price=current_price,
                    stop_loss=sl,
                    take_profit=tp,
                    confidence=min(scene.confidence * 0.88, 0.90),
                    reason=f"向上突破(阻力{resistance:.2f}) 成交量{vol_ratio:.1f}x",
                    scene=scene.type,
                )

        # ---------- 向下突破 ----------
        if current_low < support * (1 - self.params["breakout_pct"]):
            if vol_ratio >= self.params["volume_threshold"]:
                sl = support
                tp = current_price - (sl - current_price) * self.params["risk_reward"]

                self.signal_count += 1
                return Signal(
                    type=SignalType.SELL,
                    symbol=self._get_symbol(df),
                    price=current_price,
                    stop_loss=sl,
                    take_profit=tp,
                    confidence=min(scene.confidence * 0.88, 0.90),
                    reason=f"向下突破(支撑{support:.2f}) 成交量{vol_ratio:.1f}x",
                    scene=scene.type,
                )

        return None

    @staticmethod
    def _compute_atr(high, low, close, period):
        if len(high) < period + 1:
            return None
        tr = np.maximum(
            high[1:] - low[1:],
            np.maximum(np.abs(high[1:] - close[:-1]), np.abs(low[1:] - close[:-1])),
        )
        return np.mean(tr[-period:])

    @staticmethod
    def _get_symbol(df) -> str:
        return df["symbol"].iloc[-1] if "symbol" in df.columns else "UNKNOWN"
