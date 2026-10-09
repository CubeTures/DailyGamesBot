"""Admins of the bot's server can turn games on and off on the launcher.

The launcher can't reach the bot, so the bot records who is an admin in the
results store whenever they run /play, and with a results channel also polls
every known player's status in its server. The server is the results
channel's if one is set, else the one /play was run in.
"""

import asyncio

import discord

from src import results
from src.discord_bot.roles import results_guild


async def _admin_guild(
    client: discord.Client,
    results_channel_id: int | None,
    interaction: discord.Interaction,
) -> discord.Guild | None:
    if results_channel_id is not None:
        return await results_guild(client, results_channel_id)
    return interaction.guild


async def _is_admin(guild: discord.Guild, discord_id: int) -> bool | None:
    """Whether they have Administrator there; None if Discord didn't say."""
    try:
        member = await guild.fetch_member(discord_id)
    except discord.NotFound:
        return False  # Not in the server.
    except discord.HTTPException as e:
        print(f"Couldn't check whether {discord_id} is an admin: {e}")
        return None
    return member.guild_permissions.administrator


async def refresh_admins(guild: discord.Guild) -> None:
    """Re-check every known player, so rights given or taken in Discord reach
    the launcher without them running /play again."""
    for discord_id in await asyncio.to_thread(results.player_ids):
        is_admin = await _is_admin(guild, int(discord_id))
        if is_admin is not None:
            await asyncio.to_thread(results.set_player_admin, discord_id, is_admin)


async def refresh_admin(
    client: discord.Client,
    results_channel_id: int | None,
    interaction: discord.Interaction,
) -> None:
    """Record whether the player who ran /play is an admin of the server."""
    guild = await _admin_guild(client, results_channel_id, interaction)
    if guild is None:
        return  # Run in a DM with no results channel: leave it as it was.
    user = interaction.user
    if isinstance(user, discord.Member) and user.guild.id == guild.id:
        is_admin = user.guild_permissions.administrator
    else:
        is_admin = await _is_admin(guild, user.id)
    if is_admin is not None:
        await asyncio.to_thread(results.set_player_admin, str(user.id), is_admin)
