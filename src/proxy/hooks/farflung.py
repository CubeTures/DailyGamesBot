"""Farflung's API refuses writes (e.g. saving a finished expedition) unless
their Origin is the site's own: `{"error":"forbidden","detail":"A write needs
the site's Origin."}`. The page is on the game's local subdomain, so its
Origin is sent on as farflung.game's."""

from mitmproxy import http

from src.games.registry import GAMES_BY_NAME

_ORIGIN = GAMES_BY_NAME["farflung"].origin


def request(flow: http.HTTPFlow) -> None:
    if "origin" in flow.request.headers:
        flow.request.headers["origin"] = _ORIGIN
