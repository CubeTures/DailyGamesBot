import pytest

from src import settings


def test_game_origin_defaults_to_subdomain() -> None:
    assert settings.game_origin("wordle") == "http://wordle.localhost:8080"


def test_game_origin_uses_game_host(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "GAME_HOST", "{game}-daily.example.com")
    assert settings.game_origin("wordle") == "http://wordle-daily.example.com"


def test_results_channel_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DISCORD_RESULTS_CHANNEL_IDS", raising=False)
    monkeypatch.delenv("DISCORD_RESULTS_CHANNEL_ID", raising=False)
    assert settings.results_channel_ids() == []
    # The old single-channel setting still works.
    monkeypatch.setenv("DISCORD_RESULTS_CHANNEL_ID", "5")
    assert settings.results_channel_ids() == [5]
    monkeypatch.setenv("DISCORD_RESULTS_CHANNEL_IDS", " 1, 2 3,,1 ")
    assert settings.results_channel_ids() == [1, 2, 3]
    monkeypatch.setenv("DISCORD_RESULTS_CHANNEL_IDS", "1,general")
    with pytest.raises(SystemExit):
        settings.results_channel_ids()


def test_admin_channel_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DISCORD_ADMIN_CHANNEL_ID", " ")
    assert settings.admin_channel_id() is None
    monkeypatch.setenv("DISCORD_ADMIN_CHANNEL_ID", " 42 ")
    assert settings.admin_channel_id() == 42
    monkeypatch.setenv("DISCORD_ADMIN_CHANNEL_ID", "admin")
    with pytest.raises(SystemExit):
        settings.admin_channel_id()
