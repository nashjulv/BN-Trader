import json

from utils.settings_store import (
    deep_merge_defaults,
    load_json_settings,
    migrate_legacy_file,
    save_json_settings,
)


def test_deep_merge_preserves_customer_values():
    saved = {"strategy": {"period": 8}}
    defaults = {"strategy": {"period": 5, "enabled": True}, "version": 1}
    assert deep_merge_defaults(saved, defaults) == {
        "strategy": {"period": 8, "enabled": True},
        "version": 1,
    }


def test_legacy_settings_are_migrated(tmp_path):
    legacy = tmp_path / "legacy.json"
    target = tmp_path / "settings" / "strategies.json"
    legacy.write_text('{"TRENDING":{"fast_ma":8}}', encoding="utf-8")

    assert migrate_legacy_file(target, [legacy])
    loaded = load_json_settings(
        target,
        {"TRENDING": {"fast_ma": 5, "slow_ma": 20}},
    )
    assert loaded["TRENDING"] == {"fast_ma": 8, "slow_ma": 20}
    assert legacy.exists()


def test_atomic_save_keeps_backup(tmp_path):
    target = tmp_path / "global.json"
    save_json_settings(target, {"risk": {"max_drawdown": 0.2}})
    save_json_settings(target, {"risk": {"max_drawdown": 0.15}})

    current = json.loads(target.read_text(encoding="utf-8"))
    backup = json.loads(
        target.with_suffix(".json.bak").read_text(encoding="utf-8")
    )
    assert current["risk"]["max_drawdown"] == 0.15
    assert backup["risk"]["max_drawdown"] == 0.2
