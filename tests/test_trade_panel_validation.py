from gui.trade_panel import validate_available_balance, validate_exit_prices


def test_buy_exit_prices_use_absolute_prices():
    valid, message = validate_exit_prices(
        "BUY", 100.0, stop_loss=99.3, take_profit=102.0,
        max_loss_ratio=0.02,
    )
    assert valid
    assert message == ""


def test_percentage_typed_as_stop_price_gets_actionable_message():
    valid, message = validate_exit_prices(
        "BUY", 100.0, stop_loss=0.7, max_loss_ratio=0.02,
    )
    assert not valid
    assert "99.30%" in message
    assert "绝对价格" in message
    assert "99.3" in message


def test_sell_exit_price_direction_is_checked():
    valid, message = validate_exit_prices(
        "SELL", 100.0, stop_loss=99.0, max_loss_ratio=0.02,
    )
    assert not valid
    assert "高于入场价" in message


def test_buy_is_checked_against_real_quote_balance():
    valid, message = validate_available_balance(
        "BUY",
        quantity=0.02,
        price=65_000,
        quote_available=935.25,
        base_available=0.000999,
    )

    assert not valid
    assert "1,300.0000 USDT" in message
    assert "935.2500 USDT" in message


def test_sell_is_checked_against_real_base_balance():
    valid, message = validate_available_balance(
        "SELL",
        quantity=0.001,
        price=65_000,
        quote_available=935.25,
        base_available=0.000999,
    )

    assert not valid
    assert "BTC 余额不足" in message
    assert "0.000999 BTC" in message


def test_order_within_real_balance_is_allowed():
    valid, message = validate_available_balance(
        "BUY",
        quantity=0.001,
        price=65_000,
        quote_available=935.25,
        base_available=0.000999,
    )

    assert valid
    assert message == ""
