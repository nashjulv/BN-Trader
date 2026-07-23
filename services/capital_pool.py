"""
资金池管理

管理交易资金，包括分配、回收和风险控制。
"""

import logging
from typing import Optional, Dict
from dataclasses import dataclass

from config import Config

logger = logging.getLogger(__name__)


@dataclass
class TradeResult:
    """交易结果"""
    profit: float  # 盈亏金额
    profit_ratio: float  # 盈亏比例
    capital_used: float  # 使用资金
    is_win: bool  # 是否盈利


class CapitalPool:
    """资金池管理器"""

    def __init__(self, total_capital: float = None):
        """
        初始化资金池

        Args:
            total_capital: 总资金，默认使用配置值
        """
        self.total = total_capital or Config.DEFAULT_TOTAL_CAPITAL
        self.reserve_ratio = Config.RESERVE_RATIO
        self.max_single_trade_ratio = Config.MAX_SINGLE_TRADE_RATIO
        self.daily_loss_limit = Config.DAILY_LOSS_LIMIT

        # 资金分配
        self.reserve = self.total * self.reserve_ratio  # 风险准备金
        self.available = self.total - self.reserve  # 可用资金
        self.locked = 0.0  # 冻结资金
        self.margin = 0.0  # 持仓保证金

        # 统计
        self.daily_pnl = 0.0  # 今日盈亏
        self.daily_pnl_ratio = 0.0  # 今日盈亏比例
        self.total_trades = 0  # 总交易次数
        self.win_count = 0  # 盈利次数
        self.loss_count = 0  # 亏损次数
        self.consecutive_loss = 0  # 连续亏损次数
        self.max_consecutive_loss = 0  # 最大连续亏损

        # 回撤
        self.peak_capital = self.total  # 资金峰值
        self.max_drawdown = 0.0  # 最大回撤
        self.current_drawdown = 0.0  # 当前回撤

        # 仓位调整
        self.position_multiplier = 1.0  # 仓位倍数（根据盈亏调整）
        self.win_streak = 0  # 连胜次数

        logger.info(f"资金池初始化完成: 总额={self.total:.2f}, 准备金={self.reserve:.2f}")

    def allocate_for_trade(self, scene_type: str, confidence: float,
                          risk_per_trade: float = None) -> float:
        """
        为交易分配资金

        Args:
            scene_type: 当前场景类型
            confidence: 场景置信度 (0-1)
            risk_per_trade: 单笔风险比例，默认使用配置

        Returns:
            可分配的仓位金额
        """
        if risk_per_trade is None:
            risk_per_trade = Config.MAX_LOSS_PER_TRADE

        # 场景基础仓位比例
        scene_ratios = {
            "TRENDING": 0.40,
            "RANGING": 0.25,
            "BREAKOUT": 0.50,
            "REVERSAL": 0.15,
            "EXTREME": 0.05
        }

        base_ratio = scene_ratios.get(scene_type, 0.20)

        # 根据置信度调整
        adjusted_ratio = base_ratio * confidence

        # 应用连胜/连败调整
        adjusted_ratio *= self.position_multiplier

        # 计算最大允许仓位
        max_allowed = self.total * self.max_single_trade_ratio

        # 检查可用资金
        effective_available = self.available - self.locked - self.margin

        # 计算基于风险的仓位
        # 仓位 = 风险金额 / 止损比例
        risk_amount = self.total * risk_per_trade
        stop_loss_ratio = 0.02  # 假设2%止损
        position_by_risk = risk_amount / stop_loss_ratio

        # 取最小值
        allocation = min(
            effective_available,
            max_allowed,
            self.total * adjusted_ratio,
            position_by_risk
        )

        # 确保至少有一定资金
        allocation = max(allocation, 0)

        logger.info(
            f"资金分配: 场景={scene_type}, 置信度={confidence:.2f}, "
            f"分配={allocation:.2f}, 可用={effective_available:.2f}"
        )

        return allocation

    def lock_capital(self, amount: float):
        """锁定资金（下单时）"""
        if amount > self.available - self.locked - self.margin:
            logger.warning("可用资金不足，无法锁定")
            return False

        self.locked += amount
        logger.info(f"锁定资金: {amount:.2f}, 已锁定={self.locked:.2f}")
        return True

    def unlock_capital(self, amount: float):
        """解锁资金（订单取消或成交后）"""
        self.locked = max(0, self.locked - amount)
        logger.info(f"解锁资金: {amount:.2f}, 已锁定={self.locked:.2f}")

    def add_margin(self, amount: float):
        """增加持仓保证金"""
        self.margin += amount
        self.locked = max(0, self.locked - amount)  # 从锁定转为保证金
        logger.info(f"增加保证金: {amount:.2f}, 总保证金={self.margin:.2f}")

    def release_margin(self, amount: float):
        """释放持仓保证金"""
        self.margin = max(0, self.margin - amount)
        logger.info(f"释放保证金: {amount:.2f}, 总保证金={self.margin:.2f}")

    def update_after_trade(self, result: TradeResult):
        """
        交易完成后更新资金池

        Args:
            result: 交易结果
        """
        # 更新盈亏
        self.daily_pnl += result.profit
        self.daily_pnl_ratio = self.daily_pnl / self.total

        # 更新资金
        self.total += result.profit
        self.available += result.profit

        # 更新统计
        self.total_trades += 1

        if result.is_win:
            self.win_count += 1
            self.consecutive_loss = 0
            self.win_streak += 1

            # 连胜奖励：增加仓位倍数
            if self.win_streak >= 2:
                self.position_multiplier = min(1.5, 1.0 + self.win_streak * 0.1)
                logger.info(f"连胜{self.win_streak}次，仓位倍数调整为{self.position_multiplier:.2f}")
        else:
            self.loss_count += 1
            self.consecutive_loss += 1
            self.win_streak = 0

            # 连败惩罚：减少仓位倍数
            if self.consecutive_loss >= 2:
                self.position_multiplier = max(0.5, 1.0 - self.consecutive_loss * 0.15)
                logger.info(f"连败{self.consecutive_loss}次，仓位倍数调整为{self.position_multiplier:.2f}")

            # 更新最大连续亏损
            if self.consecutive_loss > self.max_consecutive_loss:
                self.max_consecutive_loss = self.consecutive_loss

        # 更新回撤
        if self.total > self.peak_capital:
            self.peak_capital = self.total
            self.current_drawdown = 0.0
        else:
            self.current_drawdown = (self.peak_capital - self.total) / self.peak_capital

        if self.current_drawdown > self.max_drawdown:
            self.max_drawdown = self.current_drawdown

        # 更新准备金
        self.reserve = self.total * self.reserve_ratio

        # 确保可用资金不为负
        self.available = max(0, self.available)

        logger.info(
            f"交易后更新: 盈亏={result.profit:.2f}, 总额={self.total:.2f}, "
            f"可用={self.available:.2f}, 回撤={self.current_drawdown:.2%}"
        )

    def reset_daily(self):
        """重置日度统计"""
        self.daily_pnl = 0.0
        self.daily_pnl_ratio = 0.0
        logger.info("日度统计已重置")

    def get_status(self) -> Dict:
        """获取资金池状态"""
        win_rate = self.win_count / max(self.total_trades, 1)

        return {
            "total": self.total,
            "available": self.available,
            "locked": self.locked,
            "margin": self.margin,
            "reserve": self.reserve,
            "daily_pnl": self.daily_pnl,
            "daily_pnl_ratio": self.daily_pnl_ratio,
            "total_trades": self.total_trades,
            "win_count": self.win_count,
            "loss_count": self.loss_count,
            "win_rate": win_rate,
            "consecutive_loss": self.consecutive_loss,
            "max_drawdown": self.max_drawdown,
            "current_drawdown": self.current_drawdown,
            "position_multiplier": self.position_multiplier
        }

    def can_trade(self) -> tuple[bool, str]:
        """检查是否可以交易"""
        # 检查日亏损
        if self.daily_pnl_ratio <= -self.daily_loss_limit:
            return False, f"日亏损超限: {self.daily_pnl_ratio:.2%}"

        # 检查连续亏损
        if self.consecutive_loss >= Config.MAX_CONSECUTIVE_LOSS:
            return False, f"连续亏损{self.consecutive_loss}次，需要复盘"

        # 检查回撤
        if self.current_drawdown >= Config.MAX_DRAWDOWN:
            return False, f"回撤超限: {self.current_drawdown:.2%}"

        # 检查可用资金
        effective_available = self.available - self.locked - self.margin
        if effective_available < self.total * 0.05:
            return False, "可用资金不足"

        return True, "可以交易"

    def get_summary(self) -> str:
        """获取资金池摘要"""
        win_rate = self.win_count / max(self.total_trades, 1) * 100

        return (
            f"资金池状态:\n"
            f"  总资金: {self.total:.2f}\n"
            f"  可用: {self.available:.2f}\n"
            f"  锁定: {self.locked:.2f}\n"
            f"  保证金: {self.margin:.2f}\n"
            f"  准备金: {self.reserve:.2f}\n"
            f"  今日盈亏: {self.daily_pnl:.2f} ({self.daily_pnl_ratio:.2%})\n"
            f"  交易次数: {self.total_trades}\n"
            f"  胜率: {win_rate:.1f}%\n"
            f"  连续亏损: {self.consecutive_loss}\n"
            f"  当前回撤: {self.current_drawdown:.2%}\n"
            f"  最大回撤: {self.max_drawdown:.2%}\n"
            f"  仓位倍数: {self.position_multiplier:.2f}x"
        )
