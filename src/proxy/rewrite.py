"""Response rewrites that let a game work from a plain-HTTP localhost origin."""

import re
from typing import cast

from mitmproxy import http

_FRAMING_AND_TRANSPORT_HEADERS = (
    "x-frame-options",
    "content-security-policy",
    "strict-transport-security",
)
_COOKIE_DOMAIN_RE = re.compile(rb";\s*Domain=[^;]*", re.IGNORECASE)
_COOKIE_SECURE_RE = re.compile(rb";\s*Secure", re.IGNORECASE)
_SECURE_PREFIXES = (b"__Secure-", b"__Host-")
_TEXT_CONTENT_TYPES = ("html", "javascript", "json", "css", "text/")


def replace_in_body(
    response: http.Response,
    replacements: list[tuple[bytes, bytes]],
    content_types: tuple[str, ...] = _TEXT_CONTENT_TYPES,
) -> None:
    """Apply byte replacements to a response whose Content-Type contains one
    of `content_types`."""
    content_type = cast(str, response.headers.get("content-type", ""))
    if not any(t in content_type for t in content_types):
        return
    original = content = response.content
    if not content:
        return
    for old, new in replacements:
        content = content.replace(old, new)
    if content != original:
        response.content = content


def drop_cache_validators(request: http.Request) -> None:
    """Force a full response instead of a bodyless 304: the client's cache
    validators were earned against whatever it last loaded through this
    proxy, and a 304 can leave the page with no body to render."""
    request.headers.pop("if-none-match", None)
    request.headers.pop("if-modified-since", None)


def strip_blocking_headers(response: http.Response) -> None:
    for header in _FRAMING_AND_TRANSPORT_HEADERS:
        response.headers.pop(header, None)


def localize_cookies(response: http.Response) -> None:
    """Bind Set-Cookie to localhost instead of the real domain, and let it
    work over plain HTTP."""
    set_cookies = response.headers.get_all("set-cookie")
    if not set_cookies:
        return
    localized: list[str] = []
    for cookie in set_cookies:
        raw = cookie.encode("latin-1")
        raw = _COOKIE_DOMAIN_RE.sub(b"", raw)
        # Browsers reject __Secure-/__Host- cookies without Secure, but do
        # accept Secure cookies from http://localhost, so those keep it.
        if not raw.lstrip().startswith(_SECURE_PREFIXES):
            raw = _COOKIE_SECURE_RE.sub(b"", raw)
        localized.append(raw.decode("latin-1"))
    response.headers.set_all("set-cookie", localized)


class OriginRewriter:
    """Points absolute URLs to the real origin at the local proxy instead.

    Pages and scripts often hardcode them (data endpoints, fonts, manifests),
    and those requests would bypass the proxy and be blocked by CORS from a
    localhost origin.
    """

    def __init__(self, real_origin: str, local_origin: str) -> None:
        real, local = real_origin.encode(), local_origin.encode()
        # Also the escaped-slash forms in embedded JSON, e.g.
        # "https:\/\/www.nytimes.com" or "https://www.nytimes.com".
        self._replacements = [
            (real.replace(b"://", sep), local.replace(b"://", sep))
            for sep in (b"://", b":\\/\\/", b":\\u002F\\u002F")
        ]

    def apply(self, response: http.Response) -> None:
        self._rewrite_redirect(response)
        replace_in_body(response, self._replacements)

    def _rewrite_redirect(self, response: http.Response) -> None:
        """Keep redirects to the real origin (e.g. an old path moved) from
        taking the player off the proxy."""
        location = cast(str | None, response.headers.get("location"))
        if location is None:
            return
        real, local = (r.decode() for r in self._replacements[0])
        if location == real or location.startswith((real + "/", real + "?")):
            response.headers["location"] = local + location.removeprefix(real)


class ForeignHostRouter:
    """Serves other hosts a game's JS fetches from under the game's own port.

    A game whose JS fetches an absolute URL on a separate API/CDN host is
    blocked by CORS from localhost. This rewrites those URLs in text responses
    to `<local origin>/__host/<host>/...`, and `route` sends requests for that
    prefix on to the real host. Games use it through
    `src.proxy.hooks.route_foreign_hosts`.
    """

    PREFIX = "/__host/"

    def __init__(self, game_origin: str, local_origin: str, hosts: list[str]) -> None:
        self._game_origin = game_origin
        self._hosts = set(hosts)
        self._rewriters = [
            OriginRewriter(f"https://{host}", f"{local_origin}{self.PREFIX}{host}")
            for host in hosts
        ]

    def route(self, request: http.Request) -> None:
        if not request.path.startswith(self.PREFIX):
            return
        host, _, path = request.path.removeprefix(self.PREFIX).partition("/")
        if host not in self._hosts:
            return
        request.scheme, request.host, request.port = "https", host, 443
        request.path = "/" + path
        request.headers["host"] = host
        # The real hosts only allow the game's own origin.
        if "origin" in request.headers:
            request.headers["origin"] = self._game_origin
        if "referer" in request.headers:
            request.headers["referer"] = self._game_origin + "/"

    def apply(self, response: http.Response) -> None:
        for rewriter in self._rewriters:
            rewriter.apply(response)
