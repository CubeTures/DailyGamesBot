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


# The `guild_id` of on_day() for every server the viewer is registered with.
# Discord IDs are numeric, so it can't name a real server.
ALL_GUILDS = "all"


def on_day(day: date, viewer_id: str, guild_id: str | None) -> list[StoredResult]:
    """Results for the puzzles of game day `day` that the viewer may see:
    their own, plus, if they're registered with server `guild_id`, those of
    everyone registered with it. `ALL_GUILDS` gives those of everyone who
    shares any server with them."""
    if guild_id == ALL_GUILDS:
        return _select(
            "r.game_day = ? AND (r.discord_id = ? OR r.discord_id IN ("
            " SELECT them.discord_id FROM player_guilds them"
            " JOIN player_guilds me USING (guild_id) WHERE me.discord_id = ?))",
            (day.isoformat(), viewer_id, viewer_id),
        )
    return _select(
        "r.game_day = ? AND (r.discord_id = ? OR (EXISTS ("
        " SELECT 1 FROM player_guilds WHERE discord_id = ? AND guild_id = ?)"
        " AND r.discord_id IN ("
        " SELECT discord_id FROM player_guilds WHERE guild_id = ?)))",
        (day.isoformat(), viewer_id, viewer_id, guild_id, guild_id),
    )


def unannounced() -> list[StoredResult]:
    """Results not yet posted to Discord, oldest first."""
    return _select("r.announced = 0")


def mark_announced(result_id: int) -> None:
    """Mark the result done with: posted in all its player's servers, or
    skipped."""
    with connect() as conn:
        conn.execute("UPDATE results SET announced = 1 WHERE id = ?", (result_id,))


def announced_in(result_id: int) -> set[str]:
    """The servers the result has been posted in so far."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT guild_id FROM announcements WHERE result_id = ?", (result_id,)
        ).fetchall()
    return {guild_id for (guild_id,) in rows}


def mark_announced_in(result_id: int, guild_id: str) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO announcements (result_id, guild_id) VALUES (?, ?)",
            (result_id, guild_id),
        )


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
