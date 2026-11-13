"""The servers each player invites others from when they start a co-op game,
picked per game in the launcher's prompt before they play.

A player who has never picked for a game invites from every server they're
registered with; an empty pick invites from none."""

import json
from typing import Any, cast

from src.store.db import connect


def save(discord_id: str, game: str, guild_ids: list[str]) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO coop_invites (discord_id, game, guilds) VALUES (?, ?, ?)"
            " ON CONFLICT (discord_id, game) DO UPDATE SET guilds = excluded.guilds",
            (discord_id, game, json.dumps(guild_ids)),
        )


def picks(discord_id: str) -> dict[str, list[str]]:
    """The servers the player picked for each game they've picked for."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT game, guilds FROM coop_invites WHERE discord_id = ?",
            (discord_id,),
        ).fetchall()
    return {game: _guild_ids(raw) for game, raw in rows}


def pick(discord_id: str, game: str) -> list[str] | None:
    """The servers the player picked for the game, or None if they haven't."""
    with connect() as conn:
        row = conn.execute(
            "SELECT guilds FROM coop_invites WHERE discord_id = ? AND game = ?",
            (discord_id, game),
        ).fetchone()
    return _guild_ids(row[0]) if row else None


def _guild_ids(raw: str) -> list[str]:
    value: Any = json.loads(raw)
    items = cast(list[Any], value) if isinstance(value, list) else []
    return [item for item in items if isinstance(item, str)]
