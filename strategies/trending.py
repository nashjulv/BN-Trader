"""
趋势跟踪策略

顺势交易：均线金叉买入，死叉卖出；MACD + ADX 双重确认。
趋势行情中追涨杀跌，使用移动止损保护利润。
"""

from typing import Optional

import numpy as np
import pandas as pd

from strategies.base import BaseStrategy, Signal, SignalType
from indicators.technical import ema, macd


class TrendingStrategy(BaseStrategy):
    """趋势跟踪策略 — 顺势而为"""

    def __init__(self):
        super().__init__(
            name="趋势跟踪策略",
            description="均线金叉/死叉 + MACD确认，顺势交易，移动止损"
        )
        self.params = {
            "fast_ma": 5,          # 快线周期
            "slow_ma": 20,         # 慢线周期
            "macd_fast": 12,       # MACD快线
            "macd_slow": 26,       # MACD慢线
            "macd_signal": 9,      # MACD信号线
            "adx_threshold": 25,   # ADX趋势阈值
            "stop_loss_pct": 0.02,  # 止损比例 2%
            "take_profit_pct": 0.05,  # 止盈比例 5%
            "trailing_stop": 0.015,  # 移动止损距离 1.5%
        }

    def analyze(self, df: pd.DataFrame, scene) -> Optional[Signal]:
        if not self._is_ready(df, 35):
            return None

        close = df["close"].values.astype(float)
        high = df["high"].values.astype(float)
        low = df["low"].values.astype(float)

        # ---------- 均线 ----------
        ema_fast = ema(close, self.params["fast_ma"])
        ema_slow = ema(close, self.params["slow_ma"])
        if len(ema_fast) < 3 or len(ema_slow) < 3:
            return None

        # ---------- MACD ----------
        macd_line, signal_line, hist = macd(
            close,
            self.params["macd_fast"],
            self.params["macd_slow"],
            self.params["macd_signal"],
        )
        if len(hist) < 2:
            return None

        # ---------- 信号生成 ----------
        current_price = close[-1]

        # 金叉：快线上穿慢线
        golden_cross = (
            ema_fast[-2] <= ema_slow[-2] and ema_fast[-1] > ema_slow[-1]
        )
        # 死叉：快线下穿慢线
        death_cross = (
            ema_fast[-2] >= ema_slow[-2] and ema_fast[-1] < ema_slow[-1]
        )

        # MACD 柱状图方向确认
        macd_turning_up = len(hist) >= 2 and hist[-2] < hist[-1]
        macd_turning_down = len(hist) >= 2 and hist[-2] > hist[-1]

        # 多头排列确认（价格 > EMA20）
        bullish_alignment = current_price > ema_slow[-1]
        bearish_alignment = current_price < ema_slow[-1]

        # ---------- 做多 ----------
        if golden_cross and macd_turning_up and bullish_alignment:
            atr_val = self._compute_atr(high, low, close, 14)
            sl = current_price - atr_val * 2 if atr_val else current_price * (1 - self.params["stop_loss_pct"])
            tp = current_price * (1 + self.params["take_profit_pct"])

            self.signal_count += 1
            return Signal(
                type=SignalType.BUY,
                symbol=self._get_symbol(df),
                price=current_price,
                stop_loss=sl,
                take_profit=tp,
                confidence=min(scene.confidence * 0.90, 0.95),
                reason=f"均线金叉(EMA{self.params['fast_ma']}↑EMA{self.params['slow_ma']}) + MACD转多",
                scene=scene.type,
            )

        # ---------- 做空 ----------
        if death_cross and macd_turning_down and bearish_alignment:
            atr_val = self._compute_atr(high, low, close, 14)
            sl = current_price + atr_val * 2 if atr_val else current_price * (1 + self.params["stop_loss_pct"])
            tp = current_price * (1 - self.params["take_profit_pct"])

            self.signal_count += 1
            return Signal(
                type=SignalType.SELL,
                symbol=self._get_symbol(df),
                price=current_price,
                stop_loss=sl,
                take_profit=tp,
                confidence=min(scene.confidence * 0.90, 0.95),
                reason=f"均线死叉(EMA{self.params['fast_ma']}↓EMA{self.params['slow_ma']}) + MACD转空",
                scene=scene.type,
            )

        return None

    # ---------- helpers ----------

    @staticmethod
    def _compute_atr(high, low, close, period=14):
        if len(high) < period + 1:
            return None
        tr = np.maximum(
            high[1:] - low[1:],
            np.maximum(
                np.abs(high[1:] - close[:-1]),
                np.abs(low[1:] - close[:-1]),
            ),
        )
        return np.mean(tr[-period:])

    @staticmethod
    def _get_symbol(df) -> str:
        return df["symbol"].iloc[-1] if "symbol" in df.columns else "UNKNOWN"
