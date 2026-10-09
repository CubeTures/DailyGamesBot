"""Paths, ports and environment settings shared by the proxy, the launcher
and the Discord bot. Environment variables may also come from .env."""

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
GAMES_DIR = REPO_ROOT / "games"
LAUNCHER_DIR = REPO_ROOT / "launcher"

LAUNCHER_PORT = 8090
LAUNCHER_URL = f"http://localhost:{LAUNCHER_PORT}"

load_dotenv(REPO_ROOT / ".env")


def db_path() -> Path:
    return Path(os.environ.get("DGB_DB_PATH", REPO_ROOT / "data" / "results.db"))


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
