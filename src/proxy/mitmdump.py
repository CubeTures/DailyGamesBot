"""Runs mitmdump: one reverse-proxy listener for the launcher and every game.

Requests go to the launcher by default; the addon sends those for a game's
subdomain on to the game's real origin instead.
"""

import asyncio
import os
import signal
from pathlib import Path

from src.settings import LAUNCHER_PORT, PROXY_PORT, REPO_ROOT

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
    return [
        "--mode",
        f"reverse:http://127.0.0.1:{LAUNCHER_PORT}@{PROXY_PORT}",
        # The addon picks the game by the Host the browser sent.
        "--set",
        "keep_host_header=true",
    ]


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
