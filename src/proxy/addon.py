"""mitmproxy addon shared by every game's reverse-proxy listener.

mitmdump loads this file as a script (see proxy/mitmdump.py), and the local
port a request arrived on says which game it's for.
"""

from mitmproxy import ctx, http
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

_hooks = {port: load_hooks(game.name) for port, game in GAMES_BY_PORT.items()}
_origin_rewriters = {
    port: rewrite.OriginRewriter(game.origin, game.local_origin)
    for port, game in GAMES_BY_PORT.items()
}


def _game_for(flow: http.HTTPFlow) -> Game | None:
    return GAMES_BY_PORT.get(flow.client_conn.sockname[1])


def request(flow: http.HTTPFlow) -> None:
    game = _game_for(flow)
    if game is None or handle_capture_request(flow, game):
        return
    strip_discord_id_cookie(flow.request)
    rewrite.drop_cache_validators(flow.request)
    _hooks[game.port].request(flow)


def response(flow: http.HTTPFlow) -> None:
    game = _game_for(flow)
    if game is None or is_capture_path(flow.request.path):
        return
    assert flow.response is not None
    rewrite.strip_blocking_headers(flow.response)
    rewrite.localize_cookies(flow.response)
    _origin_rewriters[game.port].apply(flow.response)
    inject_script_tag(flow.response, game)
    _hooks[game.port].response(flow)


def load(_loader: Loader) -> None:
    ctx.log.info(f"Daily Games Bot addon loaded for ports: {sorted(GAMES_BY_PORT)}")
