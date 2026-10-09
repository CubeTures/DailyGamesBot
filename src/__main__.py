"""Runs the game proxy, its launcher page and the Discord bot together:
`uv run python3 -m src`."""

import asyncio

from src.discord_bot.bot import run_bot
from src.launcher.server import serve_launcher
from src.proxy.mitmdump import run_mitmdump
from src.settings import bot_token, configure_logging


async def _run_all(token: str) -> None:
    with serve_launcher():
        async with asyncio.TaskGroup() as tg:
            tg.create_task(run_mitmdump())
            tg.create_task(run_bot(token))


def main() -> None:
    configure_logging()
    asyncio.run(_run_all(bot_token()))


if __name__ == "__main__":
    main()
