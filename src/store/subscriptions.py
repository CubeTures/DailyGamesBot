"""Which games' Discord roles each player wants.

The launcher saves a choice unsynced; the bot gives or takes the role and
marks it synced. This table is the source of truth: roles changed by hand in
Discord aren't reflected back.
"""

from dataclasses import dataclass

from src.store.db import connect


@dataclass(frozen=True)
class Subscription:
    discord_id: str
    game: str
    subscribed: bool


def save(sub: Subscription) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO subscriptions (discord_id, game, subscribed)"
            " VALUES (?, ?, ?) ON CONFLICT (discord_id, game)"
            " DO UPDATE SET subscribed = excluded.subscribed, synced = 0",
            (sub.discord_id, sub.game, sub.subscribed),
        )


def subscribed_games(discord_id: str) -> list[str]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT game FROM subscriptions WHERE discord_id = ? AND subscribed = 1",
            (discord_id,),
        ).fetchall()
    return [game for (game,) in rows]


def unsynced() -> list[Subscription]:
    """Choices the bot hasn't applied in Discord yet."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT discord_id, game, subscribed FROM subscriptions WHERE synced = 0"
        ).fetchall()
    return [Subscription(d, g, bool(s)) for d, g, s in rows]


def mark_synced(sub: Subscription) -> None:
    """Mark `sub` applied, unless the player has changed it again since."""
    with connect() as conn:
        conn.execute(
            "UPDATE subscriptions SET synced = 1"
            " WHERE discord_id = ? AND game = ? AND subscribed = ?",
            (sub.discord_id, sub.game, sub.subscribed),
        )
