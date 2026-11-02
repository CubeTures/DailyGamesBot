"""The Discord servers players are registered with.

A player registers with a server by running /play in it. Their results are
announced in each of their servers that has a results channel, and the
launcher's scoreboard for a server shows only the players registered with it.
The first server a player registers with is their primary one, which the
scoreboard opens on, until they pick another with /primary. Players are never
unregistered.
"""

from dataclasses import dataclass
from datetime import UTC, datetime

from src.store.db import connect


@dataclass(frozen=True)
class PlayerGuild:
    id: str
    name: str | None


def save_name(guild_id: str, name: str) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO guilds (guild_id, name) VALUES (?, ?)"
            " ON CONFLICT (guild_id) DO UPDATE SET name = excluded.name",
            (guild_id, name),
        )


def register(discord_id: str, guild_id: str) -> bool:
    """Register the player with a server, making it their primary one if they
    have none yet; return False if they were already registered with it."""
    with connect() as conn:
        cursor = conn.execute(
            "INSERT OR IGNORE INTO player_guilds (discord_id, guild_id, registered_at)"
            " VALUES (?, ?, ?)",
            (discord_id, guild_id, datetime.now(UTC).isoformat()),
        )
        conn.execute(
            "INSERT INTO players (discord_id, primary_guild) VALUES (?, ?)"
            " ON CONFLICT (discord_id) DO UPDATE"
            " SET primary_guild = COALESCE(players.primary_guild, excluded.primary_guild)",
            (discord_id, guild_id),
        )
        return cursor.rowcount == 1


def set_primary(discord_id: str, guild_id: str) -> None:
    """Make a server the player's primary one, registering them with it."""
    register(discord_id, guild_id)
    with connect() as conn:
        conn.execute(
            "UPDATE players SET primary_guild = ? WHERE discord_id = ?",
            (guild_id, discord_id),
        )


def primary(discord_id: str) -> str | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT primary_guild FROM players WHERE discord_id = ?", (discord_id,)
        ).fetchone()
    return row[0] if row else None


def of_player(discord_id: str) -> list[PlayerGuild]:
    """The servers the player is registered with, in the order they joined."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT pg.guild_id, g.name FROM player_guilds pg"
            " LEFT JOIN guilds g USING (guild_id)"
            " WHERE pg.discord_id = ? ORDER BY pg.registered_at, pg.rowid",
            (discord_id,),
        ).fetchall()
    return [PlayerGuild(guild_id, name) for guild_id, name in rows]


def is_registered(discord_id: str, guild_id: str) -> bool:
    with connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM player_guilds WHERE discord_id = ? AND guild_id = ?",
            (discord_id, guild_id),
        ).fetchone()
    return row is not None


def unregistered_players() -> list[str]:
    """Players with no server, e.g. from before servers were tracked."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT discord_id FROM players WHERE discord_id NOT IN"
            " (SELECT discord_id FROM player_guilds)"
        ).fetchall()
    return [discord_id for (discord_id,) in rows]
