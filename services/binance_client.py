"""
币安API客户端

封装币安交易所的REST API和WebSocket接口。
"""

import json
import hmac
import hashlib
import time
import logging
from decimal import Decimal, InvalidOperation, ROUND_DOWN
from typing import Dict, List, Optional, Callable
from urllib.parse import urlencode

import requests
import websocket

from config import Config

logger = logging.getLogger(__name__)


def quantize_to_step(value, step) -> Decimal:
    """按币安步长向下截断，避免浮点精度产生非法参数。"""
    decimal_value = Decimal(str(value))
    decimal_step = Decimal(str(step))
    if decimal_step <= 0:
        return decimal_value
    return (
        (decimal_value / decimal_step).to_integral_value(
            rounding=ROUND_DOWN
        )
        * decimal_step
    )


def decimal_to_api_string(value: Decimal) -> str:
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


class BinanceAPIError(RuntimeError):
    """不泄露签名 URL 的 Binance API 错误。"""

    def __init__(self, status_code: int, code=None, message: str = ""):
        self.status_code = status_code
        self.code = code
        self.api_message = message
        display_message = message
        if code == -2010 and "not whitelisted" in message.lower():
            display_message = f"交易对未加入该 API Key 的白名单（{message}）"
        code_text = f" {code}" if code is not None else ""
        super().__init__(
            f"Binance API{code_text}: "
            f"{display_message or '请求失败'} (HTTP {status_code})"
        )


class BinanceClient:
    """币安API客户端"""

    def __init__(self):
        self.api_key = Config.BINANCE_API_KEY
        self.secret_key = Config.BINANCE_SECRET_KEY
        self.base_url = Config.BINANCE_BASE_URL
        self.ws_url = Config.BINANCE_WS_URL

        self.session = requests.Session()
        self._update_session_headers()
        self._symbol_filters: Dict[str, Dict[str, Dict]] = {}

        self.ws = None
        self.ws_callbacks: Dict[str, Callable] = {}
        self.is_connected = False

    # ------ key 管理 ------

    def _update_session_headers(self):
        self.session.headers.pop("X-MBX-APIKEY", None)
        if self.api_key:
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
        original_params = dict(params or {})

        def prepare_params() -> Dict:
            request_params = dict(original_params)
            if signed:
                request_params["timestamp"] = int(time.time() * 1000)
                query_string = urlencode(request_params)
                request_params["signature"] = self._generate_signature(query_string)
            return request_params

        def send(request_params: Dict):
            if method == "GET":
                return self.session.get(url, params=request_params, timeout=10)
            if method == "POST":
                return self.session.post(url, data=request_params, timeout=10)
            if method == "DELETE":
                return self.session.delete(url, params=request_params, timeout=10)
            raise ValueError(f"不支持的HTTP方法: {method}")

        attempts = 3 if method == "GET" else 1
        for attempt in range(attempts):
            try:
                response = send(prepare_params())

                # 设置页更新过凭据但运行中的客户端尚未刷新时，自动恢复一次。
                if signed and response.status_code == 401:
                    self.reload_keys()
                    response = send(prepare_params())

                if not response.ok:
                    try:
                        payload = response.json()
                    except (ValueError, json.JSONDecodeError):
                        payload = {}
                    raise BinanceAPIError(
                        response.status_code,
                        payload.get("code"),
                        payload.get("msg") or response.reason,
                    )
                return response.json()
            except requests.exceptions.RequestException as error:
                if attempt + 1 >= attempts:
                    logger.error("API请求失败 %s: %s", endpoint, error)
                    raise
                delay = 0.25 * (2 ** attempt)
                logger.warning(
                    "API GET 短暂中断，%.2f 秒后重试 %s（%s/%s）: %s",
                    delay,
                    endpoint,
                    attempt + 2,
                    attempts,
                    error,
                )
                time.sleep(delay)

    # ------ 行情数据 ------

    def get_server_time(self) -> int:
        """获取服务器时间"""
        result = self._request("GET", "/api/v3/time")
        return result["serverTime"]

    def get_exchange_info(self, symbol: str = None) -> Dict:
        """获取交易所信息"""
        params = {"symbol": symbol} if symbol else None
        return self._request("GET", "/api/v3/exchangeInfo", params)

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

    def _get_symbol_filters(self, symbol: str) -> Dict[str, Dict]:
        symbol = symbol.upper()
        if symbol not in self._symbol_filters:
            info = self.get_exchange_info(symbol)
            symbols = info.get("symbols", [])
            if not symbols:
                raise ValueError(f"币安未返回 {symbol} 的交易规则")
            self._symbol_filters[symbol] = {
                item["filterType"]: item
                for item in symbols[0].get("filters", [])
            }
        return self._symbol_filters[symbol]

    def normalize_order_values(
        self,
        symbol: str,
        order_type: str,
        quantity: float = None,
        price: float = None,
    ) -> tuple[Optional[str], Optional[str]]:
        """按指定交易对的实时过滤规则规整数量和价格。"""
        symbol = symbol.upper()
        order_type = order_type.upper()
        filters = self._get_symbol_filters(symbol)
        normalized_quantity = None
        normalized_price = None

        if quantity is not None:
            lot = filters.get(
                "MARKET_LOT_SIZE" if order_type == "MARKET" else "LOT_SIZE",
                {},
            )
            step = Decimal(str(lot.get("stepSize", "0")))
            # 部分交易对禁用 MARKET_LOT_SIZE 步长，此时 LOT_SIZE 仍生效。
            if step <= 0:
                lot = filters.get("LOT_SIZE", lot)
                step = Decimal(str(lot.get("stepSize", "0")))
            if step <= 0:
                raise ValueError(
                    f"{symbol} 未返回有效数量步长，已停止下单"
                )
            try:
                value = quantize_to_step(quantity, step)
            except (InvalidOperation, ValueError) as error:
                raise ValueError(
                    f"{symbol} 数量格式无效: {quantity}"
                ) from error
            minimum = Decimal(str(lot.get("minQty", "0")))
            maximum = Decimal(str(lot.get("maxQty", "0")))
            if value <= 0 or (minimum > 0 and value < minimum):
                raise ValueError(
                    f"{symbol} 数量 {quantity} 按步长 {step} 截断后"
                    f"低于最小数量 {minimum}"
                )
            if maximum > 0 and value > maximum:
                raise ValueError(
                    f"{symbol} 数量超过最大值 {maximum}"
                )
            normalized_quantity = decimal_to_api_string(value)

        if price is not None:
            normalized_price = self.normalize_price(symbol, price, filters)

        return normalized_quantity, normalized_price

    def normalize_price(
        self,
        symbol: str,
        price: float,
        filters: Dict[str, Dict] = None,
    ) -> str:
        """按 PRICE_FILTER 规整任意订单价格或触发价。"""
        symbol = symbol.upper()
        filters = filters or self._get_symbol_filters(symbol)
        price_filter = filters.get("PRICE_FILTER", {})
        tick = Decimal(str(price_filter.get("tickSize", "0")))
        if tick <= 0:
            raise ValueError(
                f"{symbol} 未返回有效价格步长，已停止下单"
            )
        try:
            value = quantize_to_step(price, tick)
        except (InvalidOperation, ValueError) as error:
            raise ValueError(
                f"{symbol} 价格格式无效: {price}"
            ) from error
        minimum = Decimal(str(price_filter.get("minPrice", "0")))
        maximum = Decimal(str(price_filter.get("maxPrice", "0")))
        if minimum > 0 and value < minimum:
            raise ValueError(f"{symbol} 价格低于最小值 {minimum}")
        if maximum > 0 and value > maximum:
            raise ValueError(f"{symbol} 价格超过最大值 {maximum}")
        return decimal_to_api_string(value)

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
        symbol = symbol.upper()
        side = side.upper()
        order_type = order_type.upper()
        normalized_quantity, normalized_price = self.normalize_order_values(
            symbol, order_type, quantity, price
        )
        normalized_stop_price = (
            self.normalize_price(symbol, stop_price)
            if stop_price is not None else None
        )
        if (
            normalized_quantity is not None
            and Decimal(normalized_quantity) != Decimal(str(quantity))
        ):
            logger.info(
                "订单数量按 %s 交易步长调整: %s -> %s",
                symbol,
                quantity,
                normalized_quantity,
            )
        if (
            normalized_price is not None
            and Decimal(normalized_price) != Decimal(str(price))
        ):
            logger.info(
                "订单价格按 %s 最小变动单位调整: %s -> %s",
                symbol,
                price,
                normalized_price,
            )
        params = {
            "symbol": symbol,
            "side": side,
            "type": order_type,
        }

        if normalized_quantity is not None:
            params["quantity"] = normalized_quantity
        if normalized_price is not None:
            params["price"] = normalized_price
        if normalized_stop_price is not None:
            params["stopPrice"] = normalized_stop_price
        if order_type in {
            "LIMIT",
            "STOP_LOSS_LIMIT",
            "TAKE_PROFIT_LIMIT",
        }:
            params["timeInForce"] = time_in_force

        return self._request("POST", "/api/v3/order", params, signed=True)

    def test_order(self, symbol: str, quote_order_qty: float = 10) -> Dict:
        """验证当前 Key 的现货下单权限，不会创建真实订单。"""
        return self._request(
            "POST",
            "/api/v3/order/test",
            {
                "symbol": symbol,
                "side": "BUY",
                "type": "MARKET",
                "quoteOrderQty": quote_order_qty,
            },
            signed=True,
        )

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
