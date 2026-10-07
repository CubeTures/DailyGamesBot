"""Runs just the Discord bot: `uv run python3 -m src.discord_bot`."""

import asyncio

from src.discord_bot.bot import run_bot
from src.discord_bot.settings import bot_token

if __name__ == "__main__":
    asyncio.run(run_bot(bot_token()))
