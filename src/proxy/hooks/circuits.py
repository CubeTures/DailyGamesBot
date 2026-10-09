"""Keeps Puzzmo on its production backend when served from localhost.

Puzzmo's config treats any host containing "localhost", or any URL with a
port, as staging (`document.location.host.includes(`localhost`)||!!document.
location.port`) and then talks to api-staging.puzzmo.com, which has different
puzzles. This turns that check off in its scripts, and points any staging host
left over at production as a fallback. The production API already allows a
localhost origin over CORS.
"""

from mitmproxy import http

from src.proxy.rewrite import replace_in_body

_REPLACEMENTS = [
    (b"document.location.host.includes(`localhost`)||!!document.location.port", b"!1"),
    *(
        (f"{name}-staging.puzzmo.com".encode(), f"{name}.puzzmo.com".encode())
        for name in ("api", "live", "studio", "thumbnails")
    ),
]


def response(flow: http.HTTPFlow) -> None:
    if flow.response is not None:
        replace_in_body(flow.response, _REPLACEMENTS, content_types=("javascript",))
