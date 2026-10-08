"""Validates every game in games/ and regenerates games/schema.json:
`uv run python3 -m src.games`."""

import sys

from src.games.loader import ConfigError, load_games
from src.games.schema import SCHEMA_PATH, write_schema
from src.settings import LAUNCHER_PORT, REPO_ROOT


def main() -> None:
    # Before loading the games, so the schema stays current even when one of
    # them is broken.
    if write_schema():
        print(f"updated {SCHEMA_PATH.relative_to(REPO_ROOT)}")
    try:
        games = load_games()
    except ConfigError as e:
        sys.exit(str(e))
    for port, game in sorted(games.items()):
        triggers = ", ".join(f"{t.name} ({t.type})" for t in game.triggers) or "none"
        print(f"{port}  {game.name:<16} {game.origin}  triggers: {triggers}")
    port = max(games, default=8080) + 1
    if port == LAUNCHER_PORT:
        port += 1
    print(f"next free port: {port}")


if __name__ == "__main__":
    main()
