"""Posts newly captured results in the results channel of each server the
player is registered with."""

import asyncio
import logging
from datetime import UTC, datetime, timedelta

import discord

from src import announce
from src.discord_bot.channels import ResultsChannel, ResultsChannels
from src.discord_bot.roles import game_role
from src.games.models import Game
from src.games.registry import GAMES_BY_NAME
from src.store import guilds, results

# Results older than this when the bot first sees them (e.g. saved while it
# was down) are marked announced without being posted.
MAX_ANNOUNCE_AGE = timedelta(hours=6)

log = logging.getLogger(__name__)


async def announce_pending_results(channels: ResultsChannels) -> None:
    for result in await asyncio.to_thread(results.unannounced):
        game = GAMES_BY_NAME.get(result.game)
        if game is None or _is_stale(result) or await _announce(channels, game, result):
            await asyncio.to_thread(results.mark_announced, result.id)


async def _announce(
    channels: ResultsChannels, game: Game, result: results.StoredResult
) -> bool:
    """Post the result in each of its player's servers it hasn't been posted
    in yet; False if one failed and it should be retried."""
    registered = await asyncio.to_thread(guilds.of_player, result.discord_id)
    done = await asyncio.to_thread(results.announced_in, result.id)
    ok = True
    for guild in registered:
        channel = channels.get(int(guild.id))
        if channel is None or guild.id in done:
            continue
        try:
            text, allowed_mentions = await _message(channel, game, result)
            await channel.send(text, allowed_mentions=allowed_mentions)
        except discord.HTTPException as e:
            log.warning(
                "Couldn't announce result %s in server %s: %s", result.id, guild.id, e
            )
            ok = False  # Try again next loop.
            continue
        await asyncio.to_thread(results.mark_announced_in, result.id, guild.id)
    return ok


def _is_stale(result: results.StoredResult) -> bool:
    return datetime.now(UTC) - result.captured_at > MAX_ANNOUNCE_AGE


async def _message(
    channel: ResultsChannel, game: Game, result: results.StoredResult
) -> tuple[str, discord.AllowedMentions]:
    """The announcement, pinging the game's role but not the players named.

    The role's mention stands in for the game's title; a template that
    doesn't show the title gets the mention added on a line of its own."""
    role = await game_role(channel.guild, game)
    if role is None:
        return announce.render_result(game, result), discord.AllowedMentions.none()
    text = announce.render_result(game, result, game_mention=role.mention)
    if role.mention not in text:
        ping = f"\n-# {role.mention}"
        text = announce.truncate(text, announce.DISCORD_MAX_LENGTH - len(ping)) + ping
    return text, discord.AllowedMentions(everyone=False, users=False, roles=[role])
