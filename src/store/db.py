"""Opening the database, creating its tables and migrating old ones."""

import re
import sqlite3
from collections.abc import Callable, Generator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

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
    game_day    TEXT NOT NULL,  -- YYYY-MM-DD, by the game's [reset]
    announced   INTEGER NOT NULL DEFAULT 0,
    UNIQUE (game, discord_id, puzzle_id)
);
CREATE TABLE IF NOT EXISTS players (
    discord_id  TEXT PRIMARY KEY,
    name        TEXT,
    name_stale  INTEGER NOT NULL DEFAULT 0,
    token       TEXT,  -- in their /play link; see players.token_for
    primary_guild TEXT  -- the server their scoreboard opens on
);
CREATE TABLE IF NOT EXISTS guilds (
    guild_id    TEXT PRIMARY KEY,
    name        TEXT  -- for the launcher's server picker; kept by the bot
);
CREATE TABLE IF NOT EXISTS player_guilds (
    discord_id    TEXT NOT NULL,
    guild_id      TEXT NOT NULL,
    registered_at TEXT NOT NULL,
    PRIMARY KEY (discord_id, guild_id)
);
CREATE TABLE IF NOT EXISTS announcements (
    result_id   INTEGER NOT NULL,  -- results.id
    guild_id    TEXT NOT NULL,     -- the server it was posted in
    PRIMARY KEY (result_id, guild_id)
);
-- Co-op games started (see starts.py): one row per shared game, from
-- whoever reported it first.
CREATE TABLE IF NOT EXISTS starts (
    id          INTEGER PRIMARY KEY,
    game        TEXT NOT NULL,
    discord_id  TEXT NOT NULL,
    puzzle_id   TEXT NOT NULL,
    data        TEXT NOT NULL,  -- JSON object of the trigger's fields
    url         TEXT,           -- the page it was started on
    captured_at TEXT NOT NULL,
    announced   INTEGER NOT NULL DEFAULT 0,
    UNIQUE (game, puzzle_id)
);
-- Who's who in each co-op shared game: the game's own ID for a player
-- (e.g. Cross with Friends' dfac-id), recorded when they play in it through
-- the proxy, so whoever reports the solve can credit everyone.
CREATE TABLE IF NOT EXISTS coop_players (
    game        TEXT NOT NULL,
    puzzle_id   TEXT NOT NULL,
    player_id   TEXT NOT NULL,
    discord_id  TEXT NOT NULL,
    PRIMARY KEY (game, puzzle_id, player_id)
);
CREATE TABLE IF NOT EXISTS start_announcements (
    start_id    INTEGER NOT NULL,  -- starts.id
    guild_id    TEXT NOT NULL,     -- the server it was posted in
    PRIMARY KEY (start_id, guild_id)
);
-- The servers a player invites others from when they start each co-op
-- game (see invites.py).
CREATE TABLE IF NOT EXISTS coop_invites (
    discord_id  TEXT NOT NULL,
    game        TEXT NOT NULL,
    guilds      TEXT NOT NULL,  -- JSON array of guild IDs
    PRIMARY KEY (discord_id, game)
);
CREATE TABLE IF NOT EXISTS subscriptions (
    discord_id  TEXT NOT NULL,
    game        TEXT NOT NULL,
    subscribed  INTEGER NOT NULL,
    synced      INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (discord_id, game)
);
CREATE TABLE IF NOT EXISTS hidden_games (
    discord_id  TEXT NOT NULL,
    game        TEXT NOT NULL,
    level       TEXT NOT NULL,  -- "card", or "all" to hide its scoreboard too
    PRIMARY KEY (discord_id, game)
);
-- Left over from when admins turned games off for everyone.
DROP TABLE IF EXISTS disabled_games;
"""

_DAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_prepared: set[Path] = set()


@contextmanager
def connect() -> Generator[sqlite3.Connection]:
    """A connection that commits on success and is closed afterwards."""
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        if path not in _prepared:
            _prepare(conn)
            _prepared.add(path)
        with conn:
            yield conn
    finally:
        conn.close()


def _prepare(conn: sqlite3.Connection) -> None:
    conn.executescript(_SCHEMA)
    _add_column(
        conn,
        "results",
        "announced INTEGER NOT NULL DEFAULT 0",
        # Results from before announcements existed are old news.
        backfill=lambda: conn.execute("UPDATE results SET announced = 1"),
    )
    _add_column(
        conn,
        "results",
        "game_day TEXT NOT NULL DEFAULT ''",
        backfill=lambda: _backfill_game_days(conn),
    )
    _add_column(conn, "players", "token TEXT")
    _add_column(conn, "players", "primary_guild TEXT")
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS players_token ON players (token)")


def _add_column(
    conn: sqlite3.Connection,
    table: str,
    definition: str,
    backfill: Callable[[], object] | None = None,
) -> None:
    """Add a column that databases from before it existed lack."""
    column = definition.split()[0]
    if column in {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}:
        return
    try:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {definition}")
    except sqlite3.OperationalError as e:
        # The bot and the proxy can both get here at once.
        if "duplicate column" not in str(e):
            raise
        return
    if backfill is not None:
        backfill()
    conn.commit()


def _backfill_game_days(conn: sqlite3.Connection) -> None:
    rows = conn.execute("SELECT id, game, puzzle_id, captured_at FROM results")
    conn.executemany(
        "UPDATE results SET game_day = ? WHERE id = ?",
        [
            (_guess_game_day(game, puzzle_id, captured_at), id_)
            for id_, game, puzzle_id, captured_at in rows.fetchall()
        ],
    )


def _guess_game_day(game: str, puzzle_id: str, captured_at: str) -> str:
    """An old result's game day: its puzzle_id when that's a date (as most
    are), else the day it was captured in by the game's reset."""
    if _DAY_RE.match(puzzle_id):
        return puzzle_id
    # Imported here: the registry imports this package (via announce).
    from src.games.registry import GAMES_BY_NAME

    captured = datetime.fromisoformat(captured_at)
    config = GAMES_BY_NAME.get(game)
    day = config.reset.day_at(captured) if config else captured.astimezone().date()
    return day.isoformat()
