"""Paths and ports shared by the proxy, the launcher and the Discord bot."""

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
GAMES_DIR = REPO_ROOT / "games"
LAUNCHER_DIR = REPO_ROOT / "launcher"

LAUNCHER_PORT = 8090
LAUNCHER_URL = f"http://localhost:{LAUNCHER_PORT}"


def db_path() -> Path:
    return Path(os.environ.get("DGB_DB_PATH", REPO_ROOT / "data" / "results.db"))
