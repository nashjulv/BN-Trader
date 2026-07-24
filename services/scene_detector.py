"""
场景识别引擎

自动识别当前市场行情场景，为策略选择提供依据。
"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

import numpy as np
import pandas as pd

from indicators.technical import calculate_all_indicators, adx, atr, bollinger_bands
from config import Config

logger = logging.getLogger(__name__)


@dataclass
class Scene:
    """行情场景数据类"""
    type: str  # TRENDING, RANGING, BREAKOUT, REVERSAL, EXTREME
    confidence: float  # 置信度 0-1
    trend_strength: float  # 趋势强度
    volatility: float  # 波动率
    volume_change: float  # 成交量变化
    price_position: float  # 价格位置 (-1 到 1)
    is_breakout: bool  # 是否突破
    is_divergence: bool  # 是否背离
    description: str  # 场景描述
    position_ratio: float  # 建议仓位比例
    scene_scores: Dict[str, float] = None  # 五种场景的原始评分


class SceneDetector:
    """行情场景识别器"""

    # 场景类型定义
    SCENE_TYPES = {
        "TRENDING": {
            "name": "趋势行情",
            "description": "价格沿一个方向持续运动",
            "position_ratio": 0.40,
            "color": "#4CAF50"  # 绿色
        },
        "RANGING": {
            "name": "震荡行情",
            "description": "价格在区间内波动",
            "position_ratio": 0.25,
            "color": "#2196F3"  # 蓝色
        },
        "BREAKOUT": {
            "name": "突破行情",
            "description": "价格突破关键价位",
            "position_ratio": 0.50,
            "color": "#FF9800"  # 橙色
        },
        "REVERSAL": {
            "name": "反转行情",
            "description": "趋势可能出现反转",
            "position_ratio": 0.15,
            "color": "#9C27B0"  # 紫色
        },
        "EXTREME": {
            "name": "极端行情",
            "description": "价格剧烈波动，情绪极端",
            "position_ratio": 0.05,
            "color": "#F44336"  # 红色
        }
    }

    def __init__(self):
        self.min_klines = Config.MIN_KLINES_FOR_DETECTION
        self.last_scene: Optional[Scene] = None
        self.scene_history: List[Scene] = []

    def detect(self, df: pd.DataFrame) -> Scene:
        """
        识别当前行情场景

        Args:
            df: 包含K线数据的DataFrame，需要预先计算技术指标

        Returns:
            Scene: 识别出的场景
        """
        if len(df) < self.min_klines:
            logger.warning(f"K线数据不足，需要至少{self.min_klines}条")
            return self._create_default_scene()

        # 获取最新数据
        latest = df.iloc[-1]
        recent = df.tail(50)

        # 1. 计算各项指标
        trend_strength = self._calculate_trend_strength(df)
        volatility = self._calculate_volatility(df)
        volume_change = self._calculate_volume_change(df)
        price_position = self._calculate_price_position(df)
        is_breakout = self._detect_breakout(df)
        is_divergence = self._detect_divergence(df)

        # 2. 场景评分
        scores = self._score_scenes(
            trend_strength, volatility, volume_change,
            price_position, is_breakout, is_divergence
        )

        # 3. 选择最高分的场景
        best_scene = max(scores, key=scores.get)
        confidence = scores[best_scene]

        # 4. 构建场景对象
        scene = Scene(
            type=best_scene,
            confidence=confidence,
            trend_strength=trend_strength,
            volatility=volatility,
            volume_change=volume_change,
            price_position=price_position,
            is_breakout=is_breakout,
            is_divergence=is_divergence,
            description=self.SCENE_TYPES[best_scene]["description"],
            position_ratio=self.SCENE_TYPES[best_scene]["position_ratio"] * confidence,
            scene_scores=scores,
        )

        self.last_scene = scene
        self.scene_history.append(scene)

        # 只保留最近100个场景记录
        if len(self.scene_history) > 100:
            self.scene_history = self.scene_history[-100:]

        logger.info(
            f"场景识别: {scene.type} (置信度: {confidence:.2f}, "
            f"建议仓位: {scene.position_ratio:.1%})"
        )

        return scene

    def _calculate_trend_strength(self, df: pd.DataFrame) -> float:
        """计算趋势强度 (0-1)"""
        if "adx_14" not in df.columns or df["adx_14"].isna().all():
            # 使用简单方法计算
            closes = df["close"].values
            if len(closes) < 20:
                return 0.5

            # 计算价格变化方向的一致性
            changes = np.diff(closes[-20:])
            positive = np.sum(changes > 0)
            negative = np.sum(changes < 0)
            total = positive + negative

            if total == 0:
                return 0.5

            # 方向一致性越高，趋势越强
            consistency = abs(positive - negative) / total
            return consistency

        # 使用ADX
        adx_value = df["adx_14"].dropna().iloc[-1] if not df["adx_14"].dropna().empty else 25
        return min(adx_value / 100, 1.0)

    def _calculate_volatility(self, df: pd.DataFrame) -> float:
        """计算波动率 (0-1)"""
        if "atr_14" not in df.columns or df["atr_14"].isna().all():
            # 使用标准差
            closes = df["close"].values[-20:]
            if len(closes) < 2:
                return 0.5

            std = np.std(closes)
            mean = np.mean(closes)
            cv = std / mean if mean > 0 else 0

            # 归一化到0-1
            return min(cv * 10, 1.0)

        # 使用ATR
        atr_value = df["atr_14"].dropna().iloc[-1] if not df["atr_14"].dropna().empty else 0
        close = df["close"].iloc[-1]
        return min(atr_value / close * 5, 1.0) if close > 0 else 0

    def _calculate_volume_change(self, df: pd.DataFrame) -> float:
        """计算成交量变化 (-1 到 1)"""
        if len(df) < 20:
            return 0.0

        recent_volume = df["volume"].tail(5).mean()
        historical_volume = df["volume"].tail(20).mean()

        if historical_volume == 0:
            return 0.0

        change = (recent_volume - historical_volume) / historical_volume
        return max(-1, min(1, change))

    def _calculate_price_position(self, df: pd.DataFrame) -> float:
        """计算价格在布林带中的位置 (-1 到 1)"""
        if "bb_upper" not in df.columns or df["bb_upper"].isna().all():
            # 使用简单范围
            high = df["high"].tail(20).max()
            low = df["low"].tail(20).min()
            close = df["close"].iloc[-1]

            if high == low:
                return 0.0

            return (close - low) / (high - low) * 2 - 1

        # 使用布林带
        upper = df["bb_upper"].dropna().iloc[-1]
        lower = df["bb_lower"].dropna().iloc[-1]
        close = df["close"].iloc[-1]

        if upper == lower:
            return 0.0

        return (close - lower) / (upper - lower) * 2 - 1

    def _detect_breakout(self, df: pd.DataFrame) -> bool:
        """检测是否突破"""
        if len(df) < 20:
            return False

        recent = df.tail(5)
        historical = df.tail(20).head(15)

        high_max = historical["high"].max()
        low_min = historical["low"].min()

        # 突破高点
        if recent["high"].max() > high_max * 1.01:
            return True

        # 突破低点
        if recent["low"].min() < low_min * 0.99:
            return True

        return False

    def _detect_divergence(self, df: pd.DataFrame) -> bool:
        """检测背离"""
        if len(df) < 20:
            return False

        # 价格创新高/低，但指标没有
        closes = df["close"].values[-20:]

        # 简单检测：价格趋势与RSI趋势相反
        if "rsi_14" in df.columns and not df["rsi_14"].isna().all():
            rsi_values = df["rsi_14"].dropna().values[-20:]
            if len(rsi_values) >= 10:
                price_trend = closes[-1] - closes[-10]
                rsi_trend = rsi_values[-1] - rsi_values[-10]

                # 价格上升但RSI下降（顶背离）
                # 或价格下降但RSI上升（底背离）
                if price_trend * rsi_trend < 0:
                    return True

        return False

    def _score_scenes(self, trend_strength: float, volatility: float,
                      volume_change: float, price_position: float,
                      is_breakout: bool, is_divergence: bool) -> Dict[str, float]:
        """
        为每个场景打分

        返回每个场景的置信度分数 (0-1)
        """
        scores = {}

        # 趋势行情评分
        # 高趋势强度 + 中等波动率 + 成交量放大
        scores["TRENDING"] = (
            trend_strength * 0.5 +
            (1 - abs(volatility - 0.5)) * 0.2 +
            max(0, volume_change) * 0.2 +
            (1 if not is_breakout else 0.3) * 0.1
        )

        # 震荡行情评分
        # 低趋势强度 + 价格在中间区域 + 成交量平稳
        scores["RANGING"] = (
            (1 - trend_strength) * 0.4 +
            (1 - abs(price_position)) * 0.3 +
            (1 - abs(volume_change)) * 0.2 +
            (1 if not is_breakout else 0) * 0.1
        )

        # 突破行情评分
        # 明确突破 + 成交量放大 + 高波动率
        scores["BREAKOUT"] = (
            (1 if is_breakout else 0) * 0.4 +
            max(0, volume_change) * 0.3 +
            volatility * 0.2 +
            (1 if abs(price_position) > 0.8 else 0) * 0.1
        )

        # 反转行情评分
        # 背离信号 + 趋势末期 + 极端价格位置
        scores["REVERSAL"] = (
            (1 if is_divergence else 0) * 0.4 +
            trend_strength * 0.2 +
            abs(price_position) * 0.2 +
            (1 if volume_change > 0.5 else 0) * 0.2
        )

        # 极端行情评分
        # 极高波动率 + 成交量异常 + 价格快速变化
        scores["EXTREME"] = (
            (1 if volatility > 0.8 else volatility) * 0.4 +
            abs(volume_change) * 0.3 +
            (1 if abs(price_position) > 0.9 else 0) * 0.2 +
            (1 if is_breakout and is_divergence else 0) * 0.1
        )

        # 归一化到0-1
        max_score = max(scores.values())
        if max_score > 0:
            scores = {k: v / max_score for k, v in scores.items()}

        return scores

    def _create_default_scene(self) -> Scene:
        """创建默认场景（数据不足时）"""
        return Scene(
            type="RANGING",
            confidence=0.5,
            trend_strength=0.5,
            volatility=0.5,
            volume_change=0.0,
            price_position=0.0,
            is_breakout=False,
            is_divergence=False,
            description="数据不足，默认震荡行情",
            position_ratio=0.1,
            scene_scores={k: 0.5 for k in self.SCENE_TYPES},
        )

    def get_scene_trend(self) -> str:
        """获取场景趋势（用于UI显示）"""
        if not self.scene_history or len(self.scene_history) < 3:
            return "未知"

        recent = self.scene_history[-3:]
        types = [s.type for s in recent]

        if len(set(types)) == 1:
            return "稳定"
        elif types[-1] != types[-2]:
            return "转变"
        else:
            return "过渡"

    def get_recommended_action(self, scene: Scene) -> str:
        """获取建议操作"""
        actions = {
            "TRENDING": "顺势交易，使用移动止损",
            "RANGING": "高抛低吸，区间边界交易",
            "BREAKOUT": "突破跟进，设置假突破止损",
            "REVERSAL": "逆势试探，严格止损",
            "EXTREME": "观望或极小仓位反向操作"
        }
        return actions.get(scene.type, "观望")
