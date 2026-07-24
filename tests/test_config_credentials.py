import config


def test_reload_uses_only_highest_priority_credentials(tmp_path, monkeypatch):
    preferred = tmp_path / "preferred.env"
    legacy = tmp_path / "legacy.env"
    preferred.write_text(
        "BINANCE_API_KEY=current-key\n"
        "BINANCE_SECRET_KEY=current-secret\n",
        encoding="utf-8",
    )
    legacy.write_text(
        "BINANCE_API_KEY=stale-key\n"
        "BINANCE_SECRET_KEY=stale-secret\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(config, "_env_paths", [preferred, legacy])

    config.Config.reload_api_keys()

    assert config.Config.BINANCE_API_KEY == "current-key"
    assert config.Config.BINANCE_SECRET_KEY == "current-secret"


def test_reload_clears_runtime_keys_when_active_file_has_no_keys(
    tmp_path, monkeypatch
):
    empty = tmp_path / "empty.env"
    empty.write_text("# credentials removed\n", encoding="utf-8")
    monkeypatch.setattr(config, "_env_paths", [empty])
    monkeypatch.setenv("BINANCE_API_KEY", "stale-key")
    monkeypatch.setenv("BINANCE_SECRET_KEY", "stale-secret")

    config.Config.reload_api_keys()

    assert config.Config.BINANCE_API_KEY == ""
    assert config.Config.BINANCE_SECRET_KEY == ""
