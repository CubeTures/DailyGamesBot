"""mitmproxy addon shared by every game's reverse-proxy listener.

mitmdump loads this file as a script (see proxy/mitmdump.py), and the local
port a request arrived on says which game it's for. Games an admin has turned
off on the launcher aren't served.
"""

import html
import time

from mitmproxy import ctx, http
from mitmproxy.addonmanager import Loader

from src import results
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

# How long a game being turned on or off can take to reach the proxy, which
# would otherwise read the database on every request.
_DISABLED_TTL_SECS = 5.0
# Marks a flow answered with _disabled_response, for response() to leave alone.
_DISABLED_KEY = "dgb_disabled"

_hooks = {port: load_hooks(game.name) for port, game in GAMES_BY_PORT.items()}
_origin_rewriters = {
    port: rewrite.OriginRewriter(game.origin, game.local_origin)
    for port, game in GAMES_BY_PORT.items()
}


_disabled: set[str] = set()
_disabled_checked_at = float("-inf")


def _is_disabled(game: Game) -> bool:
    global _disabled, _disabled_checked_at
    now = time.monotonic()
    if now - _disabled_checked_at > _DISABLED_TTL_SECS:
        _disabled = results.disabled_games()
        _disabled_checked_at = now
    return game.name in _disabled


def _disabled_response(game: Game) -> http.Response:
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


def _game_for(flow: http.HTTPFlow) -> Game | None:
    return GAMES_BY_PORT.get(flow.client_conn.sockname[1])


def request(flow: http.HTTPFlow) -> None:
    game = _game_for(flow)
    if game is None:
        return
    if _is_disabled(game):
        flow.response = _disabled_response(game)
        flow.metadata[_DISABLED_KEY] = True
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
        or is_capture_path(flow.request.path)
        or flow.metadata.get(_DISABLED_KEY)
    ):
        return
    assert flow.response is not None
    rewrite.strip_blocking_headers(flow.response)
    rewrite.localize_cookies(flow.response)
    _origin_rewriters[game.port].apply(flow.response)
    inject_script_tag(flow.response, game)
    _hooks[game.port].response(flow)


def load(_loader: Loader) -> None:
    ctx.log.info(f"Daily Games Bot addon loaded for ports: {sorted(GAMES_BY_PORT)}")
