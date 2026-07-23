import json

import pytest

from gui import global_settings_dialog, strategy_settings_dialog
from services.risk_manager import RiskManager
from services.strategy_engine import StrategyEngine
from utils.parameter_units import (
    CURRENT_PARAMETER_SCHEMA,
    GLOBAL_PERCENT_FIELDS,
    STRATEGY_PERCENT_FIELDS,
    migrate_global_settings,
    migrate_strategy_settings,
    percent_to_ratio,
    ratio_to_percent,
    strategy_runtime_params,
)


@pytest.mark.parametrize(
    ("percent", "ratio"),
    [
        (0.1, 0.001),
        (0.7, 0.007),
        (0.8, 0.008),
        (1.0, 0.01),
        (1.5, 0.015),
        (2.0, 0.02),
        (20.0, 0.20),
        (100.0, 1.0),
    ],
)
def test_percent_ratio_round_trip(percent, ratio):
    assert percent_to_ratio(percent) == pytest.approx(ratio)
    assert ratio_to_percent(ratio) == pytest.approx(percent)


@pytest.mark.parametrize("value", [-0.1, 100.1, float("inf"), float("nan")])
def test_invalid_percentages_are_rejected(value):
    with pytest.raises(ValueError):
        percent_to_ratio(value)


@pytest.mark.parametrize("value", [-0.001, 1.001, float("inf"), float("nan")])
def test_invalid_internal_ratios_are_rejected(value):
    with pytest.raises(ValueError):
        ratio_to_percent(value)


def test_strategy_v1_migration_converts_every_declared_percent_field_once():
    old = {
        "RANGING": {
            "stop_loss_pct": 0.7,
            "take_profit_pct": 0.7,
            "rsi_oversold": 30,
        },
        "BREAKOUT": {"breakout_pct": 0.8, "stop_loss_pct": 1.5},
        "TRENDING": {"trailing_stop": 1.5},
        "_schema_version": 1,
    }

    migrated, changed = migrate_strategy_settings(old)
    assert changed
    assert migrated["_schema_version"] == CURRENT_PARAMETER_SCHEMA
    assert migrated["RANGING"]["stop_loss_pct"] == pytest.approx(0.007)
    assert migrated["RANGING"]["take_profit_pct"] == pytest.approx(0.007)
    assert migrated["BREAKOUT"]["breakout_pct"] == pytest.approx(0.008)
    assert migrated["BREAKOUT"]["stop_loss_pct"] == pytest.approx(0.015)
    assert migrated["TRENDING"]["trailing_stop"] == pytest.approx(0.015)
    assert migrated["RANGING"]["rsi_oversold"] == 30

    unchanged, changed_again = migrate_strategy_settings(migrated)
    assert not changed_again
    assert unchanged == migrated


def test_global_v1_migration_preserves_existing_ratios_and_fixes_mixed_fields():
    old = {
        "capital": {
            "reserve_ratio": 0.20,
            "daily_loss_limit": 0.025,
        },
        "position": {
            "initial_position_ratio": 0.15,
            "trailing_stop_pct": 1.5,
            "take_profit_trigger": 4.0,
            "breakeven_stop": 0.4,
        },
        "_schema_version": 1,
    }

    migrated, changed = migrate_global_settings(old)
    assert changed
    assert migrated["capital"]["reserve_ratio"] == pytest.approx(0.20)
    assert migrated["capital"]["daily_loss_limit"] == pytest.approx(0.025)
    assert migrated["position"]["initial_position_ratio"] == pytest.approx(0.15)
    assert migrated["position"]["trailing_stop_pct"] == pytest.approx(0.015)
    assert migrated["position"]["take_profit_trigger"] == pytest.approx(0.04)
    assert migrated["position"]["breakeven_stop"] == pytest.approx(0.004)


def test_global_v2_repairs_missed_percentage_point_values():
    old = {
        "risk": {
            "max_loss_per_trade": 2.0,
            "max_profit_per_trade": 3.5,
            "max_drawdown": 0.1,
        },
        "_schema_version": 2,
    }

    migrated, changed = migrate_global_settings(old)

    assert changed
    assert migrated["risk"]["max_loss_per_trade"] == pytest.approx(0.02)
    assert migrated["risk"]["max_profit_per_trade"] == pytest.approx(0.035)
    assert migrated["risk"]["max_drawdown"] == pytest.approx(0.1)

    unchanged, changed_again = migrate_global_settings(migrated)
    assert not changed_again
    assert unchanged == migrated


def test_runtime_params_never_guess_or_double_convert_percentages():
    params = strategy_runtime_params({
        "enabled": True,
        "stop_loss_pct": 0.007,
        "breakout_pct": 0.008,
        "rsi_oversold": 30,
    })
    assert params == {
        "stop_loss_pct": 0.007,
        "breakout_pct": 0.008,
        "rsi_oversold": 30,
    }


def test_strategy_form_defaults_match_strategy_engine_internal_units():
    engine = StrategyEngine()
    for scene, form_defaults in strategy_settings_dialog.DEFAULT_PARAMS.items():
        runtime_defaults = engine.strategies[scene].params
        for key in STRATEGY_PERCENT_FIELDS:
            if key in form_defaults and key in runtime_defaults:
                assert form_defaults[key] == pytest.approx(runtime_defaults[key])


def test_every_percentage_form_field_has_an_explicit_unit_definition():
    strategy_keys = {
        key
        for values in strategy_settings_dialog.DEFAULT_PARAMS.values()
        for key in values
        if key.endswith("_pct") or key == "trailing_stop"
    }
    assert strategy_keys == STRATEGY_PERCENT_FIELDS

    global_keys = {
        key
        for values in global_settings_dialog.DEFAULTS.values()
        for key in values
        if key.endswith("_pct") or key.endswith("_ratio")
        or key in {
            "daily_loss_limit",
            "max_loss_per_trade",
            "max_profit_per_trade",
            "max_drawdown",
            "take_profit_trigger",
            "breakeven_stop",
        }
    }
    assert global_keys == GLOBAL_PERCENT_FIELDS


def test_point_seven_percent_produces_point_seven_percent_risk():
    entry_price = 100.0
    stop_loss = entry_price * (1 - percent_to_ratio(0.7))
    risk_ratio = abs(entry_price - stop_loss) / entry_price
    assert risk_ratio == pytest.approx(0.007)

    manager = RiskManager()
    manager.state.reserve_ratio = 0.20
    result = manager.check_trade_permission(
        capital=10_000,
        position_size=1_000,
        entry_price=entry_price,
        stop_loss=stop_loss,
    )
    assert result.allowed


def test_strategy_file_is_migrated_atomically_and_not_converted_twice(
    tmp_path, monkeypatch
):
    path = tmp_path / "strategies.json"
    path.write_text(json.dumps({
        "RANGING": {
            "enabled": True,
            "stop_loss_pct": 0.7,
            "take_profit_pct": 0.7,
        },
        "_schema_version": 1,
    }))
    monkeypatch.setattr(strategy_settings_dialog, "SETTINGS_PATH", path)
    monkeypatch.setattr(
        strategy_settings_dialog, "LEGACY_SETTINGS_PATH", tmp_path / "legacy.json"
    )

    first = strategy_settings_dialog.load_strategy_settings()
    second = strategy_settings_dialog.load_strategy_settings()

    assert first["RANGING"]["stop_loss_pct"] == pytest.approx(0.007)
    assert second["RANGING"]["stop_loss_pct"] == pytest.approx(0.007)
    assert json.loads(path.read_text())["_schema_version"] == 2
    assert path.with_suffix(".json.bak").exists()


def test_global_file_migration_preserves_ratio_fields(tmp_path, monkeypatch):
    path = tmp_path / "global.json"
    path.write_text(json.dumps({
        "capital": {
            "reserve_ratio": 0.20,
            "daily_loss_limit": 0.025,
        },
        "position": {
            "trailing_stop_pct": 1.5,
            "breakeven_stop": 0.4,
        },
        "_schema_version": 1,
    }))
    monkeypatch.setattr(global_settings_dialog, "SETTINGS_PATH", path)
    monkeypatch.setattr(
        global_settings_dialog, "LEGACY_SETTINGS_PATH", tmp_path / "legacy.json"
    )

    loaded = global_settings_dialog.load_global_settings()

    assert loaded["capital"]["reserve_ratio"] == pytest.approx(0.20)
    assert loaded["capital"]["daily_loss_limit"] == pytest.approx(0.025)
    assert loaded["position"]["trailing_stop_pct"] == pytest.approx(0.015)
    assert loaded["position"]["breakeven_stop"] == pytest.approx(0.004)
    assert json.loads(path.read_text())["_schema_version"] == 2
