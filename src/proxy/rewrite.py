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
_TEXT_CONTENT_TYPES = ("html", "javascript", "json", "css", "text/")


def drop_cache_validators(request: http.Request) -> None:
    # Force a full response instead of a bodyless 304: the client's cache
    # validators were earned against whatever it loaded last through this
    # proxy, and a 304 here can leave the page with no body to render.
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
        content_type = cast(str, response.headers.get("content-type", ""))
        if not any(t in content_type for t in _TEXT_CONTENT_TYPES):
            return
        original = content = response.content
        if not content:
            return
        for real, local in self._replacements:
            content = content.replace(real, local)
        if content != original:
            response.content = content
