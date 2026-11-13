"""Offline: every game that captures results has a live-test driver."""

from src.games.registry import GAMES_BY_NAME
from tests.e2e.games import DRIVERS


def test_every_captured_game_has_a_driver() -> None:
    captured = {name for name, game in GAMES_BY_NAME.items() if game.triggers}
    missing = sorted(captured - DRIVERS.keys())
    assert not missing, (
        f"no driver in tests/e2e/games/ for {missing}; add one so its capture"
        " is tested (see tests/e2e/games/wordle.py)"
    )


def test_drivers_name_real_games() -> None:
    unknown = sorted(DRIVERS.keys() - GAMES_BY_NAME.keys())
    assert not unknown, f"drivers for games not in games/: {unknown}"
