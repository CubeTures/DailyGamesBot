"""Keeps chess.com's API calls on the game's own origin.

Chess.com's scripts derive their API host from the page's: the first label
becomes `api` (www.chess.com is served API calls from api.chess.com), unless
the page is on a bare `localhost`, where they stay on the page's origin. From
chess.localhost:8080 that gives api.localhost:8080, which isn't the game. This
turns both checks into "stay on the page's origin", whatever the host, and the
proxy passes those calls on to www.chess.com, which serves them too.
"""

import re
import string
from typing import cast

from mitmproxy import http

# The regexes start at a literal and the operand before it is found by
# walking back: with it in the pattern, they took seconds over chess.com's
# scripts, holding up every other request.
_IDENTIFIER_CHARS = frozenset((string.ascii_letters + string.digits + "_$").encode())
_MEMBER_CHAIN_CHARS = _IDENTIFIER_CHARS | {ord(".")}

# `function vMe(e){...;let[n,...r]=t;return n===`api`||n.startsWith(`api-`)?e:...`:
# the API host for hostname `e`. Its own hostname if it starts with api.
_API_HOST_CHECK_RE = re.compile(rb"===`api`\|\|([\w$]+)\.startsWith\(`api-`\)\?")
# `if(n.hostname===`localhost`)t=t.replace(e.origin,n.origin);else{...}`: route
# URLs on another origin are moved to the page's when it's on localhost. All
# such checks were true when games were served from a bare localhost.
_LOCALHOST_CHECK_RE = re.compile(rb"\.hostname===`localhost`")


def response(flow: http.HTTPFlow) -> None:
    response = flow.response
    if response is None:
        return
    if "javascript" not in cast(str, response.headers.get("content-type", "")):
        return
    content = response.content
    if not content:
        return
    patched = _replace_checks(content, _API_HOST_CHECK_RE, _IDENTIFIER_CHARS, b"!0?")
    patched = _replace_checks(patched, _LOCALHOST_CHECK_RE, _MEMBER_CHAIN_CHARS, b"!0")
    if patched != content:
        response.content = patched


def _replace_checks(
    content: bytes, check: re.Pattern[bytes], operand_chars: frozenset[int], new: bytes
) -> bytes:
    """Replace each `check` match, with the operand just before it, by `new`.
    If `check` has a group, the operand must equal it."""
    parts: list[bytes] = []
    last = 0
    for match in check.finditer(content):
        start = match.start()
        while start > last and content[start - 1] in operand_chars:
            start -= 1
        operand = content[start : match.start()]
        if not operand or (check.groups and operand != match.group(1)):
            continue
        parts += [content[last:start], new]
        last = match.end()
    if not parts:
        return content
    parts.append(content[last:])
    return b"".join(parts)
