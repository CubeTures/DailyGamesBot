import pytest

from src import settings


def test_game_origin_defaults_to_subdomain() -> None:
    assert settings.game_origin("wordle") == "http://wordle.localhost:8080"


def test_game_origin_uses_game_host(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "GAME_HOST", "{game}-daily.example.com")
    assert settings.game_origin("wordle") == "http://wordle-daily.example.com"
