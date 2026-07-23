from services.binance_client import BinanceAPIError, BinanceClient


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload
        self.ok = 200 <= status_code < 400
        self.reason = "Unauthorized" if status_code == 401 else "Bad Request"

    def json(self):
        return self._payload


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
