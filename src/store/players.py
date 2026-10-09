"""Players: their Discord usernames for the scoreboard, and whether they're
admins of the bot's server (who may turn games on and off)."""

from src.store.db import connect


def add(discord_id: str) -> bool:
    """Register a player; return False if they were already known."""
    with connect() as conn:
        cursor = conn.execute(
            "INSERT OR IGNORE INTO players (discord_id) VALUES (?)", (discord_id,)
        )
        return cursor.rowcount == 1


def all_ids() -> list[str]:
    with connect() as conn:
        rows = conn.execute("SELECT discord_id FROM players").fetchall()
    return [discord_id for (discord_id,) in rows]


def stale_name_ids() -> list[str]:
    """Players whose name should be looked up again."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT discord_id FROM players WHERE name_stale = 1"
        ).fetchall()
    return [discord_id for (discord_id,) in rows]


def set_name(discord_id: str, name: str | None) -> None:
    """Store a looked-up name (None keeps the old one) and clear the stale flag."""
    with connect() as conn:
        conn.execute(
            "UPDATE players SET name = COALESCE(?, name), name_stale = 0"
            " WHERE discord_id = ?",
            (name, discord_id),
        )


def set_admin(discord_id: str, is_admin: bool) -> None:
    """Record whether a known player (see `add`) is an admin."""
    with connect() as conn:
        conn.execute(
            "UPDATE players SET is_admin = ? WHERE discord_id = ?",
            (is_admin, discord_id),
        )


def is_admin(discord_id: str) -> bool:
    with connect() as conn:
        row = conn.execute(
            "SELECT is_admin FROM players WHERE discord_id = ?", (discord_id,)
        ).fetchone()
    return bool(row and row[0])
