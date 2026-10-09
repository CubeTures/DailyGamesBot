"""Game roles: one per game, named after it, in the results channel's server.
Players pick theirs on the launcher, and results for a game ping its role.

The launcher saves picks in the store (it can't reach the bot), so the bot
polls for unsynced ones and gives or takes the role. The bot needs the
Manage Roles permission.
"""

import asyncio
import logging

import discord

from src.games.models import Game
from src.games.registry import GAMES_BY_NAME
from src.store import subscriptions

log = logging.getLogger(__name__)


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
        log.warning("Couldn't create the %s role: %s", game.title, e)
        return None


async def create_game_roles(guild: discord.Guild) -> None:
    for game in GAMES_BY_NAME.values():
        await game_role(guild, game)


async def sync_subscriptions(guild: discord.Guild) -> None:
    for sub in await asyncio.to_thread(subscriptions.unsynced):
        if not await _apply(guild, sub):
            return  # Try again next loop.
        await asyncio.to_thread(subscriptions.mark_synced, sub)


async def _apply(guild: discord.Guild, sub: subscriptions.Subscription) -> bool:
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
        log.warning("Couldn't update %s's %s role: %s", sub.discord_id, game.title, e)
        return False
    return True
