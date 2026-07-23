"""
辅助工具函数
"""

from datetime import datetime
from typing import Optional


def format_price(price: float, decimals: int = 2) -> str:
    """格式化价格"""
    return f"{price:,.{decimals}f}"


def format_percentage(value: float, decimals: int = 2) -> str:
    """格式化百分比"""
    return f"{value:+.{decimals}%}"


def format_quantity(quantity: float, decimals: int = 4) -> str:
    """格式化数量"""
    return f"{quantity:.{decimals}f}"


def calculate_profit_loss(entry_price: float, exit_price: float,
                         quantity: float, side: str) -> tuple[float, float]:
    """
    计算盈亏

    Returns:
        (profit_amount, profit_ratio)
    """
    if side.upper() == "BUY":
        profit = (exit_price - entry_price) * quantity
    else:
        profit = (entry_price - exit_price) * quantity

    capital = entry_price * quantity
    profit_ratio = profit / capital if capital > 0 else 0

    return profit, profit_ratio


def format_time_ago(timestamp: datetime) -> str:
    """格式化时间为"多久之前"的形式"""
    if not timestamp:
        return "--"

    now = datetime.utcnow()
    diff = now - timestamp if timestamp.tzinfo is None else now - timestamp.replace(tzinfo=None)

    seconds = int(diff.total_seconds())

    if seconds < 60:
        return f"{seconds}秒前"
    elif seconds < 3600:
        return f"{seconds // 60}分钟前"
    elif seconds < 86400:
        return f"{seconds // 3600}小时前"
    else:
        return f"{seconds // 86400}天前"


def validate_stop_loss(entry_price: float, stop_loss: float,
                       side: str, max_loss_ratio: float = 0.05) -> tuple[bool, str]:
    """
    验证止损设置是否合理

    Returns:
        (is_valid, message)
    """
    if stop_loss <= 0:
        return False, "请设置止损价格"

    if side.upper() == "BUY":
        loss_ratio = (entry_price - stop_loss) / entry_price
    else:
        loss_ratio = (stop_loss - entry_price) / entry_price

    if loss_ratio <= 0:
        return False, "止损方向错误"

    if loss_ratio > max_loss_ratio:
        return False, f"止损比例过大: {loss_ratio:.2%}"

    return True, f"止损比例: {loss_ratio:.2%}"


def validate_risk_reward(entry_price: float, stop_loss: float,
                        take_profit: float, side: str,
                        min_ratio: float = 1.5) -> tuple[bool, str]:
    """
    验证盈亏比

    Returns:
        (is_valid, message)
    """
    if entry_price <= 0 or stop_loss <= 0 or take_profit <= 0:
        return False, "价格参数不完整"

    if side.upper() == "BUY":
        risk = entry_price - stop_loss
        reward = take_profit - entry_price
    else:
        risk = stop_loss - entry_price
        reward = entry_price - take_profit

    if risk <= 0:
        return False, "止损设置无效"

    if reward <= 0:
        return False, "止盈设置无效"

    rr_ratio = reward / risk

    if rr_ratio < min_ratio:
        return False, f"盈亏比不足: {rr_ratio:.1f}:1 (建议≥{min_ratio}:1)"

    return True, f"盈亏比: {rr_ratio:.1f}:1"
