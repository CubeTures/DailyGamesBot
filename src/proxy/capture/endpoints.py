"""Answers the capture script's /__dgb/ requests, which never reach the real
game server.

The player is identified by the dgb_discord_id cookie. Each game is on its
own subdomain, so the launcher's cookies don't reach it: the launcher's game
links go through /__dgb/enter?discord_id=ID&to=PATH, which sets the cookie on
the game's subdomain and redirects to the game.
"""

import json
import logging
import re
from datetime import UTC, date, datetime
from typing import Any, cast
from urllib.parse import parse_qs, urlsplit

from mitmproxy import http

from src.games.models import Game
from src.proxy.capture import ENTER_PATH, PATH_PREFIX, RESULT_PATH, SCRIPT_PATH
from src.proxy.capture.script import build_script
from src.store import results

DISCORD_ID_COOKIE = "dgb_discord_id"
_COOKIE_MAX_AGE_SECS = 365 * 24 * 60 * 60
# Discord IDs are digits; tests use IDs like "dgb-test".
_COOKIE_VALUE_RE = re.compile(r"[\w-]+", re.ASCII)

_NO_STORE = {"Cache-Control": "no-store"}

log = logging.getLogger(__name__)


def is_capture_path(path: str) -> bool:
    return path.startswith(PATH_PREFIX)


def strip_discord_id_cookie(request: http.Request) -> None:
    """Keep the player's ID from leaking to the real game server."""
    cookies = request.cookies
    if DISCORD_ID_COOKIE in cookies:
        del cookies[DISCORD_ID_COOKIE]


def handle_capture_request(flow: http.HTTPFlow, game: Game) -> bool:
    """Answer /__dgb/ requests locally. Returns True if the flow was handled."""
    path = flow.request.path.split("?", 1)[0]
    if not is_capture_path(path):
        return False
    if path == SCRIPT_PATH:
        flow.response = http.Response.make(
            200, build_script(game), {"Content-Type": "text/javascript", **_NO_STORE}
        )
    elif path == RESULT_PATH:
        flow.response = _save_result(flow.request, game)
    elif path == ENTER_PATH:
        flow.response = _enter(flow.request, game)
    else:
        flow.response = _error(404, "not found")
    return True


def _enter(request: http.Request, game: Game) -> http.Response:
    """Remember the player on this game's subdomain, then go to the game."""
    params = {k: v[0] for k, v in parse_qs(urlsplit(request.path).query).items()}
    to = params.get("to", "")
    # Only a path on this game, not another site.
    if not to.startswith("/") or to.startswith("//") or "\\" in to:
        to = game.landing_path
    headers = {"Location": to, **_NO_STORE}
    discord_id = params.get("discord_id", "")
    if _COOKIE_VALUE_RE.fullmatch(discord_id):
        headers["Set-Cookie"] = (
            f"{DISCORD_ID_COOKIE}={discord_id}; Path=/;"
            f" Max-Age={_COOKIE_MAX_AGE_SECS}; SameSite=Lax"
        )
    return http.Response.make(302, b"", headers)


def _save_result(request: http.Request, game: Game) -> http.Response:
    if request.method != "POST":
        return _error(405, "POST only")
    result = _parse_result(request, game)
    if isinstance(result, str):
        return _error(400, result)
    status = "saved" if results.save(result) else "duplicate"
    log.info(
        "%s %s (%s) for %s: %s",
        game.name,
        result.puzzle_id,
        result.game_day,
        result.discord_id,
        status,
    )
    return _json_response(200, {"status": status})


def _parse_result(request: http.Request, game: Game) -> results.NewResult | str:
    """The result a POST reports, or why it can't be saved."""
    discord_id = request.cookies.get(DISCORD_ID_COOKIE)
    if not discord_id:
        log.warning("%s: result with no %s cookie", game.name, DISCORD_ID_COOKIE)
        return "no discord id; open the /play link"
    try:
        body: Any = json.loads(request.get_text() or "")
    except json.JSONDecodeError:
        return "body must be JSON"
    if not isinstance(body, dict):
        return "body must be a JSON object"
    payload = cast(dict[str, Any], body)
    fields = payload.get("fields")
    puzzle_id = payload.get("puzzle_id")
    if not isinstance(fields, dict) or not isinstance(puzzle_id, str) or not puzzle_id:
        return "need puzzle_id and fields"
    url = payload.get("url")
    return results.NewResult(
        game=game.name,
        discord_id=discord_id,
        puzzle_id=puzzle_id,
        game_day=_game_day(payload.get("game_day"), game),
        data=cast(dict[str, Any], fields),
        trigger=str(payload.get("trigger", "")),
        url=url if isinstance(url, str) else None,
    )


def _game_day(raw: object, game: Game) -> date:
    """The game day the page reported, or else today's by the game's reset
    (in the server's timezone for "local" games)."""
    if isinstance(raw, str):
        try:
            return date.fromisoformat(raw)
        except ValueError:
            pass
    return game.reset.day_at(datetime.now(UTC))


def _json_response(status: int, body: dict[str, Any]) -> http.Response:
    return http.Response.make(
        status, json.dumps(body), {"Content-Type": "application/json", **_NO_STORE}
    )


def _error(status: int, message: str) -> http.Response:
    return _json_response(status, {"error": message})
