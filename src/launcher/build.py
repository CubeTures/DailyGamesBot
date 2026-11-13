"""Renders launcher/index.html from templates/ and the game configs, and the
pages shown instead of it to visitors without a working /play link."""

import base64
from pathlib import Path
from threading import Lock
from typing import Any
from urllib.parse import quote

import jinja2

from src.games.loader import modes_of
from src.games.models import ICON_MIME_TYPES, Game
from src.games.registry import GAMES_BY_NAME
from src.proxy.capture import ENTER_PATH
from src.settings import LAUNCHER_DIR, results_channel_ids

TEMPLATES_DIR = Path(__file__).with_name("templates")
GAME_DAY_JS = Path(__file__).parents[1] / "games" / "game_day.js"
FAVICON_PATH = TEMPLATES_DIR / "favicon.png"
OUTPUT_PATH = LAUNCHER_DIR / "index.html"
# Where the launcher's server puts the viewer's token as it sends the page.
TOKEN_PLACEHOLDER = "__DGB_TOKEN__"

# The launcher's server re-renders the page from its request threads.
_write_lock = Lock()


def write_launcher() -> str:
    """Write the page, swapping it in whole so it's never read half-written,
    and return it."""
    page = render_launcher()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp_path = OUTPUT_PATH.with_suffix(".tmp")
    with _write_lock:
        temp_path.write_text(page)
        temp_path.replace(OUTPUT_PATH)
    return page


def render_launcher() -> str:
    games = sorted(GAMES_BY_NAME.values(), key=lambda game: game.title.casefold())
    # A game's modes share one stack of cards, in their order.
    stacks = [modes_of(GAMES_BY_NAME, game) for game in games if game.mode_of is None]
    return (
        _environment()
        .get_template("index.html.j2")
        .render(
            token_placeholder=TOKEN_PLACEHOLDER,
            stacks=[[_card(mode) for mode in stack] for stack in stacks],
            game_titles={game.name: game.title for game in games},
            full_titles={game.name: full_title(game) for game in games},
            modes={
                stack[0].name: [
                    {"game": mode.name, "mode": mode.mode} for mode in stack
                ]
                for stack in stacks
                if len(stack) > 1
            },
            resets={game.name: game.reset.js_config() for game in games},
            higher_score_wins=[game.name for game in games if game.higher_score_wins],
            # Game roles live in the results channel's server.
            roles_enabled=bool(results_channel_ids()),
            game_day_js=GAME_DAY_JS.read_text(),
            favicon=_favicon_data_uri(),
        )
    )


def render_locked(expired: bool) -> str:
    """The page for visitors without a token, or with one that's been reset."""
    return (
        _environment()
        .get_template("locked.html.j2")
        .render(expired=expired, favicon=_favicon_data_uri())
    )


def _environment() -> jinja2.Environment:
    return jinja2.Environment(
        loader=jinja2.FileSystemLoader(TEMPLATES_DIR),
        autoescape=True,
        keep_trailing_newline=True,
    )


def full_title(game: Game) -> str:
    """A mode's title is the title of the game it's a mode of, then its
    mode ("Costcodle Checkout"); any other game's is just its title."""
    if game.mode is None:
        return game.title
    return f"{GAMES_BY_NAME[game.group].title} {game.mode}"


def _card(game: Game) -> dict[str, Any]:
    return {
        "name": game.name,
        # Every mode's card carries the title of the game they're modes of.
        "title": GAMES_BY_NAME[game.group].title,
        "full_title": full_title(game),
        "mode": game.mode,
        "description": game.description,
        "icon": _icon_data_uri(game),
        # Through /__dgb/enter, which app.js tags with the player's ID.
        "url": f"{game.local_origin}{ENTER_PATH}?to={quote(game.landing_path)}",
        "reset_timezone": game.reset.zone_name,
    }


def _icon_data_uri(game: Game) -> str | None:
    """The icon inlined, so the launcher stays one self-contained file."""
    if game.icon_path is None:
        return None
    return _data_uri(game.icon_path, ICON_MIME_TYPES[game.icon_path.suffix])


def _favicon_data_uri() -> str:
    return _data_uri(FAVICON_PATH, "image/png")


def _data_uri(path: Path, mime_type: str) -> str:
    data = base64.b64encode(path.read_bytes()).decode()
    return f"data:{mime_type};base64,{data}"


if __name__ == "__main__":
    write_launcher()
    print(f"wrote {OUTPUT_PATH}")
