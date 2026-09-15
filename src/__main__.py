"""Runs the game proxy (with its launcher page) and the Discord bot together.

    uv run python -m src

Equivalent to what used to be `./run.sh` plus a separate
`python -m src.discord_bot.bot` in another terminal.
"""

import asyncio
import os
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

from dotenv import load_dotenv

from src.discord_bot.bot import start as start_bot
from src.proxy import gen_launcher
from src.proxy.config import GAMES, LAUNCHER_PORT

ADDON_PATH = gen_launcher.REPO_ROOT / "src" / "proxy" / "addon.py"


def _start_launcher_server() -> ThreadingHTTPServer:
    handler = partial(
        SimpleHTTPRequestHandler,
        directory=str(gen_launcher.REPO_ROOT / "launcher"),
    )
    server = ThreadingHTTPServer(("0.0.0.0", LAUNCHER_PORT), handler)
    Thread(target=server.serve_forever, daemon=True).start()
    return server


async def _run_mitmproxy() -> None:
    mode_args: list[str] = []
    for port, (_name, origin) in sorted(GAMES.items()):
        mode_args += ["--mode", f"reverse:{origin}@{port}"]

    repo_root = str(gen_launcher.REPO_ROOT)
    env = dict(os.environ)
    env["PYTHONPATH"] = (
        f"{repo_root}{os.pathsep}{env['PYTHONPATH']}"
        if env.get("PYTHONPATH")
        else repo_root
    )
    proc = await asyncio.create_subprocess_exec(
        "mitmdump", "-s", str(ADDON_PATH), *mode_args, env=env
    )
    try:
        await proc.wait()
    except asyncio.CancelledError:
        proc.terminate()
        await proc.wait()
        raise


async def main_async() -> None:
    load_dotenv()
    token = os.environ["DISCORD_BOT_TOKEN"]

    gen_launcher.write()
    server = _start_launcher_server()
    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(_run_mitmproxy())
            tg.create_task(start_bot(token))
    finally:
        server.shutdown()


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
