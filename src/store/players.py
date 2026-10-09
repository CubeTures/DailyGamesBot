"""Players: their Discord usernames for the scoreboard, and the tokens that
stand in for their Discord IDs in /play links."""

import uuid

from src.store.db import connect


def add(discord_id: str) -> bool:
    """Register a player; return False if they were already known."""
    with connect() as conn:
        cursor = conn.execute(
            "INSERT OR IGNORE INTO players (discord_id) VALUES (?)", (discord_id,)
        )
        return cursor.rowcount == 1


def token_for(discord_id: str) -> str:
    """The token for the player's /play link, made on their first /play and
    kept until an admin resets it."""
    with connect() as conn:
        conn.execute(
            "INSERT INTO players (discord_id, token) VALUES (?, ?)"
            " ON CONFLICT (discord_id) DO UPDATE"
            " SET token = COALESCE(players.token, excluded.token)",
            (discord_id, str(uuid.uuid4())),
        )
        (token,) = conn.execute(
            "SELECT token FROM players WHERE discord_id = ?", (discord_id,)
        ).fetchone()
    return token


def reset_token(discord_id: str) -> bool:
    """Make the player's link stop working, for when it has leaked; their
    next /play gets a new one. Returns False if they had no token."""
    with connect() as conn:
        cursor = conn.execute(
            "UPDATE players SET token = NULL"
            " WHERE discord_id = ? AND token IS NOT NULL",
            (discord_id,),
        )
        return cursor.rowcount == 1


def discord_id_for(token: str) -> str | None:
    """Whose token this is, or None if it's unknown or was reset."""
    if not token:
        return None
    with connect() as conn:
        row = conn.execute(
            "SELECT discord_id FROM players WHERE token = ?", (token,)
        ).fetchone()
    return row[0] if row else None


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
