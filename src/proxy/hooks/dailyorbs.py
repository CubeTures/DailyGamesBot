"""Daily Orbs fetches its puzzles and game day from a separate API host."""

from mitmproxy import http

from src.games.registry import GAMES_BY_NAME
from src.proxy.rewrite import ForeignHostRouter

_game = GAMES_BY_NAME["dailyorbs"]
_router = ForeignHostRouter(_game.origin, _game.local_origin, ["api.dailyorbs.com"])


def request(flow: http.HTTPFlow) -> None:
    _router.route(flow.request)


def response(flow: http.HTTPFlow) -> None:
    assert flow.response is not None
    _router.apply(flow.response)
