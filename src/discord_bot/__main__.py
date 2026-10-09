"""Runs just the Discord bot: `uv run python3 -m src.discord_bot`."""

import asyncio

from src.discord_bot.bot import run_bot
from src.settings import bot_token, configure_logging

if __name__ == "__main__":
    configure_logging()
    asyncio.run(run_bot(bot_token()))
