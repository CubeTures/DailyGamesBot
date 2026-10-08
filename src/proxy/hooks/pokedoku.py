"""PokeDoku fetches its puzzle API and Lottie animations from other hosts."""

from mitmproxy import http

from src.games.registry import GAMES_BY_NAME
from src.proxy.rewrite import ForeignHostRouter

_game = GAMES_BY_NAME["pokedoku"]
_router = ForeignHostRouter(
    _game.origin,
    _game.local_origin,
    ["api.pokedoku.com", "pokedoku-space.nyc3.cdn.digitaloceanspaces.com"],
)


def request(flow: http.HTTPFlow) -> None:
    _router.route(flow.request)


def response(flow: http.HTTPFlow) -> None:
    assert flow.response is not None
    _router.apply(flow.response)
