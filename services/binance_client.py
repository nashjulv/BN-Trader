"""
币安API客户端

封装币安交易所的REST API和WebSocket接口。
"""

import json
import hmac
import hashlib
import time
import logging
from typing import Dict, List, Optional, Callable
from urllib.parse import urlencode

import requests
import websocket

from config import Config

logger = logging.getLogger(__name__)


class BinanceClient:
    """币安API客户端"""

    def __init__(self):
        self.api_key = Config.BINANCE_API_KEY
        self.secret_key = Config.BINANCE_SECRET_KEY
        self.base_url = Config.BINANCE_BASE_URL
        self.ws_url = Config.BINANCE_WS_URL

        self.session = requests.Session()
        self._update_session_headers()

        self.ws = None
        self.ws_callbacks: Dict[str, Callable] = {}
        self.is_connected = False

    # ------ key 管理 ------

    def _update_session_headers(self):
        self.session.headers.update({"X-MBX-APIKEY": self.api_key})

    def reload_keys(self):
        """重新从 Config 加载 API Key（用户在运行时保存后调用）"""
        Config.reload_api_keys()
        self.api_key = Config.BINANCE_API_KEY
        self.secret_key = Config.BINANCE_SECRET_KEY
        self._update_session_headers()
        logger.info("API Key 已重新加载")

    def has_keys(self) -> bool:
        return bool(self.api_key and self.secret_key)

    # ------ 账户 & 资产 ------

    def _generate_signature(self, query_string: str) -> str:
        """生成API签名"""
        return hmac.new(
            self.secret_key.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

    def _request(self, method: str, endpoint: str, params: Dict = None,
                 signed: bool = False) -> Dict:
        """发送HTTP请求"""
        url = f"{self.base_url}{endpoint}"

        if params is None:
            params = {}

        if signed:
            params["timestamp"] = int(time.time() * 1000)
            query_string = urlencode(params)
            params["signature"] = self._generate_signature(query_string)

        try:
            if method == "GET":
                response = self.session.get(url, params=params, timeout=10)
            elif method == "POST":
                response = self.session.post(url, data=params, timeout=10)
            elif method == "DELETE":
                response = self.session.delete(url, params=params, timeout=10)
            else:
                raise ValueError(f"不支持的HTTP方法: {method}")

            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            logger.error(f"API请求失败: {e}")
            raise

    # ------ 行情数据 ------

    def get_server_time(self) -> int:
        """获取服务器时间"""
        result = self._request("GET", "/api/v3/time")
        return result["serverTime"]

    def get_exchange_info(self) -> Dict:
        """获取交易所信息"""
        return self._request("GET", "/api/v3/exchangeInfo")

    def get_ticker_24h(self, symbol: str = None) -> Dict:
        """获取24小时价格变动统计"""
        params = {}
        if symbol:
            params["symbol"] = symbol
        return self._request("GET", "/api/v3/ticker/24hr", params)

    def get_klines(self, symbol: str, interval: str,
                   limit: int = 500, start_time: int = None,
                   end_time: int = None) -> List[List]:
        """
        获取K线数据

        Args:
            symbol: 交易对，如 "BTCUSDT"
            interval: K线周期，如 "1m", "5m", "15m", "1h", "4h", "1d"
            limit: 返回条数，最大1000
            start_time: 开始时间戳(ms)
            end_time: 结束时间戳(ms)

        Returns:
            K线数据列表 [[open_time, open, high, low, close, volume, ...], ...]
        """
        params = {
            "symbol": symbol,
            "interval": interval,
            "limit": limit
        }
        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time

        return self._request("GET", "/api/v3/klines", params)

    def get_order_book(self, symbol: str, limit: int = 100) -> Dict:
        """获取订单簿深度"""
        params = {
            "symbol": symbol,
            "limit": limit
        }
        return self._request("GET", "/api/v3/depth", params)

    def get_recent_trades(self, symbol: str, limit: int = 500) -> List[Dict]:
        """获取最近成交"""
        params = {
            "symbol": symbol,
            "limit": limit
        }
        return self._request("GET", "/api/v3/trades", params)

    # ------ 账户相关 ------

    def get_account(self) -> Dict:
        """获取账户信息"""
        return self._request("GET", "/api/v3/account", signed=True)

    def get_balance(self, asset: str = None) -> List[Dict]:
        """获取账户余额"""
        account = self.get_account()
        balances = account.get("balances", [])

        if asset:
            return [b for b in balances if b["asset"] == asset]
        return balances

    def get_nonzero_balances(self) -> List[Dict]:
        """获取非零余额"""
        account = self.get_account()
        return [
            {"asset": b["asset"], "free": float(b["free"]), "locked": float(b["locked"])}
            for b in account.get("balances", [])
            if float(b["free"]) > 0 or float(b["locked"]) > 0
        ]

    def get_asset_value_usdt(self, balances: List[Dict]) -> float:
        """估算资产总价值(USDT)"""
        total = 0.0
        for b in balances:
            asset, free, locked = b["asset"], b["free"], b["locked"]
            qty = free + locked
            if qty <= 0:
                continue
            if asset == "USDT":
                total += qty
                continue
            # 尝试用对应的 USDT 交易对查价
            try:
                price = self.get_symbol_price(f"{asset}USDT")
                total += qty * price
            except Exception:
                pass
        return total

    def get_symbol_price(self, symbol: str) -> float:
        """获取单个交易对当前价格"""
        params = {"symbol": symbol}
        result = self._request("GET", "/api/v3/ticker/price", params)
        return float(result["price"])

    # ------ 订单相关 ------

    def create_order(self, symbol: str, side: str, order_type: str,
                     quantity: float = None, price: float = None,
                     stop_price: float = None,
                     time_in_force: str = "GTC") -> Dict:
        """
        创建订单

        Args:
            symbol: 交易对
            side: BUY 或 SELL
            order_type: MARKET, LIMIT, STOP_LOSS, etc.
            quantity: 数量
            price: 价格（限价单需要）
            stop_price: 触发价格（止损单需要）
            time_in_force: 有效时间 GTC/IOC/FOK
        """
        params = {
            "symbol": symbol,
            "side": side,
            "type": order_type,
        }

        if quantity:
            params["quantity"] = quantity
        if price:
            params["price"] = price
        if stop_price:
            params["stopPrice"] = stop_price
        if order_type == "LIMIT":
            params["timeInForce"] = time_in_force

        return self._request("POST", "/api/v3/order", params, signed=True)

    def cancel_order(self, symbol: str, order_id: str) -> Dict:
        """取消订单"""
        params = {
            "symbol": symbol,
            "orderId": order_id
        }
        return self._request("DELETE", "/api/v3/order", params, signed=True)

    def get_order(self, symbol: str, order_id: str) -> Dict:
        """查询订单"""
        params = {
            "symbol": symbol,
            "orderId": order_id
        }
        return self._request("GET", "/api/v3/order", params, signed=True)

    def get_open_orders(self, symbol: str = None) -> List[Dict]:
        """获取当前挂单"""
        params = {}
        if symbol:
            params["symbol"] = symbol
        return self._request("GET", "/api/v3/openOrders", params, signed=True)

    def get_all_orders(self, symbol: str, limit: int = 500) -> List[Dict]:
        """获取所有订单"""
        params = {
            "symbol": symbol,
            "limit": limit
        }
        return self._request("GET", "/api/v3/allOrders", params, signed=True)

    # ==================== WebSocket 方法 ====================

    def start_websocket(self, streams: List[str],
                        on_message: Callable = None,
                        on_error: Callable = None,
                        on_close: Callable = None):
        """
        启动WebSocket连接

        Args:
            streams: 数据流列表，如 ["btcusdt@kline_1m", "btcusdt@depth"]
            on_message: 消息回调函数
            on_error: 错误回调函数
            on_close: 关闭回调函数
        """
        stream_path = "/".join(streams)
        ws_url = f"{self.ws_url}/{stream_path}"

        def default_on_message(ws, message):
            data = json.loads(message)
            logger.debug(f"WebSocket收到消息: {data}")
            if on_message:
                on_message(data)

        def default_on_error(ws, error):
            logger.error(f"WebSocket错误: {error}")
            if on_error:
                on_error(error)

        def default_on_close(ws, close_status_code, close_msg):
            logger.info("WebSocket连接关闭")
            self.is_connected = False
            if on_close:
                on_close(close_status_code, close_msg)

        def on_open(ws):
            logger.info("WebSocket连接已建立")
            self.is_connected = True

        self.ws = websocket.WebSocketApp(
            ws_url,
            on_open=on_open,
            on_message=default_on_message,
            on_error=default_on_error,
            on_close=default_on_close
        )

        # 在后台线程运行WebSocket
        import threading
        self.ws_thread = threading.Thread(target=self.ws.run_forever)
        self.ws_thread.daemon = True
        self.ws_thread.start()

    def stop_websocket(self):
        """停止WebSocket连接"""
        if self.ws:
            self.ws.close()
            self.is_connected = False
            logger.info("WebSocket连接已停止")

    def subscribe_stream(self, stream: str, callback: Callable):
        """订阅数据流"""
        self.ws_callbacks[stream] = callback

    # ==================== 工具方法 ====================

    @staticmethod
    def klines_to_dataframe(klines: List[List]) -> "pandas.DataFrame":
        """将K线数据转换为DataFrame"""
        import pandas as pd

        columns = [
            "open_time", "open", "high", "low", "close", "volume",
            "close_time", "quote_volume", "trades", "taker_buy_volume",
            "taker_buy_quote_volume", "ignore"
        ]

        df = pd.DataFrame(klines, columns=columns)
        df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
        df["close_time"] = pd.to_datetime(df["close_time"], unit="ms")

        numeric_columns = ["open", "high", "low", "close", "volume",
                          "quote_volume", "taker_buy_volume", "taker_buy_quote_volume"]
        for col in numeric_columns:
            df[col] = pd.to_numeric(df[col])

        return df

    def test_connection(self) -> bool:
        """测试API连接"""
        try:
            self.get_server_time()
            logger.info("币安API连接测试成功")
            return True
        except Exception as e:
            logger.error(f"币安API连接测试失败: {e}")
            return False
