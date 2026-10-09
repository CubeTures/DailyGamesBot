"""Validates every game in games/ and regenerates games/schema.json:
`uv run python3 -m src.games`."""

import sys

from src.games.loader import ConfigError, load_games
from src.games.schema import SCHEMA_PATH, write_schema
from src.settings import REPO_ROOT


def main() -> None:
    # Before loading the games, so the schema stays current even when one of
    # them is broken.
    if write_schema():
        print(f"updated {SCHEMA_PATH.relative_to(REPO_ROOT)}")
    try:
        games = load_games()
    except ConfigError as e:
        sys.exit(str(e))
    for game in games.values():
        triggers = ", ".join(f"{t.name} ({t.type})" for t in game.triggers) or "none"
        print(
            f"{game.name:<16} {game.local_origin} -> {game.origin}  triggers: {triggers}"
        )


if __name__ == "__main__":
    main()
