"""Cross with Friends plays over a socket.io connection to a separate host,
which only accepts the site's own Origin. Its bundle builds that URL from a
variable (`Qu="downforacross-com.onrender.com",Xu=`https://${Qu}``), so the
plain URL rewrite of route_foreign_hosts() can't catch it. Instead the
socket is pointed at the game's own subdomain, and its `/socket.io/`
requests (polling and the websocket upgrade) are sent on to the real host
as if from the site."""

import re
from typing import cast

from mitmproxy import http

from src.games.registry import GAMES_BY_NAME

_ORIGIN = GAMES_BY_NAME["crosswithfriends"].origin
_SOCKET_HOST = "downforacross-com.onrender.com"
_SOCKET_PATH = "/socket.io/"

# `A="<socket host>",B=`https://${A}``: B is the socket URL.
_SOCKET_URL_RE = re.compile(
    rb'(\w+)="' + re.escape(_SOCKET_HOST.encode()) + rb'",(\w+)=`https://\$\{\1\}`'
)


def request(flow: http.HTTPFlow) -> None:
    if not flow.request.path.startswith(_SOCKET_PATH):
        return
    flow.request.scheme, flow.request.host, flow.request.port = (
        "https",
        _SOCKET_HOST,
        443,
    )
    flow.request.host_header = _SOCKET_HOST
    flow.request.headers["origin"] = _ORIGIN


def response(flow: http.HTTPFlow) -> None:
    if flow.response is None:
        return
    content_type = cast(str, flow.response.headers.get("content-type", ""))
    if "javascript" not in content_type or not flow.response.content:
        return
    content = _SOCKET_URL_RE.sub(
        rb'\1="' + _SOCKET_HOST.encode() + rb'",\2=location.origin',
        flow.response.content,
    )
    if content != flow.response.content:
        flow.response.content = content
