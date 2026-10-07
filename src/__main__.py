"""Runs the game proxy (with its launcher page) and the Discord bot together.

    uv run python -m src

Equivalent to what used to be `./run.sh` plus a separate
`python -m src.discord_bot.bot` in another terminal. To run only the proxy
(no Discord token needed), use `python -m src.proxy`.
"""

import asyncio
import os

from dotenv import load_dotenv

from src.discord_bot.bot import start as start_bot
from src.proxy.runner import run_mitmproxy, start_launcher_server


async def main_async() -> None:
    load_dotenv()
    token = os.environ["DISCORD_BOT_TOKEN"]

    server = start_launcher_server()
    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(run_mitmproxy())
            tg.create_task(start_bot(token))
    finally:
        server.shutdown()


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
