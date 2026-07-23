"""
账户资产同步服务

从币安拉取真实余额，同步到本地 CapitalPool。
"""

import logging
from typing import Dict, List, Optional

from PyQt6.QtCore import QObject, pyqtSignal

from services.binance_client import BinanceClient

logger = logging.getLogger(__name__)


class AccountSyncService(QObject):
    """将币安真实账户数据同步到本地"""

    balances_updated = pyqtSignal(list)   # [{"asset":"BTC","free":0.1,"locked":0.0}, ...]
    total_value_updated = pyqtSignal(float)  # USDT 总估值
    error_occurred = pyqtSignal(str)

    def __init__(self, client: BinanceClient):
        super().__init__()
        self.client = client
        self.balances: List[Dict] = []
        self.total_value_usdt: float = 0.0

    def sync(self):
        """从币安拉取账户余额"""
        if not self.client.has_keys():
            self.error_occurred.emit("未配置 API Key")
            return

        try:
            balances = self.client.get_nonzero_balances()
            self.balances = balances
            self.balances_updated.emit(balances)

            if balances:
                total = self.client.get_asset_value_usdt(balances)
                self.total_value_usdt = total
                self.total_value_updated.emit(total)
                logger.info(f"账户同步完成: {len(balances)} 项资产, 估值 ${total:.2f}")
            else:
                logger.info("账户余额为空")
                self.total_value_updated.emit(0)

        except Exception as e:
            msg = f"账户同步失败: {e}"
            logger.error(msg)
            self.error_occurred.emit(msg)

    def execute_real_order(self, symbol: str, side: str, quantity: float,
                          price: float = 0, order_type: str = "MARKET") -> Optional[Dict]:
        """
        执行真实订单

        Returns:
            dict with keys: symbol, side, quantity, price, status, orderId
        """
        if not self.client.has_keys():
            self.error_occurred.emit("未配置 API Key，无法下单")
            return None

        try:
            if order_type == "MARKET":
                result = self.client.create_order(
                    symbol, side, "MARKET", quantity=quantity)
            else:
                result = self.client.create_order(
                    symbol, side, "LIMIT", quantity=quantity, price=price)

            logger.info(f"真实订单: {side} {symbol} x{quantity} @ {price} → {result.get('status')}")
            return {
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "price": price,
                "status": result.get("status", "UNKNOWN"),
                "order_id": result.get("orderId", ""),
            }

        except Exception as e:
            msg = f"下单失败: {e}"
            logger.error(msg)
            self.error_occurred.emit(msg)
            return None
