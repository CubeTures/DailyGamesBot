"""Renders launcher/index.html from templates/ and the game configs."""

import base64
from pathlib import Path
from typing import Any

import jinja2

from src.games.models import ICON_MIME_TYPES, Game
from src.games.registry import GAMES_BY_PORT
from src.settings import LAUNCHER_DIR

TEMPLATES_DIR = Path(__file__).with_name("templates")
OUTPUT_PATH = LAUNCHER_DIR / "index.html"


def _icon_data_uri(game: Game) -> str | None:
    """The icon inlined, so the launcher stays one self-contained file."""
    if game.icon_path is None:
        return None
    mime_type = ICON_MIME_TYPES[game.icon_path.suffix]
    data = base64.b64encode(game.icon_path.read_bytes()).decode()
    return f"data:{mime_type};base64,{data}"


def _card(game: Game) -> dict[str, Any]:
    return {
        "name": game.name,
        "title": game.title,
        "description": game.description,
        "icon": _icon_data_uri(game),
        "url": game.local_origin + game.landing_path,
    }


def render_launcher() -> str:
    games = [game for _, game in sorted(GAMES_BY_PORT.items())]
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(TEMPLATES_DIR),
        autoescape=True,
        keep_trailing_newline=True,
    )
    return env.get_template("index.html.j2").render(
        games=[_card(game) for game in games],
        game_titles={game.name: game.title for game in games},
    )


def write_launcher() -> None:
    OUTPUT_PATH.write_text(render_launcher())


if __name__ == "__main__":
    write_launcher()
    print(f"wrote {OUTPUT_PATH}")
