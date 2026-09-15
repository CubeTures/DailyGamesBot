"""Minimal discord.py bot with a single /hello slash command."""

import asyncio
import os

import discord
from discord import app_commands
from dotenv import load_dotenv

from src.proxy.config import LAUNCHER_PORT

LAUNCHER_URL = f"http://localhost:{LAUNCHER_PORT}"


def build_client() -> discord.Client:
    intents = discord.Intents.default()
    client = discord.Client(intents=intents)
    tree = app_commands.CommandTree(client)

    @client.event
    async def on_ready() -> None:
        await tree.sync()
        print(f"Logged in as {client.user}")

    @tree.command(name="play", description="Get your personal link to the games hub")
    async def link(interaction: discord.Interaction) -> None:
        url = (
            "[Let's play some games!]"
            + "({LAUNCHER_URL}/?discord_id={interaction.user.id})"
        )
        await interaction.response.send_message(url, ephemeral=True)

    return client


async def start(token: str) -> None:
    client = build_client()
    async with client:
        await client.start(token)


def main() -> None:
    load_dotenv()
    token = os.environ["DISCORD_BOT_TOKEN"]
    asyncio.run(start(token))


if __name__ == "__main__":
    main()
