"""The Discord bot: /play hands out launcher links and registers the player
with the server it's run in, /primary picks the server their scoreboard opens
on, and finished games are announced in the results channel (from
DISCORD_RESULTS_CHANNEL_IDS) of each server the player is registered with,
pinging the game's role there (see roles.py).

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
from src.discord_bot.channels import ResultsChannels, results_channels
from src.discord_bot.player_names import refresh_player_name, refresh_stale_names
from src.discord_bot.roles import create_game_roles, sync_subscriptions
from src.settings import LAUNCHER_URL, results_channel_ids
from src.store import guilds, players

POLL_SECONDS = 15

log = logging.getLogger(__name__)


async def run_bot(token: str) -> None:
    client = create_client(results_channel_ids())
    async with client:
        await client.start(token)


def create_client(results_channel_ids: list[int]) -> discord.Client:
    client = discord.Client(intents=discord.Intents.default())
    tree = app_commands.CommandTree(client)
    # The working results channels by server ID, found in on_ready.
    channels: ResultsChannels = {}

    @tasks.loop(seconds=POLL_SECONDS)
    async def poll_stale_names() -> None:
        await refresh_stale_names(client)

    @tasks.loop(seconds=POLL_SECONDS)
    async def poll_unannounced_results() -> None:
        await announce_pending_results(channels)

    @tasks.loop(seconds=POLL_SECONDS)
    async def poll_subscriptions() -> None:
        await sync_subscriptions([channel.guild for channel in channels.values()])

    @client.event
    async def on_ready() -> None:
        await tree.sync()
        _ensure_running(poll_stale_names)
        channels.clear()
        channels.update(await results_channels(client, results_channel_ids))
        for channel in channels.values():
            await _save_guild_name(channel.guild)
            await create_game_roles(channel.guild)
        await _register_unregistered_players([c.guild for c in channels.values()])
        if channels:
            _ensure_running(poll_unannounced_results)
            _ensure_running(poll_subscriptions)
        log.info("Logged in as %s", client.user)

    @client.event
    async def on_guild_update(_before: discord.Guild, after: discord.Guild) -> None:
        await _save_guild_name(after)

    @tree.command(name="play", description="Get your personal link to the games hub")
    async def play(interaction: discord.Interaction) -> None:
        discord_id = str(interaction.user.id)
        is_new = await asyncio.to_thread(players.add, discord_id)
        token = await asyncio.to_thread(players.token_for, discord_id)
        link = (
            f"[Let's play some games!]({LAUNCHER_URL}/?token={token})\n"
            "-# This link is yours alone, so don't share it."
        )
        if (guild := interaction.guild) is not None:
            await _save_guild_name(guild)
            if await asyncio.to_thread(guilds.register, discord_id, str(guild.id)):
                posted = (
                    " and your results get posted here" if guild.id in channels else ""
                )
                link += f"\n-# You've joined {guild.name}'s scoreboard{posted}."
        # Reply before the name lookup: Discord drops interactions not
        # answered within 3s.
        await interaction.response.send_message(link, ephemeral=True)
        if is_new:
            await refresh_player_name(client, discord_id)

    @tree.command(
        name="primary",
        description="Make this server's scoreboard the one your games hub opens on",
    )
    @app_commands.guild_only()
    async def primary(interaction: discord.Interaction) -> None:
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                "Run this in a server.", ephemeral=True
            )
            return
        discord_id = str(interaction.user.id)
        is_new = await asyncio.to_thread(players.add, discord_id)
        await _save_guild_name(guild)
        await asyncio.to_thread(guilds.set_primary, discord_id, str(guild.id))
        await interaction.response.send_message(
            f"Your games hub's scoreboard now opens on {guild.name}.", ephemeral=True
        )
        if is_new:
            await refresh_player_name(client, discord_id)

    return client


async def _save_guild_name(guild: discord.Guild) -> None:
    await asyncio.to_thread(guilds.save_name, str(guild.id), guild.name)


async def _register_unregistered_players(servers: list[discord.Guild]) -> None:
    """Register players from before servers were tracked with each of
    `servers` they're in; the first becomes their primary one. Those in none
    stay unregistered until they run /play in a server."""
    for discord_id in await asyncio.to_thread(guilds.unregistered_players):
        for guild in servers:
            try:
                await guild.fetch_member(int(discord_id))
            except discord.NotFound:
                continue
            except discord.HTTPException as e:
                log.warning(
                    "Couldn't check if %s is in server %s: %s", discord_id, guild.id, e
                )
                continue
            await asyncio.to_thread(guilds.register, discord_id, str(guild.id))
            log.info("Registered %s with server %s", discord_id, guild.name)


def _ensure_running(loop: tasks.Loop[Any]) -> None:
    """Start a polling loop; on_ready runs again after each reconnect."""
    if not loop.is_running():
        loop.start()
