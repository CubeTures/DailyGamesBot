"""Serves the launcher page and the results API its scoreboard reads."""

import json
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from typing import Any
from urllib.parse import parse_qs, urlsplit

from src import announce, results
from src.games.registry import GAMES_BY_NAME
from src.launcher.build import write_launcher
from src.settings import LAUNCHER_DIR, LAUNCHER_PORT

RESULTS_API_PATH = "/api/results"


def _parse_aware_time(raw: str | None) -> datetime | None:
    """An ISO time with a timezone, or None if it's missing or invalid."""
    try:
        parsed = datetime.fromisoformat(raw or "")
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


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
        # config is gone.
        "announcement": announce.render_result(game, result) if game else None,
    }


def _results_for_query(query: str) -> list[dict[str, Any]]:
    """GET /api/results?since=<ISO time>[&until=<ISO time>]."""
    params = {key: values[0] for key, values in parse_qs(query).items()}
    # The page sends the viewer's local midnight(s); fall back to 24h.
    since = _parse_aware_time(params.get("since")) or (
        datetime.now(UTC) - timedelta(days=1)
    )
    until = _parse_aware_time(params.get("until"))
    return [_result_json(r) for r in results.captured_between(since, until)]


class _LauncherRequestHandler(SimpleHTTPRequestHandler):
    def do_GET(self) -> None:
        url = urlsplit(self.path)
        if url.path == RESULTS_API_PATH:
            self._send_json(_results_for_query(url.query))
        else:
            super().do_GET()

    def _send_json(self, body: Any) -> None:
        encoded = json.dumps(body).encode()
        self.send_response(200)
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
