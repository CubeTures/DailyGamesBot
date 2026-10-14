import json
import shutil
import subprocess
from typing import cast

import pytest
from mitmproxy import http
from mitmproxy.test import tflow, tutils

from src.games.models import Game
from src.games.registry import GAMES_BY_NAME
from src.proxy.capture.endpoints import handle_capture_request
from src.proxy.capture.script import build_script, inject_script_tag
from src.store import players, results

WORDLE = GAMES_BY_NAME["wordle"]
CAPTURED_GAMES = [g for g in GAMES_BY_NAME.values() if g.triggers]


def _post(game: Game, body: object, token: str | None = "") -> http.HTTPFlow:
    """POST a result, by default as player 42 with their current token."""
    if token == "":
        token = players.token_for("42")
    flow = tflow.tflow()
    flow.request.method = "POST"
    flow.request.path = "/__dgb/result"
    flow.request.text = json.dumps(body)
    if token:
        flow.request.headers["cookie"] = f"dgb_token={token}"
    assert handle_capture_request(flow, game)
    assert flow.response is not None
    return flow


def test_saves_result_once() -> None:
    body = {
        "puzzle_id": "2026-10-08",
        "game_day": "2026-10-08",
        "fields": {"won": True},
        "trigger": "local-state",
    }
    first = _post(WORDLE, body)
    assert first.response and first.response.json() == {"status": "saved"}
    second = _post(WORDLE, body)
    assert second.response and second.response.json() == {"status": "duplicate"}
    [saved] = results.unannounced()
    assert (saved.discord_id, saved.puzzle_id, saved.data) == (
        "42",
        "2026-10-08",
        {"won": True},
    )


def test_rejects_reset_tokens() -> None:
    old = players.token_for("42")
    players.reset_token("42")
    flow = _post(WORDLE, {"puzzle_id": "1", "fields": {}}, old)
    assert flow.response and flow.response.status_code == 400
    assert results.unannounced() == []


@pytest.mark.parametrize(
    ("body", "token"),
    [
        ({"puzzle_id": "1", "fields": {}}, None),
        ({"puzzle_id": "1", "fields": {}}, "never-issued"),
        ([], ""),
        ({"puzzle_id": "", "fields": {}}, ""),
        ({"puzzle_id": "1", "fields": []}, ""),
    ],
)
def test_rejects_bad_results(body: object, token: str | None) -> None:
    flow = _post(WORDLE, body, token)
    assert flow.response and flow.response.status_code == 400
    assert results.unannounced() == []


def test_serves_script_and_404s_unknown_paths() -> None:
    flow = tflow.tflow()
    flow.request.path = "/__dgb/capture.js?v=1"
    assert handle_capture_request(flow, WORDLE)
    assert flow.response and b'"wordle"' in flow.response.content  # type: ignore[operator]

    flow = tflow.tflow()
    flow.request.path = "/__dgb/nope"
    assert handle_capture_request(flow, WORDLE)
    assert flow.response and flow.response.status_code == 404

    flow = tflow.tflow()
    flow.request.path = "/index.html"
    assert not handle_capture_request(flow, WORDLE)


def _enter(query: str) -> http.Response:
    flow = tflow.tflow()
    flow.request.path = "/__dgb/enter" + query
    assert handle_capture_request(flow, WORDLE)
    assert flow.response is not None
    return flow.response


@pytest.mark.parametrize(
    ("to", "location"),
    [
        ("/games/wordle/index.html", "/games/wordle/index.html"),
        ("/x", "/x"),
        ("//evil.com", "/games/wordle/index.html"),
        ("https://evil.com", "/games/wordle/index.html"),
    ],
)
def test_enter_sets_cookie_and_redirects_within_game(to: str, location: str) -> None:
    token = players.token_for("42")
    response = _enter(f"?token={token}&to={to}")
    assert response.status_code == 302
    assert response.headers["location"] == location
    set_cookie = cast(str, response.headers["set-cookie"])
    assert set_cookie.startswith(f"dgb_token={token}; Path=/; HttpOnly;")


def test_enter_404s_without_a_working_token() -> None:
    old = players.token_for("7")
    players.reset_token("7")
    for query in ("?to=/x", "?token=x&to=/x", "?token=4;2&to=/x", f"?token={old}"):
        response = _enter(query)
        assert response.status_code == 404
        assert "set-cookie" not in response.headers


def test_injects_script_tag_into_head() -> None:
    response = tutils.tresp(content=b"<html><head lang=en><title>x</title></head>")
    response.headers["content-type"] = "text/html; charset=utf-8"
    inject_script_tag(response, WORDLE)
    assert response.content == (
        b'<html><head lang=en><script src="/__dgb/capture.js"></script>'
        b"<title>x</title></head>"
    )


@pytest.mark.skipif(shutil.which("node") is None, reason="needs node")
@pytest.mark.parametrize("game", CAPTURED_GAMES, ids=lambda g: g.name)
def test_built_script_is_valid_js(game: Game) -> None:
    subprocess.run(
        ["node", "--check", "--input-type=commonjs"],
        input=build_script(game),
        text=True,
        check=True,
    )
