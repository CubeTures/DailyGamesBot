import json
import socket
import urllib.error
import urllib.request
from collections.abc import Generator
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from src.launcher import build, server
from src.store import hidden_games, players, results


@pytest.fixture
def launcher(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[str]:
    """The launcher on a free port, writing its page under `tmp_path`."""
    monkeypatch.setattr(build, "OUTPUT_PATH", tmp_path / "index.html")
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    with server.serve_launcher(port):
        yield f"http://127.0.0.1:{port}"


def _get(url: str) -> tuple[int, Any]:
    try:
        with urllib.request.urlopen(url) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as e:
        return e.code, json.load(e)


def _post(url: str, body: object) -> tuple[int, Any]:
    request = urllib.request.Request(
        url, json.dumps(body).encode(), {"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(request) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as e:
        return e.code, json.load(e)


def test_results_api(launcher: str) -> None:
    results.save(
        results.NewResult(
            game="wordle",
            discord_id="7",
            puzzle_id="p",
            game_day=date(2026, 10, 8),
            data={"won": True},
            trigger="t",
        )
    )
    token = players.token_for("8")
    status, body = _get(f"{launcher}/api/results?day=2026-10-08&token={token}")
    assert status == 200
    [row] = body
    assert row["game"] == "wordle"
    assert row["discord_id"] == "7"
    assert row["announcement"].startswith(":bee:")
    assert _get(f"{launcher}/api/results?day=2026-10-09&token={token}") == (200, [])
    assert _get(f"{launcher}/api/results?day=2026-10-08")[0] == 401
    assert _get(f"{launcher}/api/results?day=2026-10-08&token=x")[0] == 401


def test_me_api(launcher: str) -> None:
    old = players.token_for("7")
    players.reset_token("7")
    token = players.token_for("7")
    assert _get(f"{launcher}/api/me?token={token}") == (200, {"discord_id": "7"})
    assert _get(f"{launcher}/api/me?token={old}")[0] == 401
    assert _get(f"{launcher}/api/me")[0] == 401


def test_subscriptions_api(launcher: str) -> None:
    token = players.token_for("7")
    assert _get(f"{launcher}/api/subscriptions?token=x")[0] == 401
    assert _post(f"{launcher}/api/subscriptions", {"token": token})[0] == 400
    sub = {"token": token, "game": "wordle", "subscribed": True}
    assert _post(f"{launcher}/api/subscriptions", {**sub, "subscribed": 1})[0] == 400
    assert _post(f"{launcher}/api/subscriptions", {**sub, "token": "x"})[0] == 401
    assert _post(f"{launcher}/api/subscriptions", sub) == (200, {"ok": True})
    assert _get(f"{launcher}/api/subscriptions?token={token}") == (
        200,
        {"games": ["wordle"]},
    )


def test_hidden_api(launcher: str) -> None:
    token = players.token_for("7")
    hide = {"token": token, "game": "wordle", "level": "all"}
    assert _get(f"{launcher}/api/hidden?token={token}") == (200, {"games": {}})
    assert _post(f"{launcher}/api/hidden", {**hide, "game": "nope"})[0] == 400
    assert _post(f"{launcher}/api/hidden", {**hide, "level": "some"})[0] == 400
    assert _post(f"{launcher}/api/hidden", {**hide, "token": "x"})[0] == 401
    assert _post(f"{launcher}/api/hidden", hide) == (200, {"ok": True})
    assert hidden_games.levels("7") == {"wordle": "all"}
    assert _get(f"{launcher}/api/hidden?token={token}") == (
        200,
        {"games": {"wordle": "all"}},
    )
    assert hidden_games.levels("8") == {}


def test_unknown_post_is_404(launcher: str) -> None:
    assert _post(f"{launcher}/api/nope", {})[0] == 404


def _get_page(url: str, cookie: str | None = None) -> tuple[int, str, str | None]:
    """Status, body and Set-Cookie of a page."""
    request = urllib.request.Request(url, headers={"Cookie": cookie} if cookie else {})
    try:
        with urllib.request.urlopen(request) as response:
            return (
                response.status,
                response.read().decode(),
                response.headers["Set-Cookie"],
            )
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(), e.headers["Set-Cookie"]


def test_serves_the_page_for_a_token_from_the_link(launcher: str) -> None:
    token = players.token_for("7")
    status, page, cookie = _get_page(f"{launcher}/?token={token}")
    assert status == 200
    assert "function gameDay(reset)" in page
    assert 'data-game="wordle"' in page
    assert f'<meta name="dgb-token" content="{token}">' in page
    assert cookie is not None and cookie.startswith(f"dgb_token={token};")
    assert "HttpOnly" in cookie


def test_serves_the_page_for_a_token_from_the_cookie(launcher: str) -> None:
    token = players.token_for("7")
    status, page, cookie = _get_page(f"{launcher}/", f"dgb_token={token}")
    assert status == 200
    assert 'data-game="wordle"' in page
    assert cookie is None


def test_withholds_the_page_without_a_token(launcher: str) -> None:
    status, page, cookie = _get_page(f"{launcher}/")
    assert status == 401
    assert "Get your link first" in page
    assert "data-game=" not in page
    assert cookie is None
    assert _get_page(f"{launcher}/index.html")[0] == 401
    assert _get(f"{launcher}/locked.html")[0] == 404


def test_withholds_the_page_for_a_reset_token(launcher: str) -> None:
    old = players.token_for("7")
    players.reset_token("7")
    status, page, _ = _get_page(f"{launcher}/?token={old}")
    assert status == 401
    assert "Your link has expired" in page
    assert "data-game=" not in page
    status, page, cookie = _get_page(f"{launcher}/", f"dgb_token={old}")
    assert status == 401
    assert "Your link has expired" in page
    assert cookie is not None and "Max-Age=0" in cookie
