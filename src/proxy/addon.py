"""mitmproxy addon shared by every game's reverse-proxy listener.

mitmdump loads this file as a script (see proxy/mitmdump.py), and the local
port a request arrived on says which game it's for. Games an admin has turned
off on the launcher aren't served.
"""

import html
import logging
import time

from mitmproxy import http
from mitmproxy.addonmanager import Loader

from src.games.models import Game
from src.games.registry import GAMES_BY_PORT
from src.proxy import rewrite
from src.proxy.capture.endpoints import (
    handle_capture_request,
    is_capture_path,
    strip_discord_id_cookie,
)
from src.proxy.capture.script import inject_script_tag
from src.proxy.hooks import load_hooks
from src.settings import LAUNCHER_URL
from src.store import disabled_games

# Marks a flow answered with _turned_off_response, for response() to leave alone.
_TURNED_OFF_KEY = "dgb_turned_off"

log = logging.getLogger(__name__)


class _DisabledGames:
    """The names of turned-off games, re-read from the store at most every
    `ttl_secs` rather than on every request."""

    def __init__(self, ttl_secs: float) -> None:
        self._ttl_secs = ttl_secs
        self._names: set[str] = set()
        self._read_at = float("-inf")

    def __contains__(self, name: str) -> bool:
        now = time.monotonic()
        if now - self._read_at > self._ttl_secs:
            self._names = disabled_games.names()
            self._read_at = now
        return name in self._names


_disabled = _DisabledGames(ttl_secs=5.0)
_hooks = {port: load_hooks(game.name) for port, game in GAMES_BY_PORT.items()}
_origin_rewriters = {
    port: rewrite.OriginRewriter(game.origin, game.local_origin)
    for port, game in GAMES_BY_PORT.items()
}


def load(_loader: Loader) -> None:
    log.info("Daily Games Bot addon loaded for ports: %s", sorted(GAMES_BY_PORT))


def request(flow: http.HTTPFlow) -> None:
    game = _game_for(flow)
    if game is None:
        return
    if game.name in _disabled:
        flow.response = _turned_off_response(game)
        flow.metadata[_TURNED_OFF_KEY] = True
        return
    if handle_capture_request(flow, game):
        return
    strip_discord_id_cookie(flow.request)
    rewrite.drop_cache_validators(flow.request)
    _hooks[game.port].request(flow)


def response(flow: http.HTTPFlow) -> None:
    game = _game_for(flow)
    if (
        game is None
        or flow.response is None
        or is_capture_path(flow.request.path)
        or flow.metadata.get(_TURNED_OFF_KEY)
    ):
        return
    rewrite.strip_blocking_headers(flow.response)
    rewrite.localize_cookies(flow.response)
    _origin_rewriters[game.port].apply(flow.response)
    inject_script_tag(flow.response, game)
    _hooks[game.port].response(flow)


def _game_for(flow: http.HTTPFlow) -> Game | None:
    return GAMES_BY_PORT.get(flow.client_conn.sockname[1])


def _turned_off_response(game: Game) -> http.Response:
    title = html.escape(game.title)
    body = (
        f"<!doctype html><meta charset=utf-8><title>{title} is off</title>"
        f"<p>{title} has been turned off by a server admin."
        f' <a href="{LAUNCHER_URL}">Back to the games</a></p>'
    )
    return http.Response.make(
        410,
        body,
        {"Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store"},
    )
