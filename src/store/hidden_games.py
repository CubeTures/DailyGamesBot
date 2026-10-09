"""Games each player has hidden on their launcher: just the card, or its
scoreboard too. Only that player's view changes; the game still works and
its results are kept."""

from typing import Literal, TypeGuard, get_args

from src.store.db import connect

# "shown" is the default and is stored as no row.
HideLevel = Literal["shown", "card", "all"]
HIDE_LEVELS: tuple[HideLevel, ...] = get_args(HideLevel)


def is_hide_level(value: object) -> TypeGuard[HideLevel]:
    return value in HIDE_LEVELS


def set_level(discord_id: str, game: str, level: HideLevel) -> None:
    with connect() as conn:
        if level == "shown":
            conn.execute(
                "DELETE FROM hidden_games WHERE discord_id = ? AND game = ?",
                (discord_id, game),
            )
        else:
            conn.execute(
                "INSERT INTO hidden_games (discord_id, game, level) VALUES (?, ?, ?)"
                " ON CONFLICT (discord_id, game) DO UPDATE SET level = excluded.level",
                (discord_id, game, level),
            )


def levels(discord_id: str) -> dict[str, HideLevel]:
    """The player's hidden games, by name; games not listed are shown."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT game, level FROM hidden_games WHERE discord_id = ?",
            (discord_id,),
        ).fetchall()
    return {game: level for game, level in rows if is_hide_level(level)}
