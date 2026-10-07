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

HookFn = Callable[[http.HTTPFlow], None]


def _no_op(flow: http.HTTPFlow) -> None:
    pass


@dataclass(frozen=True)
class GameHooks:
    request: HookFn = _no_op
    response: HookFn = _no_op


def load_hooks(game_name: str) -> GameHooks:
    module_name = f"{__name__}.{game_name}"
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as e:
        if e.name != module_name:
            raise
        return GameHooks()
    return GameHooks(
        request=cast(HookFn, getattr(module, "request", _no_op)),
        response=cast(HookFn, getattr(module, "response", _no_op)),
    )
