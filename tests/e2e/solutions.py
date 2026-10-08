"""Each game's solution, learned once per game day and cached on disk.

Puzzles change daily, so drivers learn the day's answers (from the game's own
API, or by revealing everything in a throwaway play) and the other scenarios
replay them. The cache is keyed on the game day, so it goes stale by itself.
Delete tests/e2e/.solutions/ to force a re-learn.
"""

import json
from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path

from src.games.models import Game
from tests.e2e.harness import Solution

SOLUTIONS_DIR = Path(__file__).with_name(".solutions")


def game_day(game: Game) -> date:
    """Today's game day by the game's [reset]; the test machine's own
    timezone for "local" games, as the browser's."""
    return game.reset.day_at(datetime.now(UTC))


def path_for(game: str, day: date) -> Path:
    return SOLUTIONS_DIR / game / f"{day.isoformat()}.json"


def cached(game: str, day: date, learn: Callable[[], Solution]) -> Solution:
    path = path_for(game, day)
    if path.exists():
        return json.loads(path.read_text())
    solution = learn()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(solution, indent=2, ensure_ascii=False) + "\n")
    return solution
