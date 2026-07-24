"""
账户资产同步服务

从币安拉取真实余额，同步到本地 CapitalPool。
"""

import logging
import time
from typing import Dict, List, Optional

from PyQt6.QtCore import QObject, pyqtSignal

from services.binance_client import BinanceClient

logger = logging.getLogger(__name__)


def fetch_account_snapshot(client: BinanceClient) -> Dict:
    """读取账户并统一换算为 USDT，供所有资金栏位共享同一快照。"""
    balances = client.get_nonzero_balances()
    valued_balances = []
    unpriced_assets = []

    for balance in balances:
        asset = str(balance.get("asset", "")).upper()
        free = float(balance.get("free", 0) or 0)
        locked = float(balance.get("locked", 0) or 0)
        try:
            price = (
                1.0 if asset == "USDT"
                else client.get_symbol_price(f"{asset}USDT")
            )
        except Exception:
            price = 0.0
            unpriced_assets.append(asset)
        valued_balances.append({
            "asset": asset,
            "free": free,
            "locked": locked,
            "price_usdt": price,
            "free_value_usdt": free * price,
            "locked_value_usdt": locked * price,
            "total_value_usdt": (free + locked) * price,
        })

    total_value = sum(
        balance["total_value_usdt"] for balance in valued_balances
    )
    free_value = sum(
        balance["free_value_usdt"] for balance in valued_balances
    )
    locked_value = sum(
        balance["locked_value_usdt"] for balance in valued_balances
    )
    usdt = next(
        (
            balance for balance in valued_balances
            if balance["asset"] == "USDT"
        ),
        {},
    )
    non_usdt_value = sum(
        balance["total_value_usdt"]
        for balance in valued_balances
        if balance["asset"] != "USDT"
    )
    return {
        "balances": balances,
        "valued_balances": valued_balances,
        "total_value_usdt": total_value,
        "free_value_usdt": free_value,
        "locked_value_usdt": locked_value,
        "available_usdt": float(usdt.get("free", 0) or 0),
        "non_usdt_value_usdt": non_usdt_value,
        "unpriced_assets": unpriced_assets,
        "updated_at": time.time(),
    }


class AccountSyncService(QObject):
    """将币安真实账户数据同步到本地"""

    balances_updated = pyqtSignal(list)   # [{"asset":"BTC","free":0.1,"locked":0.0}, ...]
    total_value_updated = pyqtSignal(float)  # USDT 总估值
    snapshot_updated = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)

    def __init__(self, client: BinanceClient):
        super().__init__()
        self.client = client
        self.balances: List[Dict] = []
        self.total_value_usdt: float = 0.0
        self.last_snapshot: Dict = {}

    def fetch_snapshot(self) -> Dict:
        if not self.client.has_keys():
            raise RuntimeError("未配置 API Key")
        return fetch_account_snapshot(self.client)

    def apply_snapshot(self, snapshot: Dict):
        """在主线程应用完整快照，避免各栏位读取到不同步的中间值。"""
        self.last_snapshot = dict(snapshot)
        self.balances = list(snapshot.get("balances", []))
        self.total_value_usdt = float(
            snapshot.get("total_value_usdt", 0) or 0
        )
        self.balances_updated.emit(self.balances)
        self.total_value_updated.emit(self.total_value_usdt)
        self.snapshot_updated.emit(self.last_snapshot)

    def sync(self):
        """从币安拉取账户余额"""
        if not self.client.has_keys():
            self.error_occurred.emit("未配置 API Key")
            return

        try:
            snapshot = self.fetch_snapshot()
            self.apply_snapshot(snapshot)
            if self.balances:
                missing = snapshot.get("unpriced_assets", [])
                suffix = (
                    f"，未计价: {', '.join(missing)}"
                    if missing else ""
                )
                logger.info(
                    "账户同步完成: %s 项资产, 估值 $%.2f%s",
                    len(self.balances),
                    self.total_value_usdt,
                    suffix,
                )
            else:
                logger.info("账户余额为空")

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

        submitted_quantity = quantity
        submitted_price = price
        try:
            normalized_quantity, normalized_price = (
                self.client.normalize_order_values(
                    symbol,
                    order_type,
                    quantity,
                    price if order_type != "MARKET" else None,
                )
            )
            submitted_quantity = float(normalized_quantity)
            if normalized_price is not None:
                submitted_price = float(normalized_price)
            if order_type == "MARKET":
                result = self.client.create_order(
                    symbol, side, "MARKET", quantity=submitted_quantity)
            else:
                result = self.client.create_order(
                    symbol, side, "LIMIT",
                    quantity=submitted_quantity,
                    price=submitted_price)

            logger.info(
                "真实订单: %s %s x%s @ %s → %s",
                side,
                symbol,
                submitted_quantity,
                submitted_price,
                result.get("status"),
            )
            actual_quantity = float(
                result.get("origQty")
                or result.get("executedQty")
                or quantity
            )
            actual_price = float(result.get("price") or price or 0)
            if actual_price <= 0 and float(
                result.get("executedQty", 0) or 0
            ) > 0:
                actual_price = (
                    float(result.get("cummulativeQuoteQty", 0) or 0)
                    / float(result["executedQty"])
                )
            return {
                "symbol": symbol,
                "side": side,
                "quantity": actual_quantity,
                "price": actual_price,
                "status": result.get("status", "UNKNOWN"),
                "order_id": result.get("orderId", ""),
            }

        except Exception as e:
            quantity_detail = f"{quantity:g}"
            if submitted_quantity != quantity:
                quantity_detail += f" → 已规整 {submitted_quantity:g}"
            msg = (
                f"下单失败 {side} {symbol} 数量 {quantity_detail}: {e}"
            )
            logger.error(msg)
            self.error_occurred.emit(msg)
            return None
