"""Regenerate launcher/index.html from proxy/config.py."""

import base64
from pathlib import Path

import jinja2

from src.proxy.config import GAME_CONFIGS, ICON_TYPES, REPO_ROOT, Game

__all__ = ["REPO_ROOT", "build", "write"]

TEMPLATE_PATH = Path(__file__).with_name("launcher.html.j2")


def _icon_data_uri(game: Game) -> str | None:
    """The icon inlined, so the launcher stays one self-contained file."""
    if game.icon_path is None:
        return None
    mime = ICON_TYPES[game.icon_path.suffix]
    data = base64.b64encode(game.icon_path.read_bytes()).decode()
    return f"data:{mime};base64,{data}"


def build() -> str:
    games = [
        {
            "name": game.name,
            "title": game.title,
            "description": game.description,
            "icon": _icon_data_uri(game),
            "port": port,
            "path": game.landing_path,
        }
        for port, game in sorted(GAME_CONFIGS.items())
    ]
    titles = {g["name"]: g["title"] for g in games}
    env = jinja2.Environment(autoescape=True, keep_trailing_newline=True)
    template = env.from_string(TEMPLATE_PATH.read_text())
    return template.render(games=games, game_titles=titles)


def write() -> Path:
    out = REPO_ROOT / "launcher" / "index.html"
    out.write_text(build())
    return out


if __name__ == "__main__":
    print(f"wrote {write()}")
