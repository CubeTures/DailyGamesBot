"""The Discord bot: /play hands out launcher links, and finished games are
announced in the channel named by DISCORD_RESULTS_CHANNEL_ID (if set)."""

import asyncio
import os
from datetime import UTC, datetime, timedelta

import discord
from discord import app_commands
from discord.ext import tasks
from dotenv import load_dotenv

from src import announce, results
from src.proxy.config import GAME_CONFIGS, LAUNCHER_PORT

LAUNCHER_URL = f"http://localhost:{LAUNCHER_PORT}"

# Results older than this when the bot first sees them (e.g. saved while it
# was down) are marked announced without being posted.
ANNOUNCE_MAX_AGE = timedelta(hours=6)

GAMES_BY_NAME = {g.name: g for g in GAME_CONFIGS.values()}


def build_client(results_channel_id: int | None = None) -> discord.Client:
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

    async def results_channel(channel_id: int) -> discord.abc.Messageable | None:
        channel = client.get_channel(channel_id)
        if channel is None:
            try:
                channel = await client.fetch_channel(channel_id)
            except discord.HTTPException as e:
                print(f"Can't open results channel {channel_id}: {e}")
                return None
        if not isinstance(channel, discord.abc.Messageable):
            print(f"Results channel {channel_id} can't take messages")
            return None
        return channel

    # Same as names: the proxy saves results, the bot posts them.
    @tasks.loop(seconds=15)
    async def announce_results() -> None:
        assert results_channel_id is not None
        pending = await asyncio.to_thread(results.unannounced)
        if not pending:
            return
        channel = await results_channel(results_channel_id)
        if channel is None:
            return
        for result in pending:
            game = GAMES_BY_NAME.get(result.game)
            too_old = datetime.now(UTC) - result.captured_at > ANNOUNCE_MAX_AGE
            if game is not None and not too_old:
                text = announce.render(
                    game.announcement,
                    game=game.title,
                    player=f"<@{result.discord_id}>",
                    puzzle_id=result.puzzle_id,
                    fields=result.data,
                )
                try:
                    # Mentions render as names but don't ping anyone.
                    await channel.send(
                        text, allowed_mentions=discord.AllowedMentions.none()
                    )
                except discord.HTTPException as e:
                    print(f"Couldn't announce result {result.id}: {e}")
                    return  # Try again next loop.
            await asyncio.to_thread(results.mark_announced, result.id)

    @client.event
    async def on_ready() -> None:
        await tree.sync()
        if not refresh_stale_names.is_running():
            refresh_stale_names.start()
        if results_channel_id is not None and not announce_results.is_running():
            announce_results.start()
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


def results_channel_id() -> int | None:
    raw = os.environ.get("DISCORD_RESULTS_CHANNEL_ID", "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        raise SystemExit(
            f"DISCORD_RESULTS_CHANNEL_ID must be a channel ID, got {raw!r}"
        ) from None


async def start(token: str) -> None:
    client = build_client(results_channel_id())
    async with client:
        await client.start(token)


def main() -> None:
    load_dotenv()
    token = os.environ["DISCORD_BOT_TOKEN"]
    asyncio.run(start(token))


if __name__ == "__main__":
    main()
