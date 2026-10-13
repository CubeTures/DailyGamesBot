"""Keeps Puzzmo on its production backend when served from our own host.

Puzzmo's config treats any host containing "localhost", or any URL with a
port, as staging (`document.location.host.includes(`localhost`)||!!document.
location.port`) and then talks to api-staging.puzzmo.com, which has different
puzzles. This turns that check off in its scripts, and points any staging or
local dev host left over at production as a fallback.

The production API only allows Puzzmo's own sites and localhost origins over
CORS, so when the game is served from another host (DGB_GAME_HOST) its API
calls go through the proxy. Not on localhost: Puzzmo takes an API URL
containing "localhost" for a dev server and switches to dev mode.
"""

from urllib.parse import urlsplit

from mitmproxy import http

from src.games.registry import GAMES_BY_NAME
from src.proxy.hooks import route_foreign_hosts
from src.proxy.rewrite import replace_in_body

_REPLACEMENTS = [
    (b"document.location.host.includes(`localhost`)||!!document.location.port", b"!1"),
    # The game iframe's runtime sends analytics to a local dev API whenever
    # the hostname contains "localhost".
    (b"http://localhost:8911/", b"https://api.puzzmo.com/"),
    *(
        (f"{name}-staging.puzzmo.com".encode(), f"{name}.puzzmo.com".encode())
        for name in ("api", "live", "studio", "thumbnails")
    ),
]

_ROUTE_API = "localhost" not in (
    urlsplit(GAMES_BY_NAME["circuits"].local_origin).hostname or ""
)
_route_request, _route_response = route_foreign_hosts("circuits", ["api.puzzmo.com"])


def request(flow: http.HTTPFlow) -> None:
    if _ROUTE_API:
        _route_request(flow)


def response(flow: http.HTTPFlow) -> None:
    if flow.response is not None:
        replace_in_body(flow.response, _REPLACEMENTS, content_types=("javascript",))
    if _ROUTE_API:
        _route_response(flow)
