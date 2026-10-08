"""Builds a game's capture script and injects it into the game's pages."""

import json
import re
from pathlib import Path

from mitmproxy import http

from src.games.models import (
    FIELDS_EXPORT_RE,
    LOCAL_TIMEZONE,
    EventTrigger,
    Game,
    NetworkTrigger,
    Trigger,
)

SCRIPT_PATH = "/__dgb/capture.js"

_RUNTIME = (Path(__file__).parent / "runtime.js").read_text()
_HEAD_TAG_RE = re.compile(rb"<head\b[^>]*>", re.IGNORECASE)
_HTML_TAG_RE = re.compile(rb"<html\b[^>]*>", re.IGNORECASE)
_SCRIPT_TAG = f'<script src="{SCRIPT_PATH}"></script>'.encode()


def _js_function(vars_js: str, body: str) -> str:
    # vars.js runs first in each, so `when` and the fields can use its names.
    return f"function (req, res, event) {{\n{vars_js}\n{body}\n}}"


def _js_trigger(trigger: Trigger, game: Game) -> str:
    # The newlines let `when` end in a // comment.
    when = f"return (\n{trigger.when}\n);"
    fields = FIELDS_EXPORT_RE.sub("return ", game.fields_js, count=1)
    properties = {
        "name": json.dumps(trigger.name),
        "type": json.dumps(trigger.type),
        "when": _js_function(game.vars_js, when),
        "fields": _js_function(game.vars_js, fields),
    }
    if isinstance(trigger, NetworkTrigger):
        properties["method"] = json.dumps(trigger.method)
        properties["url"] = f"new RegExp({json.dumps(trigger.url)})"
    elif isinstance(trigger, EventTrigger):
        properties["event"] = json.dumps(trigger.event)
        properties["target"] = json.dumps(trigger.target)
    return "{\n" + ",\n".join(f"{k}: {v}" for k, v in properties.items()) + "\n}"


def build_script(game: Game) -> str:
    triggers = ",\n".join(_js_trigger(t, game) for t in game.triggers)
    reset = {
        "minutes": game.reset.minutes,
        "timezone": None
        if game.reset.timezone == LOCAL_TIMEZONE
        else game.reset.timezone,
    }
    return (
        _RUNTIME.replace("__DGB_GAME__", json.dumps(game.name))
        .replace("__DGB_RESET__", json.dumps(reset))
        .replace("__DGB_TRIGGERS__", f"[\n{triggers}\n]")
    )


def inject_script_tag(response: http.Response, game: Game) -> None:
    """Add the capture script to the top of an HTML page's <head>, so it can
    wrap fetch/XHR before the game's own scripts use them."""
    if not game.triggers or response.status_code != 200:
        return
    if "text/html" not in response.headers.get("content-type", ""):
        return
    content = response.content
    if not content:
        return
    tag = _HEAD_TAG_RE.search(content) or _HTML_TAG_RE.search(content)
    if tag is None:
        return
    response.content = content[: tag.end()] + _SCRIPT_TAG + content[tag.end() :]
