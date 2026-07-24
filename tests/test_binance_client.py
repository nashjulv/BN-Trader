from decimal import Decimal

from services.binance_client import (
    BinanceAPIError,
    BinanceClient,
    quantize_to_step,
)
from config import Config


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload
        self.ok = 200 <= status_code < 400
        self.reason = "Unauthorized" if status_code == 401 else "Bad Request"

    def json(self):
        return self._payload


def cache_btc_filters(client):
    client._symbol_filters["BTCUSDT"] = {
        "LOT_SIZE": {
            "minQty": "0.00001",
            "maxQty": "9000",
            "stepSize": "0.00001",
        },
        "MARKET_LOT_SIZE": {
            "minQty": "0",
            "maxQty": "9000",
            "stepSize": "0",
        },
        "PRICE_FILTER": {
            "minPrice": "0.01",
            "maxPrice": "1000000",
            "tickSize": "0.01",
        },
    }


def cache_sol_filters(client):
    client._symbol_filters["SOLUSDT"] = {
        "LOT_SIZE": {
            "minQty": "0.001",
            "maxQty": "9000",
            "stepSize": "0.001",
        },
        "MARKET_LOT_SIZE": {
            "minQty": "0",
            "maxQty": "9000",
            "stepSize": "0",
        },
        "PRICE_FILTER": {
            "minPrice": "0.01",
            "maxPrice": "1000000",
            "tickSize": "0.01",
        },
    }


def test_signed_request_reloads_credentials_and_retries_once(monkeypatch):
    client = BinanceClient()
    responses = [
        FakeResponse(401, {"code": -2015, "msg": "Invalid API-key"}),
        FakeResponse(200, {"balances": []}),
    ]
    calls = []
    reloads = []

    def fake_get(url, params, timeout):
        calls.append((url, params.copy()))
        return responses.pop(0)

    def fake_reload():
        reloads.append(True)
        client.secret_key = "refreshed-secret"

    monkeypatch.setattr(client.session, "get", fake_get)
    monkeypatch.setattr(client, "reload_keys", fake_reload)

    assert client.get_account() == {"balances": []}
    assert len(calls) == 2
    assert len(reloads) == 1
    assert calls[0][1]["signature"] != calls[1][1]["signature"]


def test_api_error_preserves_binance_code_without_signed_url(monkeypatch):
    client = BinanceClient()
    cache_btc_filters(client)
    response = FakeResponse(
        400, {"code": -1013, "msg": "Filter failure: LOT_SIZE"}
    )
    monkeypatch.setattr(
        client.session, "post",
        lambda url, data, timeout: response,
    )

    try:
        client.create_order("BTCUSDT", "BUY", "MARKET", quantity=0.00001)
    except BinanceAPIError as exc:
        message = str(exc)
    else:
        raise AssertionError("expected BinanceAPIError")

    assert "-1013" in message
    assert "LOT_SIZE" in message
    assert "signature=" not in message


def test_symbol_whitelist_error_has_chinese_guidance(monkeypatch):
    client = BinanceClient()
    cache_btc_filters(client)
    response = FakeResponse(
        400, {"code": -2010, "msg": "Symbol not whitelisted for API key."}
    )
    monkeypatch.setattr(
        client.session, "post",
        lambda url, data, timeout: response,
    )

    try:
        client.create_order("BTCUSDT", "BUY", "MARKET", quantity=0.001)
    except BinanceAPIError as exc:
        message = str(exc)
    else:
        raise AssertionError("expected BinanceAPIError")

    assert "交易对未加入" in message
    assert "-2010" in message


def test_reload_removes_api_header_when_credentials_are_cleared(monkeypatch):
    client = BinanceClient()
    client.session.headers["X-MBX-APIKEY"] = "stale-key"

    def clear_config():
        Config.BINANCE_API_KEY = ""
        Config.BINANCE_SECRET_KEY = ""

    monkeypatch.setattr(Config, "reload_api_keys", clear_config)
    client.reload_keys()

    assert client.api_key == ""
    assert client.secret_key == ""
    assert "X-MBX-APIKEY" not in client.session.headers


def test_order_uses_non_trading_test_endpoint(monkeypatch):
    client = BinanceClient()
    captured = {}

    def fake_post(url, data, timeout):
        captured["url"] = url
        captured["data"] = dict(data)
        return FakeResponse(200, {})

    monkeypatch.setattr(client.session, "post", fake_post)

    assert client.test_order("BTCUSDT", quote_order_qty=10) == {}
    assert captured["url"].endswith("/api/v3/order/test")
    assert captured["data"]["quoteOrderQty"] == 10
    assert captured["data"]["type"] == "MARKET"


def test_quantity_is_floored_to_exchange_step():
    assert quantize_to_step("0.265217", "0.001") == Decimal("0.265")
    assert quantize_to_step("0.265041", "0.001") == Decimal("0.265")


def test_sol_market_order_uses_lot_size_when_market_step_is_disabled(
    monkeypatch,
):
    client = BinanceClient()
    cache_sol_filters(client)
    captured = {}

    def fake_post(url, data, timeout):
        captured["data"] = dict(data)
        return FakeResponse(200, {"orderId": 1, "origQty": data["quantity"]})

    monkeypatch.setattr(client.session, "post", fake_post)

    result = client.create_order(
        "SOLUSDT", "BUY", "MARKET", quantity=0.265217
    )

    assert captured["data"]["quantity"] == "0.265"
    assert result["origQty"] == "0.265"


def test_sol_limit_order_normalizes_quantity_and_price(monkeypatch):
    client = BinanceClient()
    cache_sol_filters(client)
    captured = {}

    def fake_post(url, data, timeout):
        captured["data"] = dict(data)
        return FakeResponse(200, {"orderId": 1})

    monkeypatch.setattr(client.session, "post", fake_post)

    client.create_order(
        "SOLUSDT",
        "BUY",
        "LIMIT",
        quantity=0.265217,
        price=123.456,
    )

    assert captured["data"]["quantity"] == "0.265"
    assert captured["data"]["price"] == "123.45"


def test_all_supported_symbols_use_their_own_quantity_step(monkeypatch):
    cases = {
        "BTCUSDT": ("0.00001000", 0.000764378, "0.00076"),
        "ETHUSDT": ("0.00010000", 0.01234567, "0.0123"),
        "BNBUSDT": ("0.00100000", 0.123456, "0.123"),
        "SOLUSDT": ("0.00100000", 0.265217, "0.265"),
        "XRPUSDT": ("0.10000000", 12.3456, "12.3"),
        "USDCUSDT": ("0.10000000", 12.3456, "12.3"),
    }

    for symbol, (step, quantity, expected) in cases.items():
        client = BinanceClient()
        client._symbol_filters[symbol] = {
            "LOT_SIZE": {
                "minQty": step,
                "maxQty": "90000000",
                "stepSize": step,
            },
            "MARKET_LOT_SIZE": {
                "minQty": "0",
                "maxQty": "90000000",
                "stepSize": "0",
            },
            "PRICE_FILTER": {
                "minPrice": "0.00000001",
                "maxPrice": "1000000",
                "tickSize": "0.00000001",
            },
        }
        captured = {}

        def fake_post(url, data, timeout):
            captured["quantity"] = data["quantity"]
            return FakeResponse(200, {"orderId": 1})

        monkeypatch.setattr(client.session, "post", fake_post)
        client.create_order(
            symbol, "SELL", "MARKET", quantity=quantity
        )
        assert captured["quantity"] == expected


def test_stop_price_is_normalized_for_conditional_orders(monkeypatch):
    client = BinanceClient()
    cache_sol_filters(client)
    captured = {}

    def fake_post(url, data, timeout):
        captured["data"] = dict(data)
        return FakeResponse(200, {"orderId": 1})

    monkeypatch.setattr(client.session, "post", fake_post)
    client.create_order(
        "solusdt",
        "sell",
        "stop_loss_limit",
        quantity=0.265217,
        price=123.456,
        stop_price=122.987,
    )

    assert captured["data"]["symbol"] == "SOLUSDT"
    assert captured["data"]["side"] == "SELL"
    assert captured["data"]["type"] == "STOP_LOSS_LIMIT"
    assert captured["data"]["quantity"] == "0.265"
    assert captured["data"]["price"] == "123.45"
    assert captured["data"]["stopPrice"] == "122.98"
    assert captured["data"]["timeInForce"] == "GTC"
