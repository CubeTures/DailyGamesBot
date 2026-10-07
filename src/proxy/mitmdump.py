"""Runs mitmdump with one reverse-proxy listener per game."""

import asyncio
import os
import signal
from pathlib import Path

from src.games.registry import GAMES_BY_PORT
from src.settings import REPO_ROOT

ADDON_PATH = Path(__file__).with_name("addon.py")


def _env_with_repo_importable() -> dict[str, str]:
    # mitmdump loads the addon as a script, so `src` must be on its path.
    env = dict(os.environ)
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        f"{REPO_ROOT}{os.pathsep}{existing}" if existing else str(REPO_ROOT)
    )
    return env


def _listener_args() -> list[str]:
    args: list[str] = []
    for port, game in sorted(GAMES_BY_PORT.items()):
        args += ["--mode", f"reverse:{game.origin}@{port}"]
    return args


async def run_mitmdump() -> None:
    process = await asyncio.create_subprocess_exec(
        "mitmdump",
        "-s",
        str(ADDON_PATH),
        *_listener_args(),
        env=_env_with_repo_importable(),
    )
    # Without this, `kill <pid>` on us would orphan mitmdump on the ports.
    asyncio.get_running_loop().add_signal_handler(signal.SIGTERM, process.terminate)
    try:
        exit_code = await process.wait()
    except asyncio.CancelledError:
        process.terminate()
        await process.wait()
        raise
    raise SystemExit(f"mitmdump exited with code {exit_code}")
