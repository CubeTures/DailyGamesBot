"""Co-op games players have started and who has played in them.

Every player playing a shared game (game, puzzle_id) through the proxy
reports a start, recording the game's own ID for them (`player_id`) so
their squares can be credited to them when anyone reports the solve, even
if they've left by then. The first start of each shared game is also kept
in `starts`, which the bot posts in its starter's servers with a link for
others to join."""

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from src.store.db import connect


@dataclass(frozen=True)
class NewStart:
    game: str
    discord_id: str
    puzzle_id: str
    data: dict[str, Any]
    url: str | None = None


@dataclass(frozen=True)
class StoredStart:
    id: int
    game: str
    discord_id: str
    puzzle_id: str
    data: dict[str, Any]
    url: str | None
    captured_at: datetime


def save(start: NewStart) -> bool:
    """Record a started game; False if someone already started it."""
    with connect() as conn:
        cursor = conn.execute(
            "INSERT OR IGNORE INTO starts"
            " (game, discord_id, puzzle_id, data, url, captured_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (
                start.game,
                start.discord_id,
                start.puzzle_id,
                json.dumps(start.data),
                start.url,
                datetime.now(UTC).isoformat(),
            ),
        )
        return cursor.rowcount == 1


def record_player(game: str, puzzle_id: str, player_id: str, discord_id: str) -> None:
    """Note that `player_id` in the shared game is `discord_id` (the latest
    to report it, should a browser change hands)."""
    with connect() as conn:
        conn.execute(
            "INSERT INTO coop_players (game, puzzle_id, player_id, discord_id)"
            " VALUES (?, ?, ?, ?) ON CONFLICT (game, puzzle_id, player_id)"
            " DO UPDATE SET discord_id = excluded.discord_id",
            (game, puzzle_id, player_id, discord_id),
        )


def players_of(game: str, puzzle_id: str) -> dict[str, str]:
    """The Discord ID of each game player ID known in the shared game."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT player_id, discord_id FROM coop_players"
            " WHERE game = ? AND puzzle_id = ?",
            (game, puzzle_id),
        ).fetchall()
    return dict(rows)


def unannounced() -> list[StoredStart]:
    """Starts not yet posted to Discord, oldest first."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, game, discord_id, puzzle_id, data, url, captured_at"
            " FROM starts WHERE announced = 0 ORDER BY captured_at"
        ).fetchall()
    return [_start(row) for row in rows]


def _start(row: tuple[Any, ...]) -> StoredStart:
    id_, game, discord_id, puzzle_id, data, url, captured_at = row
    return StoredStart(
        id=id_,
        game=game,
        discord_id=discord_id,
        puzzle_id=puzzle_id,
        data=json.loads(data),
        url=url,
        captured_at=datetime.fromisoformat(captured_at),
    )


def mark_announced(start_id: int) -> None:
    with connect() as conn:
        conn.execute("UPDATE starts SET announced = 1 WHERE id = ?", (start_id,))


def announced_in(start_id: int) -> set[str]:
    """The servers the start has been posted in so far."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT guild_id FROM start_announcements WHERE start_id = ?", (start_id,)
        ).fetchall()
    return {guild_id for (guild_id,) in rows}


def mark_announced_in(start_id: int, guild_id: str) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO start_announcements (start_id, guild_id)"
            " VALUES (?, ?)",
            (start_id, guild_id),
        )
