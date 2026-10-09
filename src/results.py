"""SQLite store for captured game results, the players who made them, and
which games' Discord roles each player wants, plus which games admins have
turned off.

One row per (game, discord_id, puzzle_id); the first capture wins and later
ones (e.g. the game re-showing its finished state on reload) are ignored.
Each result is filed under its game day, the day the puzzle belongs to by the
game's [reset], so a scoreboard day holds the same puzzles for every viewer
whatever their timezone and whenever they played.

Results are saved by the proxy, which runs in mitmdump's process and can't
reach the Discord bot. So instead of calling the bot, a save marks the
player's name stale and leaves the result unannounced; the bot polls for both
(see discord_bot/), looks the name up, posts the result and marks it
announced. Likewise the launcher saves role subscriptions unsynced, and the
bot gives or takes the role and marks them synced, and the bot records which
players are admins of its server for the launcher to check.
"""

import json
import re
import sqlite3
from collections.abc import Generator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime
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
    game_day    TEXT NOT NULL,  -- YYYY-MM-DD
    announced   INTEGER NOT NULL DEFAULT 0,
    UNIQUE (game, discord_id, puzzle_id)
);
CREATE TABLE IF NOT EXISTS players (
    discord_id  TEXT PRIMARY KEY,
    name        TEXT,
    name_stale  INTEGER NOT NULL DEFAULT 0,
    is_admin    INTEGER NOT NULL DEFAULT 0  -- may turn games on and off
);
CREATE TABLE IF NOT EXISTS subscriptions (
    discord_id  TEXT NOT NULL,
    game        TEXT NOT NULL,
    subscribed  INTEGER NOT NULL,
    synced      INTEGER NOT NULL DEFAULT 0,  -- the bot has given/taken the role
    PRIMARY KEY (discord_id, game)
);
-- Games an admin has turned off: hidden on the launcher and not proxied.
-- Their results stay.
CREATE TABLE IF NOT EXISTS disabled_games (
    game        TEXT PRIMARY KEY
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


@dataclass(frozen=True)
class Subscription:
    discord_id: str
    game: str
    subscribed: bool


@contextmanager
def _connect() -> Generator[sqlite3.Connection]:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        conn.executescript(_SCHEMA)
        _add_announced_column(conn)
        _add_game_day_column(conn)
        _add_is_admin_column(conn)
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


_DAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _backfilled_game_day(game: str, puzzle_id: str, captured_at: str) -> str:
    """Best guess at an old result's game day: its puzzle_id when that's a
    date (as most are), else the day it was captured in by the game's reset."""
    if _DAY_RE.match(puzzle_id):
        return puzzle_id
    # Imported here: src.games.registry imports this module (via announce).
    from src.games.registry import GAMES_BY_NAME

    captured = datetime.fromisoformat(captured_at)
    config = GAMES_BY_NAME.get(game)
    day = config.reset.day_at(captured) if config else captured.astimezone().date()
    return day.isoformat()


def _add_game_day_column(conn: sqlite3.Connection) -> None:
    """Migrate databases from before results were filed by game day."""
    columns = {row[1] for row in conn.execute("PRAGMA table_info(results)")}
    if "game_day" in columns:
        return
    try:
        conn.execute("ALTER TABLE results ADD COLUMN game_day TEXT NOT NULL DEFAULT ''")
    except sqlite3.OperationalError as e:
        # The bot and the proxy can both get here at once.
        if "duplicate column" not in str(e):
            raise
        return
    rows = conn.execute("SELECT id, game, puzzle_id, captured_at FROM results")
    conn.executemany(
        "UPDATE results SET game_day = ? WHERE id = ?",
        [
            (_backfilled_game_day(game, puzzle_id, captured_at), id_)
            for id_, game, puzzle_id, captured_at in rows.fetchall()
        ],
    )
    conn.commit()


def _add_is_admin_column(conn: sqlite3.Connection) -> None:
    """Migrate databases from before players could be admins."""
    columns = {row[1] for row in conn.execute("PRAGMA table_info(players)")}
    if "is_admin" in columns:
        return
    try:
        conn.execute(
            "ALTER TABLE players ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0"
        )
    except sqlite3.OperationalError as e:
        # The bot and the proxy can both get here at once.
        if "duplicate column" not in str(e):
            raise
        return
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


def on_day(day: date) -> list[StoredResult]:
    """Results for the puzzles of game day `day`."""
    return _query_results("r.game_day = ?", (day.isoformat(),))


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


def player_ids() -> list[str]:
    with _connect() as conn:
        rows = conn.execute("SELECT discord_id FROM players").fetchall()
    return [discord_id for (discord_id,) in rows]


def stale_player_ids() -> list[str]:
    """Players whose name should be looked up again."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT discord_id FROM players WHERE name_stale = 1"
        ).fetchall()
    return [discord_id for (discord_id,) in rows]


def set_player_admin(discord_id: str, is_admin: bool) -> None:
    """Record whether a known player (see add_player) is an admin of the
    bot's server."""
    with _connect() as conn:
        conn.execute(
            "UPDATE players SET is_admin = ? WHERE discord_id = ?",
            (is_admin, discord_id),
        )


def is_admin(discord_id: str) -> bool:
    with _connect() as conn:
        row = conn.execute(
            "SELECT is_admin FROM players WHERE discord_id = ?", (discord_id,)
        ).fetchone()
    return bool(row and row[0])


def set_game_enabled(game: str, enabled: bool) -> None:
    """Turn a game on or off. Its results are kept either way."""
    with _connect() as conn:
        if enabled:
            conn.execute("DELETE FROM disabled_games WHERE game = ?", (game,))
        else:
            conn.execute(
                "INSERT OR IGNORE INTO disabled_games (game) VALUES (?)", (game,)
            )


def disabled_games() -> set[str]:
    with _connect() as conn:
        rows = conn.execute("SELECT game FROM disabled_games").fetchall()
    return {game for (game,) in rows}


def set_subscription(sub: Subscription) -> None:
    """Record whether a player wants a game's role, for the bot to apply."""
    with _connect() as conn:
        conn.execute(
            "INSERT INTO subscriptions (discord_id, game, subscribed)"
            " VALUES (?, ?, ?) ON CONFLICT (discord_id, game)"
            " DO UPDATE SET subscribed = excluded.subscribed, synced = 0",
            (sub.discord_id, sub.game, sub.subscribed),
        )


def subscribed_games(discord_id: str) -> list[str]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT game FROM subscriptions WHERE discord_id = ? AND subscribed = 1",
            (discord_id,),
        ).fetchall()
    return [game for (game,) in rows]


def unsynced_subscriptions() -> list[Subscription]:
    """Subscription changes the bot hasn't applied to Discord yet."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT discord_id, game, subscribed FROM subscriptions WHERE synced = 0"
        ).fetchall()
    return [Subscription(d, g, bool(s)) for d, g, s in rows]


def mark_subscription_synced(sub: Subscription) -> None:
    """Mark `sub` applied, unless the player has changed it again since."""
    with _connect() as conn:
        conn.execute(
            "UPDATE subscriptions SET synced = 1"
            " WHERE discord_id = ? AND game = ? AND subscribed = ?",
            (sub.discord_id, sub.game, sub.subscribed),
        )
