"""Serves the launcher page and its JSON API: the results its scoreboard
reads, the role subscriptions its bells toggle, and the games each player has
hidden.

Players are identified by the token from their /play link, which the store
maps to their Discord ID (see store/players.py). The page is only sent for a
working token, from the link's ?token= or the cookie set when it was opened;
anyone else gets a page telling them to run /play. The API takes the token as
a parameter.
"""

import json
from collections.abc import Callable, Generator
from contextlib import contextmanager
from datetime import date
from functools import partial
from http.cookies import CookieError, SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from typing import Any, cast
from urllib.parse import parse_qs, urlsplit

from src import announce
from src.games.registry import GAMES_BY_NAME
from src.launcher.build import (
    TOKEN_PLACEHOLDER,
    render_locked,
    write_launcher,
)
from src.proxy.capture import TOKEN_COOKIE, token_cookie
from src.settings import LAUNCHER_PORT
from src.store import hidden_games, players, results, subscriptions

Reply = tuple[int, Any]


def _get_results(params: dict[str, str]) -> Reply:
    """GET /api/results?day=YYYY-MM-DD&token=TOKEN: that game day's results."""
    _player(params.get("token"))
    # The page sends the viewer's local date; fall back to the server's.
    day = _parse_day(params.get("day")) or date.today()
    return 200, [_result_json(r) for r in results.on_day(day)]


def _get_me(params: dict[str, str]) -> Reply:
    """GET /api/me?token=TOKEN: {"discord_id"} of the token's player."""
    return 200, {"discord_id": _player(params.get("token"))}


def _get_subscriptions(params: dict[str, str]) -> Reply:
    """GET /api/subscriptions?token=TOKEN: the games whose role they want."""
    discord_id = _player(params.get("token"))
    return 200, {"games": subscriptions.subscribed_games(discord_id)}


def _get_hidden(params: dict[str, str]) -> Reply:
    """GET /api/hidden?token=TOKEN: {game: "card" | "all"} for the games
    they've hidden."""
    discord_id = _player(params.get("token"))
    return 200, {"games": hidden_games.levels(discord_id)}


def _post_subscription(body: bytes) -> Reply:
    """POST /api/subscriptions {"token", "game", "subscribed"}."""
    discord_id, game, subscribed = _player_game_value(body, "subscribed")
    if not isinstance(subscribed, bool):
        return _error(400, "need token, game and subscribed")
    subscriptions.save(subscriptions.Subscription(discord_id, game, subscribed))
    return 200, {"ok": True}


def _post_hidden(body: bytes) -> Reply:
    """POST /api/hidden {"token", "game", "level"}, where level is "shown",
    "card" or "all"."""
    discord_id, game, level = _player_game_value(body, "level")
    if not hidden_games.is_hide_level(level):
        return _error(400, "level must be shown, card or all")
    hidden_games.set_level(discord_id, game, level)
    return 200, {"ok": True}


_GET_ROUTES: dict[str, Callable[[dict[str, str]], Reply]] = {
    "/api/me": _get_me,
    "/api/results": _get_results,
    "/api/subscriptions": _get_subscriptions,
    "/api/hidden": _get_hidden,
}
_POST_ROUTES: dict[str, Callable[[bytes], Reply]] = {
    "/api/subscriptions": _post_subscription,
    "/api/hidden": _post_hidden,
}


_PAGE_PATHS = {"/", "/index.html"}


class _LauncherRequestHandler(BaseHTTPRequestHandler):
    def __init__(self, *args: Any, page: str, **kwargs: Any) -> None:
        self.page = page
        super().__init__(*args, **kwargs)

    def do_GET(self) -> None:
        url = urlsplit(self.path)
        params = {key: values[0] for key, values in parse_qs(url.query).items()}
        route = _GET_ROUTES.get(url.path)
        if route is not None:
            self._send_json(*_answer(route, params))
        elif url.path in _PAGE_PATHS:
            self._send_page(params.get("token"))
        else:
            self._send_json(*_error(404, "not found"))

    def do_POST(self) -> None:
        route = _POST_ROUTES.get(urlsplit(self.path).path)
        if route is None:
            self._send_json(*_error(404, "not found"))
            return
        length = int(self.headers.get("Content-Length") or 0)
        self._send_json(*_answer(route, self.rfile.read(length)))

    def _send_page(self, link_token: str | None) -> None:
        """The launcher for a working token from the link or cookie, else the
        page telling the visitor to run /play."""
        cookie_token = self._cookie_token()
        token = link_token or cookie_token
        if token is not None and players.discord_id_for(token) is not None:
            # Opened from a /play link: remember it for visits without one.
            cookie = token_cookie(token) if token != cookie_token else None
            page = self.page.replace(TOKEN_PLACEHOLDER, token)
            self._send(200, "text/html; charset=utf-8", page.encode(), cookie)
        else:
            # Drop a cookie whose token an admin has reset.
            cookie = f"{TOKEN_COOKIE}=; Path=/; Max-Age=0" if cookie_token else None
            page = render_locked(expired=token is not None)
            self._send(401, "text/html; charset=utf-8", page.encode(), cookie)

    def _cookie_token(self) -> str | None:
        try:
            cookies = SimpleCookie(self.headers.get("Cookie") or "")
        except CookieError:
            return None
        morsel = cookies.get(TOKEN_COOKIE)
        return morsel.value if morsel else None

    def _send_json(self, status: int, body: Any) -> None:
        self._send(status, "application/json", json.dumps(body).encode())

    def _send(
        self,
        status: int,
        content_type: str,
        body: bytes,
        set_cookie: str | None = None,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        if set_cookie:
            self.send_header("Set-Cookie", set_cookie)
        self.end_headers()
        self.wfile.write(body)


@contextmanager
def serve_launcher(port: int = LAUNCHER_PORT) -> Generator[None]:
    """Regenerate the launcher page and serve it in a background thread, for
    the proxy to pass requests on to."""
    handler = partial(_LauncherRequestHandler, page=write_launcher())
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
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


def _player(token: object) -> str:
    """The Discord ID a token from a /play link stands for."""
    discord_id = players.discord_id_for(token) if isinstance(token, str) else None
    if discord_id is None:
        # Never issued, or an admin has reset it since.
        raise _ApiError(401, "link expired; run /play for a new one")
    return discord_id


def _player_game_value(body: bytes, key: str) -> tuple[str, str, object]:
    """The player its `token` stands for, `game` and the value of `key` from
    a JSON body."""
    try:
        payload: Any = json.loads(body)
    except ValueError:
        payload = None
    fields = cast(dict[str, Any], payload) if isinstance(payload, dict) else {}
    game = fields.get("game")
    if game not in GAMES_BY_NAME:
        raise _ApiError(400, f"need token, game and {key}")
    return _player(fields.get("token")), cast(str, game), fields.get(key)


def _parse_day(raw: str | None) -> date | None:
    """A YYYY-MM-DD date, or None if it's missing or invalid."""
    try:
        return date.fromisoformat(raw or "")
    except ValueError:
        return None


def _error(status: int, message: str) -> Reply:
    return status, {"error": message}


class _ApiError(Exception):
    """Raised by a route to reply with an error."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.reply = _error(status, message)


def _answer[T](route: Callable[[T], Reply], request: T) -> Reply:
    try:
        return route(request)
    except _ApiError as e:
        return e.reply
