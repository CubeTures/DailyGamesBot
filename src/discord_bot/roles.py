"""Game roles: one per game, named after it, in the results channel's server.
Players pick theirs on the launcher, and results for a game ping its role.

The launcher saves picks in the results store (it can't reach the bot), so
the bot polls for unsynced ones and gives or takes the role. The bot needs
the Manage Roles permission.
"""

import asyncio

import discord

from src import results
from src.games.models import Game
from src.games.registry import GAMES_BY_NAME


async def results_guild(
    client: discord.Client, channel_id: int
) -> discord.Guild | None:
    """The server the results channel is in."""
    channel = client.get_channel(channel_id)
    if channel is None:
        try:
            channel = await client.fetch_channel(channel_id)
        except discord.HTTPException as e:
            print(f"Can't open results channel {channel_id}: {e}")
            return None
    if not isinstance(channel, discord.abc.GuildChannel):
        print(f"Results channel {channel_id} isn't in a server; no game roles")
        return None
    return channel.guild


async def game_role(guild: discord.Guild, game: Game) -> discord.Role | None:
    """The game's role, created if it doesn't exist yet."""
    role = discord.utils.get(guild.roles, name=game.title)
    if role is not None:
        return role
    try:
        return await guild.create_role(
            name=game.title,
            mentionable=True,
            reason=f"Pinged when someone finishes {game.title}",
        )
    except discord.HTTPException as e:
        print(f"Couldn't create the {game.title} role: {e}")
        return None


async def create_game_roles(guild: discord.Guild) -> None:
    for game in GAMES_BY_NAME.values():
        await game_role(guild, game)


async def _apply(guild: discord.Guild, sub: results.Subscription) -> bool:
    """Give or take the role; False if it should be retried later."""
    game = GAMES_BY_NAME.get(sub.game)
    if game is None:
        return True  # The game is gone; nothing to do.
    role = await game_role(guild, game)
    if role is None:
        return False
    try:
        member = await guild.fetch_member(int(sub.discord_id))
        if sub.subscribed:
            await member.add_roles(role, reason="Subscribed on the launcher")
        else:
            await member.remove_roles(role, reason="Unsubscribed on the launcher")
    except discord.NotFound:
        return True  # Not in the server.
    except discord.HTTPException as e:
        print(f"Couldn't update {sub.discord_id}'s {game.title} role: {e}")
        return False
    return True


async def sync_subscriptions(guild: discord.Guild) -> None:
    for sub in await asyncio.to_thread(results.unsynced_subscriptions):
        if not await _apply(guild, sub):
            return  # Try again next loop.
        await asyncio.to_thread(results.mark_subscription_synced, sub)
