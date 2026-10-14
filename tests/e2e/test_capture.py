"""Plays every game on its real site, through the proxy, once per outcome
(win / lose / mixed, where the game has them), and checks the result the
capture script saved.

    uv run pytest -m live                       # everything
    uv run pytest -m live -k wordle --headed    # one game, watching
    uv run pytest -m live -k "chess and lose"

A failure prints the fields that didn't match and saves a trace, screenshot
and __dgb.status() under tests/e2e/.artifacts/ (see conftest.py).
"""

import json
import urllib.request
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from src.games.models import Game
from src.games.registry import GAMES_BY_NAME
from src.settings import LAUNCHER_URL
from tests.e2e import expect, solutions
from tests.e2e.conftest import PlayerFactory
from tests.e2e.games import DRIVERS
from tests.e2e.harness import Driver, Player, Row

CASES = [
    pytest.param(name, scenario, id=f"{name}-{scenario}")
    for name, driver in sorted(DRIVERS.items())
    for scenario in driver.scenarios
]


def _skip_near_reset(game: Game) -> None:
    """The puzzle would change mid-test."""
    if game.reset.day_at(
        datetime.now(UTC) + timedelta(minutes=10)
    ) != solutions.game_day(game):
        pytest.skip(f"{game.name} resets within 10 minutes")


def _solution(driver: Driver, game: Game, players: PlayerFactory) -> dict[str, Any]:
    learn = driver.learn
    if learn is None:
        return {}

    def run() -> dict[str, Any]:
        player = players(driver.name, "learn")
        return learn(player)

    return solutions.cached(driver.name, solutions.game_day(game), run)


def _launcher_results(day: str, token: str) -> list[dict[str, Any]]:
    url = f"{LAUNCHER_URL}/api/results?day={day}&token={token}"
    with urllib.request.urlopen(url) as r:
        return json.load(r)


def _check_row(player: Player, row: Row, expected: dict[str, Any]) -> None:
    game = player.game
    problems = expect.mismatches(expected, row.data)
    if row.puzzle_id != str(row.data.get("puzzle_id")):
        problems.append(f"  row puzzle_id {row.puzzle_id!r} != fields' puzzle_id")
    if row.game_day != solutions.game_day(game).isoformat():
        problems.append(
            f"  game_day: expected {solutions.game_day(game)}, got {row.game_day}"
            " (the launcher would file it under the wrong day)"
        )
    secs = row.data.get("time_secs")
    if not isinstance(secs, int | float) or secs <= 0:
        problems.append(f"  time_secs: expected a number > 0, got {secs!r}")
    if len(player.rows()) != 1:
        problems.append(f"  {len(player.rows())} rows saved, expected 1")

    # The launcher serves the same announcement the bot posts. Every game's
    # template opens with :bee:; the generic fallback (used when the template
    # throws) doesn't.
    shown = [
        r
        for r in _launcher_results(row.game_day, player.token)
        if r["discord_id"] == player.discord_id and r["game"] == game.name
    ]
    announcement = shown[0]["announcement"] if shown else None
    if not shown:
        problems.append("  not in the launcher's /api/results for its game day")
    elif not announcement or not announcement.startswith(":bee:"):
        problems.append(
            f"  announcement fell back to the generic one (template error?):\n"
            f"    {announcement!r}"
        )
    elif "None" in announcement or "{{" in announcement:
        problems.append(f"  announcement has None or raw Jinja:\n{announcement}")

    assert not problems, (
        f"{game.name} result for {player.discord_id} doesn't match:\n"
        + "\n".join(problems)
        + "\nsaved fields:\n"
        + json.dumps(row.data, indent=2, ensure_ascii=False)
        + (f"\nannouncement:\n{announcement}" if announcement else "")
    )


@pytest.mark.live
@pytest.mark.parametrize(("name", "scenario"), CASES)
def test_capture(
    name: str, scenario: str, players: PlayerFactory, request: pytest.FixtureRequest
) -> None:
    driver = DRIVERS[name]
    game = GAMES_BY_NAME[name]
    if reason := driver.known_failures.get(scenario):
        request.applymarker(pytest.mark.xfail(reason=reason, strict=True))
    _skip_near_reset(game)
    solution = _solution(driver, game, players)

    player = players(name, scenario)
    player.open()
    expected = driver.scenarios[scenario](player, solution)
    row = player.wait_for_result()
    _check_row(player, row, expected)
