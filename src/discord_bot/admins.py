"""Admins of the bot's server can turn games on and off on the launcher.

The launcher can't reach the bot, so the bot records who is an admin in the
store whenever they run /play, and with a results channel also polls every
known player's status in its server. The server is the results channel's if
one is set, else the one /play was run in.
"""

import asyncio
import logging

import discord

from src.discord_bot.channels import results_guild
from src.store import players

log = logging.getLogger(__name__)


async def refresh_admins(guild: discord.Guild) -> None:
    """Re-check every known player, so rights given or taken in Discord reach
    the launcher without them running /play again."""
    for discord_id in await asyncio.to_thread(players.all_ids):
        is_admin = await _is_admin(guild, int(discord_id))
        if is_admin is not None:
            await asyncio.to_thread(players.set_admin, discord_id, is_admin)


async def refresh_admin(
    client: discord.Client,
    results_channel_id: int | None,
    interaction: discord.Interaction,
) -> None:
    """Record whether the player who ran /play is an admin of the server."""
    if results_channel_id is not None:
        guild = await results_guild(client, results_channel_id)
    else:
        guild = interaction.guild
    if guild is None:
        return  # Run in a DM with no results channel: leave it as it was.
    user = interaction.user
    if isinstance(user, discord.Member) and user.guild.id == guild.id:
        is_admin = user.guild_permissions.administrator
    else:
        is_admin = await _is_admin(guild, user.id)
    if is_admin is not None:
        await asyncio.to_thread(players.set_admin, str(user.id), is_admin)


async def _is_admin(guild: discord.Guild, discord_id: int) -> bool | None:
    """Whether they have Administrator there; None if Discord didn't say."""
    try:
        member = await guild.fetch_member(discord_id)
    except discord.NotFound:
        return False  # Not in the server.
    except discord.HTTPException as e:
        log.warning("Couldn't check whether %s is an admin: %s", discord_id, e)
        return None
    return member.guild_permissions.administrator
