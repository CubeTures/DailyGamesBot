"""Keeps Puzzmo on its production backend when served from localhost.

Puzzmo's config treats any host containing "localhost", or any URL with a
port, as staging (`document.location.host.includes(`localhost`)||!!document.
location.port`) and then talks to api-staging.puzzmo.com, which has different
puzzles. This turns that check off in its scripts, and points any staging host
left over at production as a fallback. The production API already allows a
localhost origin over CORS.
"""

from typing import cast

from mitmproxy import http

_LOCAL_CHECK = b"document.location.host.includes(`localhost`)||!!document.location.port"
_STAGING_HOSTS = [
    (f"{name}-staging.puzzmo.com".encode(), f"{name}.puzzmo.com".encode())
    for name in ("api", "live", "studio", "thumbnails")
]


def response(flow: http.HTTPFlow) -> None:
    response = flow.response
    if response is None:
        return
    if "javascript" not in cast(str, response.headers.get("content-type", "")):
        return
    original = content = response.content
    if not content:
        return
    content = content.replace(_LOCAL_CHECK, b"!1")
    for staging, production in _STAGING_HOSTS:
        content = content.replace(staging, production)
    if content != original:
        response.content = content
