"""
技术指标模块

提供常用的技术分析指标计算。
"""

import numpy as np
import pandas as pd
from typing import List, Tuple, Optional


def sma(data: np.ndarray, period: int) -> np.ndarray:
    """简单移动平均线"""
    return np.convolve(data, np.ones(period) / period, mode="valid")


def ema(data: np.ndarray, period: int) -> np.ndarray:
    """指数移动平均线"""
    alpha = 2 / (period + 1)
    ema_values = np.zeros_like(data)
    ema_values[0] = data[0]

    for i in range(1, len(data)):
        ema_values[i] = alpha * data[i] + (1 - alpha) * ema_values[i - 1]

    return ema_values


def rsi(data: np.ndarray, period: int = 14) -> np.ndarray:
    """
    相对强弱指数 (RSI)

    Args:
        data: 收盘价数组
        period: 计算周期，默认14

    Returns:
        RSI值数组 (0-100)
    """
    deltas = np.diff(data)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)

    avg_gains = np.convolve(gains, np.ones(period) / period, mode="valid")
    avg_losses = np.convolve(losses, np.ones(period) / period, mode="valid")

    rs = avg_gains / (avg_losses + 1e-10)
    rsi_values = 100 - (100 / (1 + rs))

    return rsi_values


def macd(data: np.ndarray, fast: int = 12, slow: int = 26,
         signal: int = 9) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    MACD指标

    Args:
        data: 收盘价数组
        fast: 快线周期
        slow: 慢线周期
        signal: 信号线周期

    Returns:
        (macd_line, signal_line, histogram)
    """
    ema_fast = ema(data, fast)
    ema_slow = ema(data, slow)

    # 对齐长度
    min_len = min(len(ema_fast), len(ema_slow))
    ema_fast = ema_fast[-min_len:]
    ema_slow = ema_slow[-min_len:]

    macd_line = ema_fast - ema_slow
    signal_line = ema(macd_line, signal)

    # 对齐histogram
    min_len = min(len(macd_line), len(signal_line))
    macd_line = macd_line[-min_len:]
    signal_line = signal_line[-min_len:]
    histogram = macd_line - signal_line

    return macd_line, signal_line, histogram


def bollinger_bands(data: np.ndarray, period: int = 20,
                    std_dev: float = 2.0) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    布林带

    Args:
        data: 收盘价数组
        period: 计算周期
        std_dev: 标准差倍数

    Returns:
        (upper_band, middle_band, lower_band)
    """
    middle_band = sma(data, period)

    # 计算标准差
    std_values = np.array([
        np.std(data[i:i + period])
        for i in range(len(data) - period + 1)
    ])

    upper_band = middle_band + std_dev * std_values
    lower_band = middle_band - std_dev * std_values

    return upper_band, middle_band, lower_band


def atr(high: np.ndarray, low: np.ndarray, close: np.ndarray,
        period: int = 14) -> np.ndarray:
    """
    平均真实波幅 (ATR)

    Args:
        high: 最高价数组
        low: 最低价数组
        close: 收盘价数组
        period: 计算周期

    Returns:
        ATR值数组
    """
    tr1 = high[1:] - low[1:]
    tr2 = np.abs(high[1:] - close[:-1])
    tr3 = np.abs(low[1:] - close[:-1])

    tr = np.maximum(np.maximum(tr1, tr2), tr3)

    atr_values = np.convolve(tr, np.ones(period) / period, mode="valid")

    return atr_values


def adx(high: np.ndarray, low: np.ndarray, close: np.ndarray,
        period: int = 14) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    平均趋向指数 (ADX)

    Args:
        high: 最高价数组
        low: 最低价数组
        close: 收盘价数组
        period: 计算周期

    Returns:
        (adx, plus_di, minus_di)
    """
    # +DM 和 -DM
    plus_dm = np.where(
        (high[1:] - high[:-1]) > (low[:-1] - low[1:]),
        np.maximum(high[1:] - high[:-1], 0),
        0
    )
    minus_dm = np.where(
        (low[:-1] - low[1:]) > (high[1:] - high[:-1]),
        np.maximum(low[:-1] - low[1:], 0),
        0
    )

    # 真实波幅
    tr1 = high[1:] - low[1:]
    tr2 = np.abs(high[1:] - close[:-1])
    tr3 = np.abs(low[1:] - close[:-1])
    tr = np.maximum(np.maximum(tr1, tr2), tr3)

    # 平滑
    atr_values = np.convolve(tr, np.ones(period) / period, mode="valid")
    plus_di_values = np.convolve(plus_dm, np.ones(period) / period, mode="valid")
    minus_di_values = np.convolve(minus_dm, np.ones(period) / period, mode="valid")

    # 对齐长度
    min_len = min(len(atr_values), len(plus_di_values), len(minus_di_values))
    atr_values = atr_values[-min_len:]
    plus_di_values = plus_di_values[-min_len:]
    minus_di_values = minus_di_values[-min_len:]

    # DI
    plus_di = 100 * plus_di_values / (atr_values + 1e-10)
    minus_di = 100 * minus_di_values / (atr_values + 1e-10)

    # DX
    dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)

    # ADX
    adx_values = np.convolve(dx, np.ones(period) / period, mode="valid")

    return adx_values, plus_di[-len(adx_values):], minus_di[-len(adx_values):]


def volume_profile(volume: np.ndarray, close: np.ndarray,
                   bins: int = 10) -> Tuple[np.ndarray, np.ndarray]:
    """
    成交量分布

    Args:
        volume: 成交量数组
        close: 收盘价数组
        bins: 价格分档数

    Returns:
        (price_levels, volume_at_levels)
    """
    min_price = np.min(close)
    max_price = np.max(close)
    bin_size = (max_price - min_price) / bins

    price_levels = np.linspace(min_price + bin_size / 2, max_price - bin_size / 2, bins)
    volume_at_levels = np.zeros(bins)

    for i in range(len(close)):
        bin_idx = int((close[i] - min_price) / bin_size)
        bin_idx = min(bin_idx, bins - 1)
        volume_at_levels[bin_idx] += volume[i]

    return price_levels, volume_at_levels


def support_resistance(high: np.ndarray, low: np.ndarray,
                        close: np.ndarray, lookback: int = 20,
                        tolerance: float = 0.02) -> Tuple[List[float], List[float]]:
    """
    支撑阻力位识别

    Args:
        high: 最高价数组
        low: 最低价数组
        close: 收盘价数组
        lookback: 回看周期
        tolerance: 价格容忍度（比例）

    Returns:
        (支撑位列表, 阻力位列表)
    """
    supports = []
    resistances = []

    for i in range(lookback, len(high) - 1):
        # 检查是否是局部低点
        if low[i] == np.min(low[i - lookback:i + 1]):
            supports.append(low[i])

        # 检查是否是局部高点
        if high[i] == np.max(high[i - lookback:i + 1]):
            resistances.append(high[i])

    # 合并接近的价位
    def merge_levels(levels: List[float], tol: float) -> List[float]:
        if not levels:
            return []

        levels = sorted(levels)
        merged = [levels[0]]

        for level in levels[1:]:
            avg_price = np.mean(merged)
            if abs(level - avg_price) / avg_price < tol:
                merged.append(level)
            else:
                merged = [level]

        return merged

    return merge_levels(supports, tolerance), merge_levels(resistances, tolerance)


def calculate_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    计算所有技术指标

    Args:
        df: DataFrame包含 open, high, low, close, volume 列

    Returns:
        添加了技术指标列的DataFrame
    """
    close = df["close"].values
    high = df["high"].values
    low = df["low"].values
    volume = df["volume"].values

    # 移动平均线
    df["sma_5"] = np.nan
    df["sma_10"] = np.nan
    df["sma_20"] = np.nan
    df["sma_60"] = np.nan

    if len(close) >= 5:
        df.loc[4:, "sma_5"] = sma(close, 5)
    if len(close) >= 10:
        df.loc[9:, "sma_10"] = sma(close, 10)
    if len(close) >= 20:
        df.loc[19:, "sma_20"] = sma(close, 20)
    if len(close) >= 60:
        df.loc[59:, "sma_60"] = sma(close, 60)

    # EMA
    df["ema_12"] = ema(close, 12)
    df["ema_26"] = ema(close, 26)

    # RSI
    df["rsi_14"] = np.nan
    if len(close) >= 15:
        df.loc[14:, "rsi_14"] = rsi(close, 14)

    # MACD
    macd_line, signal_line, histogram = macd(close, 12, 26, 9)
    df["macd"] = np.nan
    df["macd_signal"] = np.nan
    df["macd_hist"] = np.nan

    macd_start = len(close) - len(macd_line)
    df.loc[macd_start:, "macd"] = macd_line
    signal_start = len(close) - len(signal_line)
    df.loc[signal_start:, "macd_signal"] = signal_line
    hist_start = len(close) - len(histogram)
    df.loc[hist_start:, "macd_hist"] = histogram

    # 布林带
    if len(close) >= 20:
        upper, middle, lower = bollinger_bands(close, 20, 2)
        bb_start = len(close) - len(upper)
        df.loc[bb_start:, "bb_upper"] = upper
        df.loc[bb_start:, "bb_middle"] = middle
        df.loc[bb_start:, "bb_lower"] = lower

    # ATR
    if len(high) >= 15:
        atr_values = atr(high, low, close, 14)
        atr_start = len(close) - len(atr_values)
        df.loc[atr_start:, "atr_14"] = atr_values

    # ADX
    if len(high) >= 28:
        adx_values, plus_di, minus_di = adx(high, low, close, 14)
        adx_start = len(close) - len(adx_values)
        df.loc[adx_start:, "adx_14"] = adx_values
        df.loc[adx_start:, "plus_di"] = plus_di
        df.loc[adx_start:, "minus_di"] = minus_di

    # 成交量指标
    df["volume_sma_20"] = np.nan
    if len(volume) >= 20:
        df.loc[19:, "volume_sma_20"] = sma(volume, 20)

    df["volume_ratio"] = df["volume"] / df["volume_sma_20"]

    return df
