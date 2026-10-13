"""Paths, ports and environment settings shared by the proxy, the launcher
and the Discord bot. Environment variables may also come from .env."""

import logging
import os
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
GAMES_DIR = REPO_ROOT / "games"
LAUNCHER_DIR = REPO_ROOT / "launcher"

load_dotenv(REPO_ROOT / ".env")

# Where players reach the launcher. Each game is served from its own subdomain
# of it (http://wordle.localhost:8080), all through the proxy on this one
# port. Browsers resolve *.localhost themselves; in production, point this at
# a domain with wildcard DNS behind a TLS-terminating reverse proxy.
PUBLIC_URL = (
    os.environ.get("DGB_PUBLIC_URL", "").strip() or "http://localhost:8080"
).rstrip("/")
_PUBLIC = urlsplit(PUBLIC_URL)
PUBLIC_SCHEME = _PUBLIC.scheme
# The port the proxy listens on. Set it when something in front of the proxy
# (a reverse proxy, Docker) serves the public URL on a different port.
PROXY_PORT = int(os.environ.get("DGB_PROXY_PORT") or _PUBLIC.port or 8080)
# The launcher's own server, which only the proxy talks to.
LAUNCHER_PORT = 8090
LAUNCHER_URL = PUBLIC_URL
# Each game's host (and port, if any), with {game} for its name. Default: a
# subdomain of the public URL. Set it when those can't get a certificate, e.g.
# behind Cloudflare, whose free one doesn't cover *.daily.example.com:
# {game}-daily.example.com.
GAME_HOST = os.environ.get("DGB_GAME_HOST", "").strip() or f"{{game}}.{_PUBLIC.netloc}"


def game_origin(game_name: str) -> str:
    """Where a game is served: its own host, by default a subdomain of the
    public URL."""
    return f"{PUBLIC_SCHEME}://{GAME_HOST.format(game=game_name)}"


def db_path() -> Path:
    return Path(os.environ.get("DGB_DB_PATH") or REPO_ROOT / "data" / "results.db")


def bot_token() -> str:
    token = os.environ.get("DISCORD_BOT_TOKEN", "").strip()
    if not token:
        raise SystemExit("DISCORD_BOT_TOKEN isn't set; see .env.example")
    return token


def results_channel_id() -> int | None:
    """The channel results are announced in, or None to not announce them."""
    raw = os.environ.get("DISCORD_RESULTS_CHANNEL_ID", "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        raise SystemExit(
            f"DISCORD_RESULTS_CHANNEL_ID must be a channel ID, got {raw!r}"
        ) from None


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
