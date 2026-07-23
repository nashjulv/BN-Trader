"""
场景识别引擎测试

验证5种行情场景的识别功能。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from services.scene_detector import SceneDetector
from indicators.technical import calculate_all_indicators


def generate_trending_data(length=200):
    """生成趋势行情数据"""
    np.random.seed(42)
    dates = pd.date_range(start="2024-01-01", periods=length, freq="15min")

    # 上升趋势
    price = 100 + np.cumsum(np.random.normal(0.5, 1, length))

    data = pd.DataFrame({
        "open": price + np.random.normal(0, 0.5, length),
        "high": price + np.random.normal(2, 1, length),
        "low": price - np.random.normal(2, 1, length),
        "close": price,
        "volume": np.random.uniform(100, 500, length),
    })

    # 确保OHLC逻辑正确
    for col in ["high", "low"]:
        data[col] = data[col].clip(lower=0)

    for i in range(length):
        o = data.loc[i, "open"]
        c = data.loc[i, "close"]
        data.loc[i, "high"] = max(data.loc[i, "high"], o, c)
        data.loc[i, "low"] = min(data.loc[i, "low"], o, c)

    return data


def generate_ranging_data(length=200):
    """生成震荡行情数据"""
    np.random.seed(123)
    dates = pd.date_range(start="2024-01-01", periods=length, freq="15min")

    # 区间震荡
    price = 100 + np.sin(np.linspace(0, 10 * np.pi, length)) * 5 + np.random.normal(0, 0.3, length)

    data = pd.DataFrame({
        "open": price + np.random.normal(0, 0.3, length),
        "high": price + np.random.normal(2, 0.5, length),
        "low": price - np.random.normal(2, 0.5, length),
        "close": price,
        "volume": np.random.uniform(80, 300, length),
    })

    for i in range(length):
        o = data.loc[i, "open"]
        c = data.loc[i, "close"]
        data.loc[i, "high"] = max(data.loc[i, "high"], o, c)
        data.loc[i, "low"] = min(data.loc[i, "low"], o, c)

    return data


def test_scene_detection():
    """测试场景识别"""
    detector = SceneDetector()
    print("=== 场景识别测试 ===\n")

    # 测试趋势数据
    print("1. 测试趋势行情...")
    trend_data = generate_trending_data(200)
    trend_data = calculate_all_indicators(trend_data)
    scene = detector.detect(trend_data)
    print(f"   场景类型: {scene.type}")
    print(f"   置信度: {scene.confidence:.2f}")
    print(f"   建议仓位: {scene.position_ratio:.1%}")
    print(f"   趋势强度: {scene.trend_strength:.2f}")
    print()

    # 测试震荡数据
    print("2. 测试震荡行情...")
    range_data = generate_ranging_data(200)
    range_data = calculate_all_indicators(range_data)
    scene = detector.detect(range_data)
    print(f"   场景类型: {scene.type}")
    print(f"   置信度: {scene.confidence:.2f}")
    print(f"   建议仓位: {scene.position_ratio:.1%}")
    print(f"   波动率: {scene.volatility:.2f}")
    print()

    # 验证场景历史
    print(f"3. 场景历史记录数: {len(detector.scene_history)}")
    print(f"   场景趋势: {detector.get_scene_trend()}")
    print(f"   建议操作: {detector.get_recommended_action(scene)}")

    print("\n✅ 场景识别测试完成!")


if __name__ == "__main__":
    test_scene_detection()
