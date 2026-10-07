"""The Discord bot: /play hands out launcher links, and finished games are
announced in the channel named by DISCORD_RESULTS_CHANNEL_ID (if set).

The proxy saves results in another process, so the bot polls the results
store for names to look up and results to post.
"""

import discord
from discord import app_commands
from discord.ext import tasks

from src import results
from src.discord_bot import settings
from src.discord_bot.announcer import announce_pending_results
from src.discord_bot.player_names import refresh_player_name, refresh_stale_names
from src.settings import LAUNCHER_URL

POLL_SECONDS = 15


def create_client(results_channel_id: int | None) -> discord.Client:
    client = discord.Client(intents=discord.Intents.default())
    tree = app_commands.CommandTree(client)

    @tasks.loop(seconds=POLL_SECONDS)
    async def poll_stale_names() -> None:
        await refresh_stale_names(client)

    @tasks.loop(seconds=POLL_SECONDS)
    async def poll_unannounced_results(channel_id: int) -> None:
        await announce_pending_results(client, channel_id)

    @client.event
    async def on_ready() -> None:
        await tree.sync()
        if not poll_stale_names.is_running():
            poll_stale_names.start()
        if results_channel_id is not None and not poll_unannounced_results.is_running():
            poll_unannounced_results.start(results_channel_id)
        print(f"Logged in as {client.user}")

    @tree.command(name="play", description="Get your personal link to the games hub")
    async def play(interaction: discord.Interaction) -> None:
        discord_id = str(interaction.user.id)
        link = f"[Let's play some games!]({LAUNCHER_URL}/?discord_id={discord_id})"
        # Reply first: Discord drops interactions not answered within 3s.
        await interaction.response.send_message(link, ephemeral=True)
        if results.add_player(discord_id):
            await refresh_player_name(client, discord_id)

    return client


async def run_bot(token: str) -> None:
    client = create_client(settings.results_channel_id())
    async with client:
        await client.start(token)
