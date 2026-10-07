"""The configured games, loaded once at import."""

import sys

from src.games.loader import load_games
from src.games.models import Game

GAMES_BY_PORT = load_games()
GAMES_BY_NAME = {game.name: game for game in GAMES_BY_PORT.values()}


def game_from_argv(module: str, *arg_names: str) -> tuple[Game, list[str]]:
    """For dev CLIs called as `python -m <module> <game> <arg_names...>`:
    the named game and the remaining args. Exits with usage if they're wrong."""
    args = sys.argv[1:]
    if len(args) != 1 + len(arg_names) or args[0] not in GAMES_BY_NAME:
        game_names = "|".join(sorted(GAMES_BY_NAME))
        usage = " ".join([f"python -m {module}", f"<{game_names}>", *arg_names])
        sys.exit(f"usage: {usage}")
    return GAMES_BY_NAME[args[0]], args[1:]
