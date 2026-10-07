"""Answers the capture script's /__dgb/ requests, which never reach the real
game server.

The player is identified by the dgb_discord_id cookie the launcher sets:
cookies are shared across ports on localhost, unlike localStorage.
"""

import json
from typing import Any, cast

from mitmproxy import ctx, http

from src import results
from src.games.models import Game
from src.proxy.capture.script import SCRIPT_PATH, build_script

PREFIX = "/__dgb/"
RESULT_PATH = PREFIX + "result"
DISCORD_ID_COOKIE = "dgb_discord_id"

_NO_STORE = {"Cache-Control": "no-store"}


def is_capture_path(path: str) -> bool:
    return path.startswith(PREFIX)


def strip_discord_id_cookie(request: http.Request) -> None:
    """Keep the player's ID from leaking to the real game server."""
    cookies = request.cookies
    if DISCORD_ID_COOKIE in cookies:
        del cookies[DISCORD_ID_COOKIE]


def _json_response(status: int, body: dict[str, Any]) -> http.Response:
    return http.Response.make(
        status, json.dumps(body), {"Content-Type": "application/json", **_NO_STORE}
    )


def _error(status: int, message: str) -> http.Response:
    return _json_response(status, {"error": message})


def _parse_result(request: http.Request, game: Game) -> results.NewResult | str:
    """The result a POST reports, or why it can't be saved."""
    discord_id = request.cookies.get(DISCORD_ID_COOKIE)
    if not discord_id:
        ctx.log.warn(
            f"[capture] {game.name}: result with no {DISCORD_ID_COOKIE} cookie"
        )
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
        data=cast(dict[str, Any], fields),
        trigger=str(payload.get("trigger", "")),
        url=url if isinstance(url, str) else None,
    )


def _save_result(request: http.Request, game: Game) -> http.Response:
    if request.method != "POST":
        return _error(405, "POST only")
    result = _parse_result(request, game)
    if isinstance(result, str):
        return _error(400, result)
    status = "saved" if results.save(result) else "duplicate"
    ctx.log.info(
        f"[capture] {game.name} {result.puzzle_id} for {result.discord_id}: {status}"
    )
    return _json_response(200, {"status": status})


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
    else:
        flow.response = _error(404, "not found")
    return True
