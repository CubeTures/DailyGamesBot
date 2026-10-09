"""Games an admin has turned off: hidden on the launcher and not proxied.
Their results are kept."""

from src.store.db import connect


def set_enabled(game: str, enabled: bool) -> None:
    with connect() as conn:
        if enabled:
            conn.execute("DELETE FROM disabled_games WHERE game = ?", (game,))
        else:
            conn.execute(
                "INSERT OR IGNORE INTO disabled_games (game) VALUES (?)", (game,)
            )


def names() -> set[str]:
    with connect() as conn:
        rows = conn.execute("SELECT game FROM disabled_games").fetchall()
    return {game for (game,) in rows}
