"""Serves the launcher page and its JSON API: the results its scoreboard
reads, the role subscriptions its bells toggle, and the admin calls that turn
games on and off.

Players are identified by the unauthenticated `discord_id` the page sends.
"""

import json
from collections.abc import Callable, Generator
from contextlib import contextmanager
from datetime import date
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from typing import Any, TypeGuard, cast
from urllib.parse import parse_qs, urlsplit

from src import announce
from src.games.registry import GAMES_BY_NAME
from src.launcher.build import write_launcher
from src.settings import LAUNCHER_DIR, LAUNCHER_PORT
from src.store import disabled_games, players, results, subscriptions

Reply = tuple[int, Any]


def _get_results(params: dict[str, str]) -> Reply:
    """GET /api/results?day=YYYY-MM-DD: that game day's results."""
    # The page sends the viewer's local date; fall back to the server's.
    day = _parse_day(params.get("day")) or date.today()
    return 200, [_result_json(r) for r in results.on_day(day)]


def _get_subscriptions(params: dict[str, str]) -> Reply:
    """GET /api/subscriptions?discord_id=ID: the games whose role they want."""
    discord_id = params.get("discord_id")
    if not _is_discord_id(discord_id):
        return _error(400, "need a discord_id")
    return 200, {"games": subscriptions.subscribed_games(discord_id)}


def _get_admin(params: dict[str, str]) -> Reply:
    """GET /api/admin?discord_id=ID: whether they may turn games on and off."""
    discord_id = params.get("discord_id")
    if not _is_discord_id(discord_id):
        return _error(400, "need a discord_id")
    return 200, {"admin": players.is_admin(discord_id)}


def _post_subscription(body: bytes) -> Reply:
    """POST /api/subscriptions {"discord_id", "game", "subscribed"}."""
    request = _player_game_flag(body, "subscribed")
    if request is None:
        return _error(400, "need discord_id, game and subscribed")
    subscriptions.save(subscriptions.Subscription(*request))
    return 200, {"ok": True}


def _post_game_toggle(body: bytes) -> Reply:
    """POST /api/games {"discord_id", "game", "enabled"}: admins only."""
    request = _player_game_flag(body, "enabled")
    if request is None:
        return _error(400, "need discord_id, game and enabled")
    discord_id, game, enabled = request
    if not players.is_admin(discord_id):
        return _error(403, "only server admins can do that")
    disabled_games.set_enabled(game, enabled)
    # The page is static, so re-render it with the game shown or hidden.
    write_launcher()
    return 200, {"ok": True}


_GET_ROUTES: dict[str, Callable[[dict[str, str]], Reply]] = {
    "/api/results": _get_results,
    "/api/subscriptions": _get_subscriptions,
    "/api/admin": _get_admin,
}
_POST_ROUTES: dict[str, Callable[[bytes], Reply]] = {
    "/api/subscriptions": _post_subscription,
    "/api/games": _post_game_toggle,
}


class _LauncherRequestHandler(SimpleHTTPRequestHandler):
    def do_GET(self) -> None:
        url = urlsplit(self.path)
        route = _GET_ROUTES.get(url.path)
        if route is None:
            super().do_GET()  # the page itself
            return
        params = {key: values[0] for key, values in parse_qs(url.query).items()}
        self._send_json(*route(params))

    def do_POST(self) -> None:
        route = _POST_ROUTES.get(urlsplit(self.path).path)
        if route is None:
            self._send_json(*_error(404, "not found"))
            return
        length = int(self.headers.get("Content-Length") or 0)
        self._send_json(*route(self.rfile.read(length)))

    def _send_json(self, status: int, body: Any) -> None:
        encoded = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


@contextmanager
def serve_launcher(port: int = LAUNCHER_PORT) -> Generator[None]:
    """Regenerate the launcher page and serve it in a background thread."""
    write_launcher()
    handler = partial(_LauncherRequestHandler, directory=str(LAUNCHER_DIR))
    server = ThreadingHTTPServer(("0.0.0.0", port), handler)
    Thread(target=server.serve_forever, daemon=True).start()
    try:
        yield
    finally:
        server.shutdown()


def _result_json(result: results.StoredResult) -> dict[str, Any]:
    game = GAMES_BY_NAME.get(result.game)
    return {
        "game": result.game,
        "discord_id": result.discord_id,
        "name": result.player_name,
        "puzzle_id": result.puzzle_id,
        "data": result.data,
        "captured_at": result.captured_at.isoformat(),
        # What the bot posts, or None if the game's config is gone. The page
        # has no role IDs, so the role mention carries the game's name instead.
        "announcement": (
            announce.render_result(game, result, game_mention=f"<@&{game.name}>")
            if game
            else None
        ),
    }


def _player_game_flag(body: bytes, flag: str) -> tuple[str, str, bool] | None:
    """`discord_id`, `game` and the boolean `flag` from a JSON body, or None
    if any is missing or invalid."""
    try:
        payload: Any = json.loads(body)
    except ValueError:
        return None
    if not isinstance(payload, dict):
        return None
    fields = cast(dict[str, Any], payload)
    discord_id, game, value = (
        fields.get("discord_id"),
        fields.get("game"),
        fields.get(flag),
    )
    if (
        not _is_discord_id(discord_id)
        or game not in GAMES_BY_NAME
        or not isinstance(value, bool)
    ):
        return None
    return discord_id, cast(str, game), value


def _is_discord_id(value: object) -> TypeGuard[str]:
    return isinstance(value, str) and value.isascii() and value.isdigit()


def _parse_day(raw: str | None) -> date | None:
    """A YYYY-MM-DD date, or None if it's missing or invalid."""
    try:
        return date.fromisoformat(raw or "")
    except ValueError:
        return None


def _error(status: int, message: str) -> Reply:
    return status, {"error": message}
