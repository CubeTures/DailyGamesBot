"""Captured game results: one row per (game, player, puzzle).

The first capture of a puzzle wins; later ones (e.g. the game re-showing its
finished state on reload) are ignored. Each result is filed under its game
day, so a scoreboard day holds the same puzzles for every viewer whatever
their timezone and whenever they played.
"""

import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

from src.store.db import connect


@dataclass(frozen=True)
class NewResult:
    game: str
    discord_id: str
    puzzle_id: str
    game_day: date
    data: dict[str, Any]
    trigger: str
    url: str | None = None


@dataclass(frozen=True)
class StoredResult:
    id: int
    game: str
    discord_id: str
    player_name: str | None
    puzzle_id: str
    data: dict[str, Any]
    captured_at: datetime


def save(result: NewResult) -> bool:
    """Insert a result and mark its player's name for a lookup; return False
    if this puzzle was already recorded."""
    with connect() as conn:
        cursor = conn.execute(
            "INSERT OR IGNORE INTO results"
            " (game, discord_id, puzzle_id, game_day, data, trigger, url,"
            " captured_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                result.game,
                result.discord_id,
                result.puzzle_id,
                result.game_day.isoformat(),
                json.dumps(result.data),
                result.trigger,
                result.url,
                datetime.now(UTC).isoformat(),
            ),
        )
        if cursor.rowcount != 1:
            return False
        conn.execute(
            "INSERT INTO players (discord_id, name_stale) VALUES (?, 1)"
            " ON CONFLICT (discord_id) DO UPDATE SET name_stale = 1",
            (result.discord_id,),
        )
        return True


def on_day(day: date) -> list[StoredResult]:
    """Results for the puzzles of game day `day`."""
    return _select("r.game_day = ?", (day.isoformat(),))


def unannounced() -> list[StoredResult]:
    """Results not yet posted to Discord, oldest first."""
    return _select("r.announced = 0")


def mark_announced(result_id: int) -> None:
    with connect() as conn:
        conn.execute("UPDATE results SET announced = 1 WHERE id = ?", (result_id,))


def _select(where: str, params: Sequence[Any] = ()) -> list[StoredResult]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT r.id, r.game, r.discord_id, p.name, r.puzzle_id, r.data,"
            " r.captured_at FROM results r LEFT JOIN players p USING (discord_id)"
            f" WHERE {where} ORDER BY r.captured_at",
            params,
        ).fetchall()
    return [
        StoredResult(
            id=id_,
            game=game,
            discord_id=discord_id,
            player_name=name,
            puzzle_id=puzzle_id,
            data=json.loads(data),
            captured_at=datetime.fromisoformat(captured_at),
        )
        for id_, game, discord_id, name, puzzle_id, data, captured_at in rows
    ]
