"""Renders launcher/index.html from templates/ and the game configs."""

import base64
from pathlib import Path
from threading import Lock
from typing import Any

import jinja2

from src import results
from src.discord_bot.settings import results_channel_id
from src.games.models import ICON_MIME_TYPES, LOCAL_TIMEZONE, Game
from src.games.registry import GAMES_BY_PORT
from src.settings import LAUNCHER_DIR

TEMPLATES_DIR = Path(__file__).with_name("templates")
OUTPUT_PATH = LAUNCHER_DIR / "index.html"
# The launcher's server re-renders the page from its request threads.
_write_lock = Lock()


def _icon_data_uri(game: Game) -> str | None:
    """The icon inlined, so the launcher stays one self-contained file."""
    if game.icon_path is None:
        return None
    mime_type = ICON_MIME_TYPES[game.icon_path.suffix]
    data = base64.b64encode(game.icon_path.read_bytes()).decode()
    return f"data:{mime_type};base64,{data}"


def _card(game: Game, disabled: set[str]) -> dict[str, Any]:
    return {
        "name": game.name,
        "title": game.title,
        "description": game.description,
        "icon": _icon_data_uri(game),
        "url": game.local_origin + game.landing_path,
        # Only games that don't reset at the player's own midnight name their
        # timezone.
        "reset_timezone": None
        if game.reset.timezone == LOCAL_TIMEZONE
        else game.reset.timezone,
        # Turned off by an admin: hidden, except to admins editing the list.
        "disabled": game.name in disabled,
    }


def render_launcher() -> str:
    games = sorted(GAMES_BY_PORT.values(), key=lambda game: game.title.casefold())
    disabled = results.disabled_games()
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(TEMPLATES_DIR),
        autoescape=True,
        keep_trailing_newline=True,
    )
    return env.get_template("index.html.j2").render(
        games=[_card(game, disabled) for game in games],
        game_titles={game.name: game.title for game in games},
        resets={game.name: game.reset.js_config() for game in games},
        higher_score_wins=[game.name for game in games if game.higher_score_wins],
        # Game roles live in the results channel's server.
        roles_enabled=results_channel_id() is not None,
    )


def write_launcher() -> None:
    """Write the page, swapping it in whole so it's never served half-written."""
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp_path = OUTPUT_PATH.with_suffix(".tmp")
    with _write_lock:
        temp_path.write_text(render_launcher())
        temp_path.replace(OUTPUT_PATH)


if __name__ == "__main__":
    write_launcher()
    print(f"wrote {OUTPUT_PATH}")
