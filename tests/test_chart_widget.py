from gui.chart_widget import format_price, price_precision


def test_price_format_keeps_stablecoin_movement_visible():
    assert price_precision(1.0002) == 4
    assert format_price(1.0002) == "1.0002"


def test_price_format_keeps_high_value_symbol_readable():
    assert price_precision(68420.125) == 2
    assert format_price(68420.125) == "68,420.12"


def test_price_format_supports_low_value_symbols():
    assert price_precision(0.123456) == 6
    assert format_price(0.123456) == "0.123456"
