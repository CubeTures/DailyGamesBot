"""Optional per-game proxy hooks.

To inspect or modify a game's traffic, add `src/proxy/hooks/<game>.py`
defining `request(flow)` and/or `response(flow)`, taking a
mitmproxy.http.HTTPFlow. They run after the proxy's own handling.
"""

import importlib
from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from mitmproxy import http

from src.games.registry import GAMES_BY_NAME
from src.proxy.rewrite import ForeignHostRouter

Hook = Callable[[http.HTTPFlow], None]


def _no_op(flow: http.HTTPFlow) -> None:
    pass


@dataclass(frozen=True)
class GameHooks:
    request: Hook = _no_op
    response: Hook = _no_op


def load_hooks(game_name: str) -> GameHooks:
    module_name = f"{__name__}.{game_name}"
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as e:
        if e.name != module_name:
            raise
        return GameHooks()
    return GameHooks(
        request=cast(Hook, getattr(module, "request", _no_op)),
        response=cast(Hook, getattr(module, "response", _no_op)),
    )


def route_foreign_hosts(game_name: str, hosts: list[str]) -> tuple[Hook, Hook]:
    """`request` and `response` hooks serving `hosts`, which the game's JS
    fetches from, under the game's own port (see ForeignHostRouter)."""
    game = GAMES_BY_NAME[game_name]
    router = ForeignHostRouter(game.origin, game.local_origin, hosts)

    def request(flow: http.HTTPFlow) -> None:
        router.route(flow.request)

    def response(flow: http.HTTPFlow) -> None:
        if flow.response is not None:
            router.apply(flow.response)

    return request, response
