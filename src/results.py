"""SQLite store for captured game results.

One row per (game, discord_id, puzzle_id); the first capture wins and later
ones (e.g. the game re-showing its finished state on reload) are ignored.
Players' Discord usernames are kept alongside. The bot looks a name up when a
player first runs /play, and again after each result: save() can run outside
the bot's process (in mitmproxy), so it only marks the name stale and the bot
refreshes stale names (see discord_bot/bot.py). The same goes for
announcing results in Discord: each result starts unannounced and the bot
posts it, then marks it announced.
The database lives at data/results.db unless DGB_DB_PATH is set.
"""

import json
import os
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent

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


@dataclass(frozen=True)
class StoredResult:
    id: int
    game: str
    discord_id: str
    puzzle_id: str
    data: dict[str, Any]
    captured_at: datetime


@dataclass(frozen=True)
class Result:
    game: str
    discord_id: str
    puzzle_id: str
    data: dict[str, Any]
    trigger: str
    url: str | None = None


def db_path() -> Path:
    return Path(os.environ.get("DGB_DB_PATH", REPO_ROOT / "data" / "results.db"))


@contextmanager
def connect() -> Generator[sqlite3.Connection]:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        conn.executescript(_SCHEMA)
        _migrate(conn)
        with conn:
            yield conn
    finally:
        conn.close()


def _migrate(conn: sqlite3.Connection) -> None:
    columns = {row[1] for row in conn.execute("PRAGMA table_info(results)")}
    if "announced" not in columns:
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


def save(result: Result) -> bool:
    """Insert a result; return False if this puzzle was already recorded."""
    with connect() as conn:
        cur = conn.execute(
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
                datetime.now(UTC).isoformat(),
            ),
        )
        saved = cur.rowcount == 1
        if saved:
            conn.execute(
                "INSERT INTO players (discord_id, name_stale) VALUES (?, 1)"
                " ON CONFLICT (discord_id) DO UPDATE SET name_stale = 1",
                (result.discord_id,),
            )
        return saved


def add_player(discord_id: str) -> bool:
    """Register a player; return False if they were already known."""
    with connect() as conn:
        cur = conn.execute(
            "INSERT OR IGNORE INTO players (discord_id) VALUES (?)", (discord_id,)
        )
        return cur.rowcount == 1


def set_player_name(discord_id: str, name: str | None) -> None:
    """Store a looked-up name (None keeps the old one) and clear the stale flag."""
    with connect() as conn:
        conn.execute(
            "UPDATE players SET name = COALESCE(?, name), name_stale = 0"
            " WHERE discord_id = ?",
            (name, discord_id),
        )


def stale_players() -> list[str]:
    """Players whose name should be looked up again."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT discord_id FROM players WHERE name_stale = 1"
        ).fetchall()
    return [discord_id for (discord_id,) in rows]


def results_since(
    since: datetime, until: datetime | None = None
) -> list[dict[str, Any]]:
    """Results captured at or after `since` (and before `until`, if given),
    with each player's name if known."""
    until_iso = until.astimezone(UTC).isoformat() if until else None
    with connect() as conn:
        rows = conn.execute(
            "SELECT r.game, r.discord_id, p.name, r.puzzle_id, r.data, r.captured_at"
            " FROM results r LEFT JOIN players p USING (discord_id)"
            " WHERE r.captured_at >= ? AND (? IS NULL OR r.captured_at < ?)"
            " ORDER BY r.captured_at",
            (since.astimezone(UTC).isoformat(), until_iso, until_iso),
        ).fetchall()
    return [
        {
            "game": game,
            "discord_id": discord_id,
            "name": name,
            "puzzle_id": puzzle_id,
            "data": json.loads(data),
            "captured_at": captured_at,
        }
        for game, discord_id, name, puzzle_id, data, captured_at in rows
    ]


def unannounced() -> list[StoredResult]:
    """Results not yet posted to Discord, oldest first."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, game, discord_id, puzzle_id, data, captured_at"
            " FROM results WHERE announced = 0 ORDER BY captured_at"
        ).fetchall()
    return [
        StoredResult(
            id=id_,
            game=game,
            discord_id=discord_id,
            puzzle_id=puzzle_id,
            data=json.loads(data),
            captured_at=datetime.fromisoformat(captured_at),
        )
        for id_, game, discord_id, puzzle_id, data, captured_at in rows
    ]


def mark_announced(result_id: int) -> None:
    with connect() as conn:
        conn.execute("UPDATE results SET announced = 1 WHERE id = ?", (result_id,))
