"""Result capture: injects capture.js into game pages and stores what it reports.

For a game whose games/<name>.toml has triggers, every HTML page the game
serves gets a <script src="/__dgb/capture.js"> at the top of <head>. That
script watches for the configured "finished" condition and POSTs the result
to /__dgb/result on the same local origin. Both /__dgb/ paths are answered
here by the proxy and never reach the real game server.

The player is identified by the dgb_discord_id cookie the launcher sets
(cookies are shared across ports on localhost, unlike localStorage).
"""

import json
import re
from pathlib import Path
from typing import Any, cast

from mitmproxy import ctx, http

from src import results
from src.proxy.config import GameConfig, Trigger

PREFIX = "/__dgb/"
SCRIPT_PATH = PREFIX + "capture.js"
RESULT_PATH = PREFIX + "result"
DISCORD_COOKIE = "dgb_discord_id"

_RUNTIME = (Path(__file__).parent / "capture.js").read_text()
_HEAD_RE = re.compile(rb"<head\b[^>]*>", re.IGNORECASE)
_HTML_RE = re.compile(rb"<html\b[^>]*>", re.IGNORECASE)
_SCRIPT_TAG = f'<script src="{SCRIPT_PATH}"></script>'.encode()


def _js_fn(expr: str, vars_: dict[str, str]) -> str:
    # The newlines let an expression end in a // comment.
    decls = "".join(f"var {name} = (\n{e}\n);\n" for name, e in vars_.items())
    return f"function (req, res, event) {{\n{decls}return (\n{expr}\n);\n}}"


def _js_trigger(t: Trigger) -> str:
    fields = ",\n".join(
        f"{json.dumps(k)}: {_js_fn(v, t.vars)}" for k, v in t.fields.items()
    )
    parts = [
        f"name: {json.dumps(t.name)}",
        f"type: {json.dumps(t.type)}",
        f"when: {_js_fn(t.when, t.vars)}",
        f"fields: {{\n{fields}\n}}",
        f"method: {json.dumps(t.method)}",
        f"event: {json.dumps(t.event)}",
        f"target: {json.dumps(t.target)}",
    ]
    if t.url is not None:
        parts.append(f"url: new RegExp({json.dumps(t.url)})")
    return "{\n" + ",\n".join(parts) + "\n}"


def build_script(game: GameConfig) -> str:
    triggers = "[\n" + ",\n".join(_js_trigger(t) for t in game.triggers) + "\n]"
    return _RUNTIME.replace("__DGB_GAME__", json.dumps(game.name)).replace(
        "__DGB_TRIGGERS__", triggers
    )


def strip_discord_cookie(flow: http.HTTPFlow) -> None:
    """Keep our player-ID cookie from leaking to the real game server."""
    cookies = flow.request.cookies
    if DISCORD_COOKIE in cookies:
        del cookies[DISCORD_COOKIE]


def _json_response(status: int, body: dict[str, Any]) -> http.Response:
    return http.Response.make(
        status,
        json.dumps(body),
        {"Content-Type": "application/json", "Cache-Control": "no-store"},
    )


def _handle_result(flow: http.HTTPFlow, game: GameConfig) -> http.Response:
    if flow.request.method != "POST":
        return _json_response(405, {"error": "POST only"})
    discord_id = flow.request.cookies.get(DISCORD_COOKIE)
    if not discord_id:
        ctx.log.warn(f"[capture] {game.name}: result with no {DISCORD_COOKIE} cookie")
        return _json_response(400, {"error": "no discord id; open the /play link"})
    try:
        raw: Any = json.loads(flow.request.get_text() or "")
    except json.JSONDecodeError:
        return _json_response(400, {"error": "body must be JSON"})
    if not isinstance(raw, dict):
        return _json_response(400, {"error": "body must be a JSON object"})
    payload = cast(dict[str, Any], raw)
    fields = payload.get("fields")
    puzzle_id = payload.get("puzzle_id")
    if not isinstance(fields, dict) or not isinstance(puzzle_id, str) or not puzzle_id:
        return _json_response(400, {"error": "need puzzle_id and fields"})

    url = payload.get("url")
    saved = results.save(
        results.Result(
            game=game.name,
            discord_id=discord_id,
            puzzle_id=puzzle_id,
            data=cast(dict[str, Any], fields),
            trigger=str(payload.get("trigger", "")),
            url=url if isinstance(url, str) else None,
        )
    )
    status = "saved" if saved else "duplicate"
    ctx.log.info(f"[capture] {game.name} {puzzle_id} for {discord_id}: {status}")
    return _json_response(200, {"status": status})


def handle_request(flow: http.HTTPFlow, game: GameConfig) -> bool:
    """Answer /__dgb/ requests locally. Returns True if the flow was handled."""
    path = flow.request.path.split("?", 1)[0]
    if not path.startswith(PREFIX):
        return False
    if path == SCRIPT_PATH:
        flow.response = http.Response.make(
            200,
            build_script(game),
            {"Content-Type": "text/javascript", "Cache-Control": "no-store"},
        )
    elif path == RESULT_PATH:
        flow.response = _handle_result(flow, game)
    else:
        flow.response = _json_response(404, {"error": "not found"})
    return True


def inject(flow: http.HTTPFlow, game: GameConfig) -> None:
    """Add the capture script to the top of an HTML page's <head>."""
    response = flow.response
    if not game.triggers or response is None or response.status_code != 200:
        return
    if "text/html" not in response.headers.get("content-type", ""):
        return
    content = response.content
    if not content:
        return
    match = _HEAD_RE.search(content) or _HTML_RE.search(content)
    if match is None:
        return
    end = match.end()
    response.content = content[:end] + _SCRIPT_TAG + content[end:]


if __name__ == "__main__":
    import sys

    from src.proxy.config import GAME_CONFIGS

    by_name = {g.name: g for g in GAME_CONFIGS.values()}
    if len(sys.argv) != 2 or sys.argv[1] not in by_name:
        sys.exit(f"usage: python -m src.proxy.capture <{'|'.join(sorted(by_name))}>")
    print(build_script(by_name[sys.argv[1]]))
