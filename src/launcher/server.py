"""Serves the launcher page, the results API its scoreboard reads, the
subscriptions API its role pickers use, and the admin API that turns games
on and off."""

import json
from collections.abc import Generator
from contextlib import contextmanager
from datetime import date
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from typing import Any, cast
from urllib.parse import parse_qs, urlsplit

from src import announce, results
from src.games.registry import GAMES_BY_NAME
from src.launcher.build import write_launcher
from src.settings import LAUNCHER_DIR, LAUNCHER_PORT

RESULTS_API_PATH = "/api/results"
SUBSCRIPTIONS_API_PATH = "/api/subscriptions"
ADMIN_API_PATH = "/api/admin"
GAMES_API_PATH = "/api/games"


def _parse_day(raw: str | None) -> date | None:
    """A YYYY-MM-DD date, or None if it's missing or invalid."""
    try:
        return date.fromisoformat(raw or "")
    except ValueError:
        return None


def _result_json(result: results.StoredResult) -> dict[str, Any]:
    game = GAMES_BY_NAME.get(result.game)
    return {
        "game": result.game,
        "discord_id": result.discord_id,
        "name": result.player_name,
        "puzzle_id": result.puzzle_id,
        "data": result.data,
        "captured_at": result.captured_at.isoformat(),
        # What the bot posts, so the launcher can show it; None if the game's
        # config is gone. The page has no role IDs, so the game's role mention
        # carries its name instead.
        "announcement": (
            announce.render_result(game, result, game_mention=f"<@&{game.name}>")
            if game
            else None
        ),
    }


def _results_for_query(query: str) -> list[dict[str, Any]]:
    """GET /api/results?day=<YYYY-MM-DD>: that game day's results."""
    # The page sends the viewer's local date; fall back to the server's.
    day = _parse_day(_query_params(query).get("day")) or date.today()
    return [_result_json(r) for r in results.on_day(day)]


def _query_params(query: str) -> dict[str, str]:
    return {key: values[0] for key, values in parse_qs(query).items()}


def _is_discord_id(value: object) -> bool:
    return isinstance(value, str) and value.isascii() and value.isdigit()


def _subscriptions_for_query(query: str) -> dict[str, Any] | None:
    """GET /api/subscriptions?discord_id=<id>: the games whose role they want."""
    discord_id = _query_params(query).get("discord_id")
    if not _is_discord_id(discord_id):
        return None
    return {"games": results.subscribed_games(cast(str, discord_id))}


def _parse_subscription(body: bytes) -> results.Subscription | None:
    """POST /api/subscriptions {"discord_id", "game", "subscribed"}."""
    try:
        payload: Any = json.loads(body)
    except ValueError:
        return None
    if not isinstance(payload, dict):
        return None
    fields = cast(dict[str, Any], payload)
    discord_id, game, subscribed = (
        fields.get("discord_id"),
        fields.get("game"),
        fields.get("subscribed"),
    )
    if (
        not _is_discord_id(discord_id)
        or game not in GAMES_BY_NAME
        or not isinstance(subscribed, bool)
    ):
        return None
    return results.Subscription(cast(str, discord_id), cast(str, game), subscribed)


def _admin_for_query(query: str) -> dict[str, Any] | None:
    """GET /api/admin?discord_id=<id>: whether they may turn games on and off."""
    discord_id = _query_params(query).get("discord_id")
    if not _is_discord_id(discord_id):
        return None
    return {"admin": results.is_admin(cast(str, discord_id))}


def _parse_game_toggle(body: bytes) -> tuple[str, str, bool] | None:
    """POST /api/games {"discord_id", "game", "enabled"}."""
    try:
        payload: Any = json.loads(body)
    except ValueError:
        return None
    if not isinstance(payload, dict):
        return None
    fields = cast(dict[str, Any], payload)
    discord_id, game, enabled = (
        fields.get("discord_id"),
        fields.get("game"),
        fields.get("enabled"),
    )
    if (
        not _is_discord_id(discord_id)
        or game not in GAMES_BY_NAME
        or not isinstance(enabled, bool)
    ):
        return None
    return cast(str, discord_id), cast(str, game), enabled


class _LauncherRequestHandler(SimpleHTTPRequestHandler):
    def do_GET(self) -> None:
        url = urlsplit(self.path)
        if url.path == RESULTS_API_PATH:
            self._send_json(_results_for_query(url.query))
        elif url.path == SUBSCRIPTIONS_API_PATH:
            subscriptions = _subscriptions_for_query(url.query)
            if subscriptions is None:
                self._send_json({"error": "need a discord_id"}, 400)
            else:
                self._send_json(subscriptions)
        elif url.path == ADMIN_API_PATH:
            admin = _admin_for_query(url.query)
            if admin is None:
                self._send_json({"error": "need a discord_id"}, 400)
            else:
                self._send_json(admin)
        else:
            super().do_GET()

    def do_POST(self) -> None:
        path = urlsplit(self.path).path
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length)
        if path == SUBSCRIPTIONS_API_PATH:
            self._post_subscription(body)
        elif path == GAMES_API_PATH:
            self._post_game_toggle(body)
        else:
            self._send_json({"error": "not found"}, 404)

    def _post_subscription(self, body: bytes) -> None:
        sub = _parse_subscription(body)
        if sub is None:
            self._send_json({"error": "need discord_id, game and subscribed"}, 400)
            return
        results.set_subscription(sub)
        self._send_json({"ok": True})

    def _post_game_toggle(self, body: bytes) -> None:
        toggle = _parse_game_toggle(body)
        if toggle is None:
            self._send_json({"error": "need discord_id, game and enabled"}, 400)
            return
        discord_id, game, enabled = toggle
        if not results.is_admin(discord_id):
            self._send_json({"error": "only server admins can do that"}, 403)
            return
        results.set_game_enabled(game, enabled)
        # The page is static, so re-render it with the game shown or hidden.
        write_launcher()
        self._send_json({"ok": True})

    def _send_json(self, body: Any, status: int = 200) -> None:
        encoded = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


@contextmanager
def serve_launcher(port: int = LAUNCHER_PORT) -> Generator[None]:
    """Regenerate the launcher page and serve it in a background thread."""
    write_launcher()
    handler = partial(_LauncherRequestHandler, directory=str(LAUNCHER_DIR))
    server = ThreadingHTTPServer(("0.0.0.0", port), handler)
    Thread(target=server.serve_forever, daemon=True).start()
    try:
        yield
    finally:
        server.shutdown()
