"""SQLite store for captured game results and the players who made them.

One row per (game, discord_id, puzzle_id); the first capture wins and later
ones (e.g. the game re-showing its finished state on reload) are ignored.

Results are saved by the proxy, which runs in mitmdump's process and can't
reach the Discord bot. So instead of calling the bot, a save marks the
player's name stale and leaves the result unannounced; the bot polls for both
(see discord_bot/), looks the name up, posts the result and marks it
announced.
"""

import json
import sqlite3
from collections.abc import Generator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from src.settings import db_path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS results (
    id          INTEGER PRIMARY KEY,
    game        TEXT NOT NULL,
    discord_id  TEXT NOT NULL,
    puzzle_id   TEXT NOT NULL,
    data        TEXT NOT NULL,  -- JSON object of the trigger's fields
    trigger     TEXT NOT NULL,
    url         TEXT,
    captured_at TEXT NOT NULL,
    announced   INTEGER NOT NULL DEFAULT 0,
    UNIQUE (game, discord_id, puzzle_id)
);
CREATE TABLE IF NOT EXISTS players (
    discord_id  TEXT PRIMARY KEY,
    name        TEXT,
    name_stale  INTEGER NOT NULL DEFAULT 0
);
"""

_SELECT_RESULTS = """
SELECT r.id, r.game, r.discord_id, p.name, r.puzzle_id, r.data, r.captured_at
FROM results r LEFT JOIN players p USING (discord_id)
"""


@dataclass(frozen=True)
class NewResult:
    game: str
    discord_id: str
    puzzle_id: str
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


@contextmanager
def _connect() -> Generator[sqlite3.Connection]:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        conn.executescript(_SCHEMA)
        _add_announced_column(conn)
        with conn:
            yield conn
    finally:
        conn.close()


def _add_announced_column(conn: sqlite3.Connection) -> None:
    """Migrate databases from before results were announced."""
    columns = {row[1] for row in conn.execute("PRAGMA table_info(results)")}
    if "announced" in columns:
        return
    try:
        conn.execute(
            "ALTER TABLE results ADD COLUMN announced INTEGER NOT NULL DEFAULT 0"
        )
    except sqlite3.OperationalError as e:
        # The bot and the proxy can both get here at once.
        if "duplicate column" not in str(e):
            raise
        return
    # Results from before announcements existed are old news.
    conn.execute("UPDATE results SET announced = 1")
    conn.commit()


def _utc_iso(time: datetime) -> str:
    return time.astimezone(UTC).isoformat()


def _query_results(where: str, params: Sequence[Any] = ()) -> list[StoredResult]:
    with _connect() as conn:
        rows = conn.execute(
            f"{_SELECT_RESULTS} WHERE {where} ORDER BY r.captured_at", params
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


def save(result: NewResult) -> bool:
    """Insert a result; return False if this puzzle was already recorded."""
    with _connect() as conn:
        cursor = conn.execute(
            "INSERT OR IGNORE INTO results"
            " (game, discord_id, puzzle_id, data, trigger, url, captured_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                result.game,
                result.discord_id,
                result.puzzle_id,
                json.dumps(result.data),
                result.trigger,
                result.url,
                _utc_iso(datetime.now(UTC)),
            ),
        )
        saved = cursor.rowcount == 1
        if saved:
            conn.execute(
                "INSERT INTO players (discord_id, name_stale) VALUES (?, 1)"
                " ON CONFLICT (discord_id) DO UPDATE SET name_stale = 1",
                (result.discord_id,),
            )
        return saved


def captured_between(
    since: datetime, until: datetime | None = None
) -> list[StoredResult]:
    """Results captured at or after `since` and before `until`, if given."""
    until_iso = _utc_iso(until) if until else None
    return _query_results(
        "r.captured_at >= ? AND (? IS NULL OR r.captured_at < ?)",
        (_utc_iso(since), until_iso, until_iso),
    )


def unannounced() -> list[StoredResult]:
    """Results not yet posted to Discord, oldest first."""
    return _query_results("r.announced = 0")


def mark_announced(result_id: int) -> None:
    with _connect() as conn:
        conn.execute("UPDATE results SET announced = 1 WHERE id = ?", (result_id,))


def add_player(discord_id: str) -> bool:
    """Register a player; return False if they were already known."""
    with _connect() as conn:
        cursor = conn.execute(
            "INSERT OR IGNORE INTO players (discord_id) VALUES (?)", (discord_id,)
        )
        return cursor.rowcount == 1


def set_player_name(discord_id: str, name: str | None) -> None:
    """Store a looked-up name (None keeps the old one) and clear the stale flag."""
    with _connect() as conn:
        conn.execute(
            "UPDATE players SET name = COALESCE(?, name), name_stale = 0"
            " WHERE discord_id = ?",
            (name, discord_id),
        )


def stale_player_ids() -> list[str]:
    """Players whose name should be looked up again."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT discord_id FROM players WHERE name_stale = 1"
        ).fetchall()
    return [discord_id for (discord_id,) in rows]
