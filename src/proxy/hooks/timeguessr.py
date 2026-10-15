"""TimeGuessr's map is Apple MapKit JS, whose token only works from timeguessr.com.

MapKit's bootstrap call, which trades the token for an access key, is refused
unless its Origin is the one in the token. So that call goes through the
proxy, which sends the real origin on. The rest of MapKit (its scripts, tiles)
doesn't check and loads straight from Apple.

The game loads `https://cdn.apple-mapkit.com/mk/<version>/mapkit.core.js`,
which the router serves through the proxy. In it, the bootstrap URL is
`${C}${o.A.cdnBase}/ma/bootstrap`, with `C="https:"` and
`cdnBase:"//cdn.apple-mapkit.com"`; it's pointed at the router instead.
"""

import re

from mitmproxy import http

from src.games.registry import GAMES_BY_NAME
from src.proxy.hooks import route_foreign_hosts
from src.proxy.rewrite import ForeignHostRouter

_MAPKIT_HOST = "cdn.apple-mapkit.com"
_BOOTSTRAP_RE = re.compile(rb"`\$\{[\w$]+\}\$\{[\w$.]+\.cdnBase\}/ma/bootstrap`")
_LOCAL_BOOTSTRAP = (
    f'"{GAMES_BY_NAME["timeguessr"].local_origin}'
    f'{ForeignHostRouter.PREFIX}{_MAPKIT_HOST}/ma/bootstrap"'
).encode()

request, _route_response = route_foreign_hosts("timeguessr", [_MAPKIT_HOST])


def response(flow: http.HTTPFlow) -> None:
    _route_response(flow)
    if flow.response is None or not flow.request.path.endswith("/mapkit.core.js"):
        return
    content = flow.response.content
    if content:
        flow.response.content = _BOOTSTRAP_RE.sub(_LOCAL_BOOTSTRAP, content)
