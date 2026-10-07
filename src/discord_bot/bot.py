"""Minimal discord.py bot with a single /hello slash command."""

import asyncio
import os

import discord
from discord import app_commands
from discord.ext import tasks
from dotenv import load_dotenv

from src import results
from src.proxy.config import LAUNCHER_PORT

LAUNCHER_URL = f"http://localhost:{LAUNCHER_PORT}"


def build_client() -> discord.Client:
    intents = discord.Intents.default()
    client = discord.Client(intents=intents)
    tree = app_commands.CommandTree(client)

    async def refresh_name(discord_id: str) -> None:
        try:
            user = await client.fetch_user(int(discord_id))
        except discord.NotFound:
            # Don't retry a deleted account every loop; keep any old name.
            results.set_player_name(discord_id, None)
            return
        except discord.HTTPException as e:
            print(f"Couldn't look up Discord user {discord_id}: {e}")
            return
        results.set_player_name(discord_id, user.name)

    # Results are saved by the proxy, which can't reach the bot, so it marks
    # the player's name stale and this picks it up.
    @tasks.loop(seconds=15)
    async def refresh_stale_names() -> None:
        for discord_id in await asyncio.to_thread(results.stale_players):
            await refresh_name(discord_id)

    @client.event
    async def on_ready() -> None:
        await tree.sync()
        if not refresh_stale_names.is_running():
            refresh_stale_names.start()
        print(f"Logged in as {client.user}")

    @tree.command(name="play", description="Get your personal link to the games hub")
    async def link(interaction: discord.Interaction) -> None:
        discord_id = str(interaction.user.id)
        url = "[Let's play some games!]" + f"({LAUNCHER_URL}/?discord_id={discord_id})"
        # Reply first: Discord drops interactions not answered within 3s.
        await interaction.response.send_message(url, ephemeral=True)
        if results.add_player(discord_id):
            await refresh_name(discord_id)

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
