"""
应用核心模块

提供应用主控类和系统协调功能。
"""

import logging
from typing import Dict, Optional, List

from services.binance_client import BinanceClient
from services.scene_detector import SceneDetector, Scene
from services.capital_pool import CapitalPool, TradeResult
from services.risk_manager import RiskManager, RiskCheck
from services.strategy_engine import StrategyEngine, Signal

logger = logging.getLogger(__name__)


class App:
    """应用主控类"""

    def __init__(self):
        """初始化应用"""
        self.client = BinanceClient()
        self.scene_detector = SceneDetector()
        self.capital_pool = CapitalPool()
        self.risk_manager = RiskManager()
        self.strategy_engine = StrategyEngine()

        self.is_running = False
        self.is_auto_trading = False

        self.positions: List[Dict] = []
        self.trade_history: List[Dict] = []

        logger.info("应用核心初始化完成")

    def start(self):
        """启动应用"""
        self.is_running = True

        # 测试API连接
        connected = self.client.test_connection()
        if not connected:
            logger.warning("币安API连接失败，将在离线模式运行")

        logger.info("应用已启动")

    def stop(self):
        """停止应用"""
        self.is_running = False
        self.is_auto_trading = False

        # 关闭WebSocket连接
        self.client.stop_websocket()

        logger.info("应用已停止")

    def analyze_market(self, symbol: str, timeframe: str = "15m") -> Optional[Scene]:
        """
        分析市场行情

        Args:
            symbol: 交易对
            timeframe: K线周期

        Returns:
            Scene or None
        """
        try:
            # 获取K线数据
            klines = self.client.get_klines(symbol, timeframe, limit=100)
            if not klines:
                logger.warning(f"无法获取{symbol}的K线数据")
                return None

            # 转换数据
            df = BinanceClient.klines_to_dataframe(klines)
            df["symbol"] = symbol

            # 计算技术指标
            from indicators.technical import calculate_all_indicators
            df = calculate_all_indicators(df)

            # 识别场景
            scene = self.scene_detector.detect(df)
            return scene

        except Exception as e:
            logger.error(f"行情分析失败: {e}")
            return None

    def execute_trade(self, symbol: str, side: str, quantity: float,
                     price: float, stop_loss: float = None,
                     take_profit: float = None) -> Optional[Dict]:
        """
        执行交易

        Args:
            symbol: 交易对
            side: BUY/SELL
            quantity: 数量
            price: 价格
            stop_loss: 止损价格
            take_profit: 止盈价格

        Returns:
            交易记录字典，失败返回None
        """
        # 风控检查
        capital_used = quantity * price
        check = self.risk_manager.check_trade_permission(
            self.capital_pool.total, capital_used, price, stop_loss
        )

        if not check.allowed:
            logger.warning(f"风控拦截: {check.message}")
            return None

        # 资金检查
        can_trade, reason = self.capital_pool.can_trade()
        if not can_trade:
            logger.warning(f"交易禁止: {reason}")
            return None

        try:
            # 锁定资金
            self.capital_pool.lock_capital(capital_used)

            # 创建订单（模拟模式下）
            trade = {
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "entry_price": price,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "capital_used": capital_used,
                "scene": self.scene_detector.last_scene.type if self.scene_detector.last_scene else "UNKNOWN",
                "status": "OPEN",
            }

            self.positions.append(trade)
            self.capital_pool.add_margin(capital_used)

            logger.info(f"交易已执行: {side} {symbol} {quantity}@{price}")

            return trade

        except Exception as e:
            logger.error(f"交易执行失败: {e}")
            self.capital_pool.unlock_capital(capital_used)
            return None

    def close_trade(self, trade_index: int, exit_price: float) -> Optional[TradeResult]:
        """
        平仓

        Args:
            trade_index: 持仓索引
            exit_price: 平仓价格

        Returns:
            TradeResult or None
        """
        if trade_index < 0 or trade_index >= len(self.positions):
            return None

        trade = self.positions.pop(trade_index)

        entry_price = trade["entry_price"]
        quantity = trade["quantity"]
        capital_used = trade["capital_used"]
        side = trade["side"]

        # 计算盈亏
        if side == "BUY":
            profit = (exit_price - entry_price) * quantity
        else:
            profit = (entry_price - exit_price) * quantity

        profit_ratio = profit / capital_used if capital_used > 0 else 0

        result = TradeResult(
            profit=profit,
            profit_ratio=profit_ratio,
            capital_used=capital_used,
            is_win=profit > 0
        )

        # 释放保证金
        self.capital_pool.release_margin(capital_used)

        # 更新资金池
        self.capital_pool.update_after_trade(result)

        # 更新风控
        self.risk_manager.update_after_trade(profit, profit_ratio)

        # 更新交易记录
        trade["exit_price"] = exit_price
        trade["pnl"] = profit
        trade["pnl_ratio"] = profit_ratio
        trade["status"] = "CLOSED"
        self.trade_history.append(trade)

        # 检查是否需要强制复盘
        if self.risk_manager.review_required:
            logger.critical("触发强制复盘机制")

        logger.info(
            f"交易已平仓: {side} {trade['symbol']} 盈亏={profit:+.2f} ({profit_ratio:+.2%})"
        )

        return result

    def get_system_status(self) -> Dict:
        """获取系统状态"""
        capital_status = self.capital_pool.get_status()
        risk_summary = self.risk_manager.get_risk_summary()

        return {
            "is_running": self.is_running,
            "is_auto_trading": self.is_auto_trading,
            "capital": capital_status,
            "risk": risk_summary,
            "positions_count": len(self.positions),
            "trades_count": len(self.trade_history),
        }
