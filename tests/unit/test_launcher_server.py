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
    monkeypatch.setattr(server, "LAUNCHER_DIR", tmp_path)
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
    status, body = _get(f"{launcher}/api/results?day=2026-10-08")
    assert status == 200
    [row] = body
    assert row["game"] == "wordle"
    assert row["discord_id"] == "7"
    assert row["announcement"].startswith(":bee:")
    assert _get(f"{launcher}/api/results?day=2026-10-09") == (200, [])


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


def test_serves_the_page(launcher: str) -> None:
    with urllib.request.urlopen(f"{launcher}/") as response:
        page = response.read().decode()
    assert "function gameDay(reset)" in page
    assert 'data-game="wordle"' in page
