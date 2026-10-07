"""Prints a game's compiled capture script, e.g. to `node --check` it:
`uv run python3 -m src.proxy.capture <game>`."""

from src.games.registry import game_from_argv
from src.proxy.capture.script import build_script

if __name__ == "__main__":
    game, _ = game_from_argv("src.proxy.capture")
    print(build_script(game))
