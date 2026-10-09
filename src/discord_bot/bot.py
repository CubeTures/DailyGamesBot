"""The Discord bot: /play hands out launcher links, and finished games are
announced in the channel named by DISCORD_RESULTS_CHANNEL_ID (if set),
pinging the game's role in that channel's server (see roles.py).

A link carries a token standing in for the player's Discord ID (see
store/players.py). It stays the same until an admin resets it.

The proxy saves results in another process, so the bot polls the store for
names to look up, results to post, and roles to give or take.
"""

import asyncio
import logging
from typing import Any

import discord
from discord import app_commands
from discord.ext import tasks

from src.discord_bot.announcer import announce_pending_results
from src.discord_bot.channels import results_guild
from src.discord_bot.player_names import refresh_player_name, refresh_stale_names
from src.discord_bot.roles import create_game_roles, sync_subscriptions
from src.settings import LAUNCHER_URL, results_channel_id
from src.store import players

POLL_SECONDS = 15

log = logging.getLogger(__name__)


async def run_bot(token: str) -> None:
    client = create_client(results_channel_id())
    async with client:
        await client.start(token)


def create_client(results_channel_id: int | None) -> discord.Client:
    client = discord.Client(intents=discord.Intents.default())
    tree = app_commands.CommandTree(client)

    @tasks.loop(seconds=POLL_SECONDS)
    async def poll_stale_names() -> None:
        await refresh_stale_names(client)

    @tasks.loop(seconds=POLL_SECONDS)
    async def poll_unannounced_results(channel_id: int) -> None:
        await announce_pending_results(client, channel_id)

    @tasks.loop(seconds=POLL_SECONDS)
    async def poll_subscriptions(channel_id: int) -> None:
        if guild := await results_guild(client, channel_id):
            await sync_subscriptions(guild)

    @client.event
    async def on_ready() -> None:
        await tree.sync()
        _ensure_running(poll_stale_names)
        if results_channel_id is not None:
            if guild := await results_guild(client, results_channel_id):
                await create_game_roles(guild)
            _ensure_running(poll_unannounced_results, results_channel_id)
            _ensure_running(poll_subscriptions, results_channel_id)
        log.info("Logged in as %s", client.user)

    @tree.command(name="play", description="Get your personal link to the games hub")
    async def play(interaction: discord.Interaction) -> None:
        discord_id = str(interaction.user.id)
        is_new = await asyncio.to_thread(players.add, discord_id)
        token = await asyncio.to_thread(players.token_for, discord_id)
        link = (
            f"[Let's play some games!]({LAUNCHER_URL}/?token={token})\n"
            "-# This link is yours alone, so don't share it."
        )
        # Reply before the name lookup: Discord drops interactions not
        # answered within 3s.
        await interaction.response.send_message(link, ephemeral=True)
        if is_new:
            await refresh_player_name(client, discord_id)

    return client


def _ensure_running(loop: tasks.Loop[Any], *args: Any) -> None:
    """Start a polling loop; on_ready runs again after each reconnect."""
    if not loop.is_running():
        loop.start(*args)
