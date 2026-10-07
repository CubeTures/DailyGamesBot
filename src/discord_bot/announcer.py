"""Posts newly captured results to the results channel."""

import asyncio
from datetime import UTC, datetime, timedelta

import discord

from src import announce, results
from src.discord_bot.roles import game_role
from src.games.models import Game
from src.games.registry import GAMES_BY_NAME

# Results older than this when the bot first sees them (e.g. saved while it
# was down) are marked announced without being posted.
MAX_ANNOUNCE_AGE = timedelta(hours=6)


async def _messageable_channel(
    client: discord.Client, channel_id: int
) -> discord.abc.Messageable | None:
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


def _is_stale(result: results.StoredResult) -> bool:
    return datetime.now(UTC) - result.captured_at > MAX_ANNOUNCE_AGE


async def _message(
    channel: discord.abc.Messageable, game: Game, result: results.StoredResult
) -> tuple[str, discord.AllowedMentions]:
    """The announcement, pinging the game's role but not the players named.

    The role's mention stands in for the game's title; a template that
    doesn't show the title gets the mention added on a line of its own."""
    role = None
    if isinstance(channel, discord.abc.GuildChannel):
        role = await game_role(channel.guild, game)
    if role is None:
        return announce.render_result(game, result), discord.AllowedMentions.none()
    text = announce.render_result(game, result, game_mention=role.mention)
    if role.mention not in text:
        ping = f"\n-# {role.mention}"
        limit = announce.DISCORD_MAX_LENGTH - len(ping)
        if len(text) > limit:
            text = text[: limit - 1] + "…"
        text += ping
    return text, discord.AllowedMentions(everyone=False, users=False, roles=[role])


async def announce_pending_results(client: discord.Client, channel_id: int) -> None:
    pending = await asyncio.to_thread(results.unannounced)
    if not pending:
        return
    channel = await _messageable_channel(client, channel_id)
    if channel is None:
        return
    for result in pending:
        game = GAMES_BY_NAME.get(result.game)
        if game is not None and not _is_stale(result):
            try:
                text, allowed_mentions = await _message(channel, game, result)
                await channel.send(text, allowed_mentions=allowed_mentions)
            except discord.HTTPException as e:
                print(f"Couldn't announce result {result.id}: {e}")
                return  # Try again next loop.
        await asyncio.to_thread(results.mark_announced, result.id)
