"""Shared mitmproxy addon for all reverse-proxied game listeners.

Load with: mitmdump -s src/proxy/addon.py --mode reverse:<origin>@<port> ...

For each configured local port this:
  * strips headers that would otherwise block loading/framing the game
    from a localhost origin (X-Frame-Options, CSP, HSTS)
  * rewrites Set-Cookie so cookies bind to localhost instead of the
    upstream domain, and work over plain HTTP
  * injects the result-capture script into pages of games that have
    capture triggers, and answers its /__dgb/ requests (proxy/capture.py)
  * dispatches to the matching proxy/hooks/<game>.py module, if any, so
    bot/solver logic can be added later without touching this file
"""

import importlib
import re
from collections.abc import Callable
from types import ModuleType
from typing import cast

from mitmproxy import ctx, http
from mitmproxy.addonmanager import Loader

from src.proxy import capture
from src.proxy.config import GAME_CONFIGS, GAMES

_COOKIE_DOMAIN_RE = re.compile(rb";\s*Domain=[^;]*", re.IGNORECASE)
_COOKIE_SECURE_RE = re.compile(rb";\s*Secure", re.IGNORECASE)

_TEXT_CONTENT_TYPES = ("html", "javascript", "json", "css", "text/")

_HookFn = Callable[[http.HTTPFlow], None]

_hook_modules: dict[int, ModuleType | None] = {}
_origin_rewrites: dict[int, list[tuple[bytes, bytes]]] = {}
for port, (name, origin) in GAMES.items():
    try:
        _hook_modules[port] = importlib.import_module(f"src.proxy.hooks.{name}")
    except ModuleNotFoundError as e:
        if e.name != f"src.proxy.hooks.{name}":
            raise
        _hook_modules[port] = None
    real = origin.encode()
    local = f"http://localhost:{port}".encode()
    # also cover escaped-slash forms seen inside embedded JSON config blobs,
    # e.g. "https:\/\/www.nytimes.com" or "https://www.nytimes.com"
    _origin_rewrites[port] = [
        (real, local),
        (real.replace(b"://", b":\\/\\/"), local.replace(b"://", b":\\/\\/")),
        (
            real.replace(b"://", b":\\u002F\\u002F"),
            local.replace(b"://", b":\\u002F\\u002F"),
        ),
    ]


def _local_port(flow: http.HTTPFlow) -> int:
    return flow.client_conn.sockname[1]


def _game_for(flow: http.HTTPFlow) -> tuple[int, tuple[str, str] | None]:
    port = _local_port(flow)
    return port, GAMES.get(port)


def _hook_fn(port: int, name: str) -> _HookFn | None:
    hook = _hook_modules.get(port)
    if hook is None:
        return None
    return cast("_HookFn | None", getattr(hook, name, None))


def request(flow: http.HTTPFlow) -> None:
    port, game = _game_for(flow)
    if game is None:
        return

    if capture.handle_request(flow, GAME_CONFIGS[port]):
        return
    capture.strip_discord_cookie(flow)

    # Force a full response instead of a bodyless 304: the client's cache
    # validators were earned against whatever it loaded last through this
    # proxy, and a 304 here can leave the page with no body to render.
    flow.request.headers.pop("if-none-match", None)
    flow.request.headers.pop("if-modified-since", None)

    hook_request = _hook_fn(port, "request")
    if hook_request is not None:
        hook_request(flow)


def response(flow: http.HTTPFlow) -> None:
    port, game = _game_for(flow)
    if game is None or flow.request.path.startswith(capture.PREFIX):
        return
    assert flow.response is not None

    headers = flow.response.headers
    for h in (
        "x-frame-options",
        "content-security-policy",
        "strict-transport-security",
    ):
        headers.pop(h, None)

    set_cookies = headers.get_all("set-cookie")
    if set_cookies:
        rewritten: list[str] = []
        for cookie in set_cookies:
            raw = cookie.encode("latin-1")
            raw = _COOKIE_DOMAIN_RE.sub(b"", raw)
            raw = _COOKIE_SECURE_RE.sub(b"", raw)
            rewritten.append(raw.decode("latin-1"))
        headers.set_all("set-cookie", rewritten)

    # Pages/JS often hardcode absolute URLs back to the real origin (game
    # data endpoints, fonts, manifests). Those bypass the proxy entirely and
    # get blocked by CORS from a localhost origin, so rewrite them in-place
    # for textual responses.
    content_type = cast(str, headers.get("content-type", ""))
    if any(t in content_type for t in _TEXT_CONTENT_TYPES):
        content = flow.response.content
        if content:
            changed = False
            for real, local in _origin_rewrites[port]:
                if real in content:
                    content = content.replace(real, local)
                    changed = True
            if changed:
                flow.response.content = content

    capture.inject(flow, GAME_CONFIGS[port])

    hook_response = _hook_fn(port, "response")
    if hook_response is not None:
        hook_response(flow)


def load(_loader: Loader) -> None:
    ctx.log.info(f"Daily Games Bot addon loaded for ports: {sorted(GAMES)}")
