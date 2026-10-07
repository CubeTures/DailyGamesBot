"""Starts the launcher page server and the mitmproxy reverse proxy."""

import asyncio
import json
import os
import signal
from datetime import UTC, datetime, timedelta
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from urllib.parse import parse_qs, urlsplit

from src import results
from src.proxy import gen_launcher
from src.proxy.config import GAMES, LAUNCHER_PORT, REPO_ROOT

ADDON_PATH = REPO_ROOT / "src" / "proxy" / "addon.py"


class LauncherHandler(SimpleHTTPRequestHandler):
    """Static launcher files, plus GET /api/results?since=<ISO time>."""

    def do_GET(self) -> None:
        url = urlsplit(self.path)
        if url.path != "/api/results":
            super().do_GET()
            return
        raw_since = parse_qs(url.query).get("since", [""])[0]
        try:
            since = datetime.fromisoformat(raw_since)
            if since.tzinfo is None:
                raise ValueError("since needs a timezone")
        except ValueError:
            # The page sends the viewer's local midnight; fall back to 24h.
            since = datetime.now(UTC) - timedelta(days=1)
        body = json.dumps(results.results_since(since)).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def start_launcher_server() -> ThreadingHTTPServer:
    gen_launcher.write()
    handler = partial(
        LauncherHandler,
        directory=str(REPO_ROOT / "launcher"),
    )
    server = ThreadingHTTPServer(("0.0.0.0", LAUNCHER_PORT), handler)
    Thread(target=server.serve_forever, daemon=True).start()
    return server


async def run_mitmproxy() -> None:
    mode_args: list[str] = []
    for port, (_name, origin) in sorted(GAMES.items()):
        mode_args += ["--mode", f"reverse:{origin}@{port}"]

    repo_root = str(REPO_ROOT)
    env = dict(os.environ)
    env["PYTHONPATH"] = (
        f"{repo_root}{os.pathsep}{env['PYTHONPATH']}"
        if env.get("PYTHONPATH")
        else repo_root
    )
    proc = await asyncio.create_subprocess_exec(
        "mitmdump", "-s", str(ADDON_PATH), *mode_args, env=env
    )
    # Without this, `kill <pid>` on us would orphan mitmdump on the ports.
    asyncio.get_running_loop().add_signal_handler(signal.SIGTERM, proc.terminate)
    try:
        code = await proc.wait()
    except asyncio.CancelledError:
        proc.terminate()
        await proc.wait()
        raise
    raise SystemExit(f"mitmdump exited with code {code}")
