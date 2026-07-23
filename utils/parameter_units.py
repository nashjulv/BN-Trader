"""参数单位转换与配置 schema 迁移。

界面中的百分比始终使用百分数（例如 0.7 表示 0.7%）；
持久化与业务计算始终使用小数比例（例如 0.007）。
"""

from copy import deepcopy
from decimal import Decimal
from math import isfinite
from typing import Mapping


CURRENT_PARAMETER_SCHEMA = 2

STRATEGY_PERCENT_FIELDS = frozenset({
    "breakout_pct",
    "stop_loss_pct",
    "take_profit_pct",
    "trailing_stop",
})

GLOBAL_PERCENT_FIELDS = frozenset({
    "reserve_ratio",
    "max_single_trade_ratio",
    "daily_loss_limit",
    "max_loss_per_trade",
    "max_profit_per_trade",
    "max_drawdown",
    "min_reserve_ratio",
    "trailing_stop_pct",
    "initial_position_ratio",
    "scale_in_ratio",
    "max_position_ratio",
    "take_profit_trigger",
    "breakeven_stop",
})

# schema v1 的全局设置并非统一单位：这三个字段保存的是界面百分数，
# 其余 GLOBAL_PERCENT_FIELDS 已经保存为小数比例。
LEGACY_GLOBAL_PERCENT_POINT_FIELDS = frozenset({
    "trailing_stop_pct",
    "take_profit_trigger",
    "breakeven_stop",
})


def percent_to_ratio(value: float) -> float:
    """把界面百分数转换为内部比例，不根据数值大小猜测单位。"""
    number = float(value)
    if not isfinite(number):
        raise ValueError("百分比必须是有限数值")
    if not 0 <= number <= 100:
        raise ValueError("百分比必须在 0% 到 100% 之间")
    return float(Decimal(str(number)) / Decimal("100"))


def ratio_to_percent(value: float) -> float:
    """把内部比例转换为界面百分数。"""
    number = float(value)
    if not isfinite(number):
        raise ValueError("比例必须是有限数值")
    if not 0 <= number <= 1:
        raise ValueError("比例必须在 0 到 1 之间")
    return float(Decimal(str(number)) * Decimal("100"))


def strategy_runtime_params(values: Mapping) -> dict:
    """返回已经使用内部比例单位的策略运行参数。"""
    return {
        key: value
        for key, value in values.items()
        if key not in {"enabled", "_schema_version"}
    }


def migrate_strategy_settings(data: Mapping) -> tuple[dict, bool]:
    """将策略 schema v1 的百分数迁移为 schema v2 小数比例。"""
    migrated = deepcopy(dict(data))
    version = int(migrated.get("_schema_version", 1) or 1)
    changed = version < CURRENT_PARAMETER_SCHEMA
    if changed:
        for scene_values in migrated.values():
            if not isinstance(scene_values, dict):
                continue
            for key in STRATEGY_PERCENT_FIELDS:
                value = scene_values.get(key)
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    scene_values[key] = percent_to_ratio(value)
        migrated["_schema_version"] = CURRENT_PARAMETER_SCHEMA
    return migrated, changed


def migrate_global_settings(data: Mapping) -> tuple[dict, bool]:
    """迁移全局 schema v1 中以百分数保存的少数历史字段。"""
    migrated = deepcopy(dict(data))
    version = int(migrated.get("_schema_version", 1) or 1)
    changed = version < CURRENT_PARAMETER_SCHEMA
    if changed:
        for section in migrated.values():
            if not isinstance(section, dict):
                continue
            for key in LEGACY_GLOBAL_PERCENT_POINT_FIELDS:
                value = section.get(key)
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    section[key] = percent_to_ratio(value)
        migrated["_schema_version"] = CURRENT_PARAMETER_SCHEMA
    return migrated, changed
