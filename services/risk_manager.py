"""
风控管理模块

提供多层风控机制，包括单笔风控、日度风控和账户风控。
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

from config import Config

logger = logging.getLogger(__name__)


@dataclass
class RiskCheck:
    """风控检查结果"""
    allowed: bool  # 是否允许
    level: str  # 级别: INFO, WARNING, CRITICAL, STOP
    message: str  # 提示信息
    detail: str = ""  # 详细信息


@dataclass
class RiskState:
    """风控状态"""
    # 单笔风控
    single_loss_ratio: float = 0.0  # 单笔亏损比例
    single_profit_ratio: float = 0.0  # 单笔盈利比例
    hold_time: int = 0  # 持仓时间(秒)
    slippage: float = 0.0  # 滑点

    # 日度风控
    daily_loss: float = 0.0  # 日亏损金额
    daily_loss_ratio: float = 0.0  # 日亏损比例
    daily_trades: int = 0  # 日交易次数
    consecutive_loss: int = 0  # 连续亏损次数
    last_loss_time: datetime = None  # 上次亏损时间
    cooldown_until: datetime = None  # 冷却结束时间

    # 账户风控
    total_drawdown: float = 0.0  # 总回撤比例
    reserve_ratio: float = 0.0  # 准备金比例
    account_loss: float = 0.0  # 账户总亏损

    # 强制复盘触发
    needs_review: bool = False  # 是否需要复盘
    review_reason: str = ""  # 复盘原因


class RiskManager:
    """风险管理器"""

    def __init__(self):
        # 风控配置
        self.single_limits = {
            "max_loss_ratio": Config.MAX_LOSS_PER_TRADE,  # 单笔最大亏损2%
            "max_profit_ratio": Config.MAX_PROFIT_PER_TRADE,  # 单笔止盈5%
            "max_hold_time": Config.MAX_HOLD_TIME,  # 最大持仓1小时
            "max_slippage": 0.001,  # 最大滑点0.1%
            "max_position_ratio": Config.MAX_SINGLE_TRADE_RATIO,
        }

        self.daily_limits = {
            "max_daily_loss": Config.DAILY_LOSS_LIMIT,  # 日亏损5%
            "max_daily_trades": Config.MAX_DAILY_TRADES,  # 日最大20笔
            "max_consecutive_loss": Config.MAX_CONSECUTIVE_LOSS,  # 连续亏损3次
            "cooldown_seconds": Config.COOLDOWN_SECONDS,  # 冷却300秒
        }

        self.account_limits = {
            "max_drawdown": Config.MAX_DRAWDOWN,  # 最大回撤20%
            "min_reserve_ratio": 0.10,  # 最低准备金10%
            "forced_stop_loss": 0.30,  # 强制止损30%
        }

        # 状态
        self.state = RiskState()
        self.risk_logs: List[Dict] = []  # 风控日志
        self.is_trading_allowed = True  # 是否允许交易
        self.review_required = False  # 是否需要复盘

        logger.info("风控管理器初始化完成")

    def check_trade_permission(self, capital: float, position_size: float,
                               entry_price: float, stop_loss: float = None) -> RiskCheck:
        """
        检查交易权限

        Args:
            capital: 当前总资金
            position_size: 计划仓位大小
            entry_price: 入场价格
            stop_loss: 止损价格

        Returns:
            RiskCheck: 风控检查结果
        """
        # 检查是否被禁止交易
        if not self.is_trading_allowed:
            return RiskCheck(
                allowed=False,
                level="STOP",
                message="交易已被禁止",
                detail="请联系管理员或完成复盘后恢复"
            )

        # 检查冷却期
        if self.state.cooldown_until and datetime.now() < self.state.cooldown_until:
            remaining = (self.state.cooldown_until - datetime.now()).seconds
            return RiskCheck(
                allowed=False,
                level="STOP",
                message=f"冷却期中，还需等待{remaining}秒",
                detail="连续亏损后需要冷静"
            )

        # 检查日亏损
        if self.state.daily_loss_ratio <= -self.daily_limits["max_daily_loss"]:
            return RiskCheck(
                allowed=False,
                level="STOP",
                message=f"日亏损超限: {self.state.daily_loss_ratio:.2%}",
                detail=f"超过限制{self.daily_limits['max_daily_loss']:.2%}"
            )

        # 检查交易次数
        if self.state.daily_trades >= self.daily_limits["max_daily_trades"]:
            return RiskCheck(
                allowed=False,
                level="STOP",
                message=f"日交易次数超限: {self.state.daily_trades}次",
                detail=f"超过限制{self.daily_limits['max_daily_trades']}次"
            )

        # 检查连续亏损
        if self.state.consecutive_loss >= self.daily_limits["max_consecutive_loss"]:
            return RiskCheck(
                allowed=False,
                level="CRITICAL",
                message=f"连续亏损{self.state.consecutive_loss}次",
                detail="触发强制复盘机制"
            )

        # 检查回撤
        if self.state.total_drawdown >= self.account_limits["max_drawdown"]:
            return RiskCheck(
                allowed=False,
                level="STOP",
                message=f"回撤超限: {self.state.total_drawdown:.2%}",
                detail=f"超过限制{self.account_limits['max_drawdown']:.2%}"
            )

        # 检查准备金
        if self.state.reserve_ratio < self.account_limits["min_reserve_ratio"]:
            return RiskCheck(
                allowed=False,
                level="WARNING",
                message=f"准备金不足: {self.state.reserve_ratio:.2%}",
                detail=f"低于最低要求{self.account_limits['min_reserve_ratio']:.2%}"
            )

        # 检查单笔风险
        if stop_loss and entry_price > 0:
            risk_ratio = abs(entry_price - stop_loss) / entry_price
            if risk_ratio > self.single_limits["max_loss_ratio"]:
                return RiskCheck(
                    allowed=False,
                    level="WARNING",
                    message=f"单笔风险过大: {risk_ratio:.2%}",
                    detail=(
                        f"入场价 {entry_price:g}，止损价 {stop_loss:g}；"
                        f"超过限制{self.single_limits['max_loss_ratio']:.2%}"
                    )
                )

        # 检查仓位大小
        max_position_ratio = self.single_limits["max_position_ratio"]
        if position_size > capital * max_position_ratio:
            return RiskCheck(
                allowed=False,
                level="WARNING",
                message=f"仓位过大: {position_size:.2f}",
                detail=f"超过单笔最大限制{capital * max_position_ratio:.2f}"
            )

        return RiskCheck(
            allowed=True,
            level="INFO",
            message="交易检查通过",
            detail="所有风控条件满足"
        )

    def update_after_trade(self, profit: float, profit_ratio: float,
                          hold_time: int = 0):
        """
        交易完成后更新风控状态

        Args:
            profit: 盈亏金额
            profit_ratio: 盈亏比例
            hold_time: 持仓时间(秒)
        """
        self.state.daily_trades += 1

        if profit < 0:
            # 亏损
            self.state.daily_loss += abs(profit)
            self.state.daily_loss_ratio = self.state.daily_loss / 10000  # 假设总资金10000
            self.state.consecutive_loss += 1
            self.state.last_loss_time = datetime.now()

            # 检查是否需要冷却
            if self.state.consecutive_loss >= 2:
                self.state.cooldown_until = datetime.now() + timedelta(
                    seconds=self.daily_limits["cooldown_seconds"]
                )
                logger.warning(
                    f"连续亏损{self.state.consecutive_loss}次，进入冷却期"
                )

            # 检查是否需要强制复盘
            if self.state.consecutive_loss >= self.daily_limits["max_consecutive_loss"]:
                self._trigger_review("consecutive_loss")

        else:
            # 盈利
            self.state.consecutive_loss = 0
            self.state.cooldown_until = None

        # 更新单笔统计
        self.state.single_loss_ratio = abs(min(profit_ratio, 0))
        self.state.single_profit_ratio = max(profit_ratio, 0)
        self.state.hold_time = hold_time

        # 检查强制止损
        if self.state.daily_loss_ratio <= -self.account_limits["forced_stop_loss"]:
            self._trigger_review("forced_stop")

        logger.info(
            f"交易后风控更新: 盈亏={profit:.2f}, "
            f"日亏损={self.state.daily_loss:.2f}, "
            f"连续亏损={self.state.consecutive_loss}"
        )

    def record_order_execution(self):
        """记录本应用已被交易所接受或已模拟执行的一笔订单。"""
        self.state.daily_trades += 1
        logger.info("日交易次数更新: %s", self.state.daily_trades)

    def update_drawdown(self, current_capital: float, peak_capital: float):
        """更新回撤"""
        if peak_capital > 0:
            self.state.total_drawdown = (peak_capital - current_capital) / peak_capital
            self.state.reserve_ratio = current_capital * Config.RESERVE_RATIO / current_capital

    def _trigger_review(self, reason: str):
        """触发强制复盘"""
        self.review_required = True
        self.is_trading_allowed = False
        self.state.needs_review = True

        reasons = {
            "consecutive_loss": f"连续亏损{self.state.consecutive_loss}次",
            "daily_loss": f"日亏损达到{self.state.daily_loss_ratio:.2%}",
            "forced_stop": f"触发强制止损线{self.account_limits['forced_stop_loss']:.2%}",
            "drawdown": f"回撤达到{self.state.total_drawdown:.2%}",
        }

        self.state.review_reason = reasons.get(reason, "未知原因")

        logger.critical(
            f"触发强制复盘: {self.state.review_reason}"
        )

        self._log_risk("REVIEW", "CRITICAL",
                       f"强制复盘: {self.state.review_reason}",
                       f"连续亏损: {self.state.consecutive_loss}, "
                       f"日亏损: {self.state.daily_loss_ratio:.2%}")

    def complete_review(self, approved: bool):
        """
        完成复盘

        Args:
            approved: 是否批准恢复交易
        """
        if approved:
            self.review_required = False
            self.is_trading_allowed = True
            self.state.needs_review = False
            self.state.consecutive_loss = 0
            self.state.cooldown_until = None

            logger.info("复盘完成，恢复交易权限")
        else:
            logger.warning("复盘未通过，继续禁止交易")

    def reset_daily(self):
        """重置日度统计"""
        self.state.daily_loss = 0.0
        self.state.daily_loss_ratio = 0.0
        self.state.daily_trades = 0
        self.state.consecutive_loss = 0
        self.state.cooldown_until = None

        logger.info("日度风控统计已重置")

    def _log_risk(self, type: str, level: str, message: str, detail: str = ""):
        """记录风控日志"""
        log_entry = {
            "type": type,
            "level": level,
            "message": message,
            "detail": detail,
            "timestamp": datetime.now()
        }
        self.risk_logs.append(log_entry)

        # 只保留最近100条
        if len(self.risk_logs) > 100:
            self.risk_logs = self.risk_logs[-100:]

    def get_risk_summary(self) -> Dict:
        """获取风控摘要"""
        return {
            "is_trading_allowed": self.is_trading_allowed,
            "review_required": self.review_required,
            "daily_loss": self.state.daily_loss,
            "daily_loss_ratio": self.state.daily_loss_ratio,
            "daily_trades": self.state.daily_trades,
            "consecutive_loss": self.state.consecutive_loss,
            "total_drawdown": self.state.total_drawdown,
            "needs_review": self.state.needs_review,
            "review_reason": self.state.review_reason,
            "cooldown_remaining": self._get_cooldown_remaining(),
        }

    def _get_cooldown_remaining(self) -> int:
        """获取冷却剩余时间"""
        if self.state.cooldown_until and datetime.now() < self.state.cooldown_until:
            return (self.state.cooldown_until - datetime.now()).seconds
        return 0

    def get_status_text(self) -> str:
        """获取风控状态文本"""
        if not self.is_trading_allowed:
            if self.review_required:
                return f" 强制复盘: {self.state.review_reason}"
            return "🚫 交易禁止"

        if self.state.cooldown_until and datetime.now() < self.state.cooldown_until:
            remaining = self._get_cooldown_remaining()
            return f"⏳ 冷却中: {remaining}秒"

        if self.state.consecutive_loss > 0:
            return f"⚠️ 连续亏损: {self.state.consecutive_loss}次"

        return "✅ 正常"
