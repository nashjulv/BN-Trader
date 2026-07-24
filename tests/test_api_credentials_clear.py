import gui.api_settings_dialog as api_settings


def test_clear_persisted_api_settings_removes_all_known_caches(
    tmp_path, monkeypatch
):
    preferences = tmp_path / "preferences"
    preferences.mkdir()
    settings = preferences / "api.json"
    settings_backup = preferences / "api.json.bak"
    legacy = tmp_path / ".bn_trader_api.json"
    legacy_backup = tmp_path / ".bn_trader_api.json.bak"
    env = preferences / ".env"

    for path in (settings, settings_backup, legacy, legacy_backup):
        path.write_text('{"secret_key":"stale"}', encoding="utf-8")
    env.write_text(
        "OTHER_SETTING=keep\n"
        "BINANCE_API_KEY=stale-key\n"
        "BINANCE_SECRET_KEY=stale-secret\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(api_settings, "SETTINGS_FILE", settings)
    monkeypatch.setattr(api_settings, "LEGACY_SETTINGS_FILE", legacy)
    monkeypatch.setattr(
        api_settings.Config, "PREFERENCES_DIR", preferences
    )

    api_settings.clear_persisted_api_settings()

    assert not settings.exists()
    assert not settings_backup.exists()
    assert not legacy.exists()
    assert not legacy_backup.exists()
    assert env.read_text(encoding="utf-8") == "OTHER_SETTING=keep\n"
    assert env.stat().st_mode & 0o777 == 0o600
