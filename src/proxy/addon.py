"""mitmproxy addon shared by every game's reverse-proxy listener.

mitmdump loads this file as a script (see proxy/mitmdump.py). The subdomain
a request was sent to says which game it's for; it's passed on to the game's
real origin. Requests for any other host go on to the launcher.
"""

import logging
from urllib.parse import urlsplit

from mitmproxy import http
from mitmproxy.addonmanager import Loader

from src.games.models import Game
from src.games.registry import GAMES_BY_NAME
from src.proxy import rewrite
from src.proxy.capture.endpoints import (
    handle_capture_request,
    is_capture_path,
    strip_token_cookie,
)
from src.proxy.capture.script import inject_script_tag
from src.proxy.hooks import load_hooks

log = logging.getLogger(__name__)


_GAMES_BY_HOST = {
    (urlsplit(game.local_origin).hostname or "").lower(): game
    for game in GAMES_BY_NAME.values()
}
_hooks = {name: load_hooks(name) for name in GAMES_BY_NAME}
_origin_rewriters = {
    name: rewrite.OriginRewriter(game.origin, game.local_origin)
    for name, game in GAMES_BY_NAME.items()
}
# Which game a flow is for, kept from its request: by its response, the Host
# header names the real origin.
_GAME_KEY = "dgb_game"


def load(_loader: Loader) -> None:
    log.info("Daily Games Bot addon loaded for: %s", ", ".join(_GAMES_BY_HOST))


def request(flow: http.HTTPFlow) -> None:
    game = _GAMES_BY_HOST.get(_hostname(flow.request.host_header))
    if game is None:
        return
    flow.metadata[_GAME_KEY] = game
    if handle_capture_request(flow, game):
        return
    _route_to_origin(flow.request, game)
    strip_token_cookie(flow.request)
    rewrite.drop_cache_validators(flow.request)
    _hooks[game.name].request(flow)


def response(flow: http.HTTPFlow) -> None:
    game: Game | None = flow.metadata.get(_GAME_KEY)
    if game is None or flow.response is None or is_capture_path(flow.request.path):
        return
    rewrite.strip_blocking_headers(flow.response)
    rewrite.localize_cookies(flow.response)
    _origin_rewriters[game.name].apply(flow.response)
    inject_script_tag(flow.response, game)
    _hooks[game.name].response(flow)


def _hostname(host_header: str | None) -> str:
    return (urlsplit(f"//{host_header or ''}").hostname or "").lower()


def _route_to_origin(request: http.Request, game: Game) -> None:
    origin = urlsplit(game.origin)
    request.scheme = origin.scheme
    request.host = origin.hostname or ""
    request.port = origin.port or (443 if origin.scheme == "https" else 80)
    request.host_header = origin.netloc
