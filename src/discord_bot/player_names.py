"""Keeps players' Discord usernames current for the launcher's scoreboard."""

import asyncio
import logging

import discord

from src.store import players

log = logging.getLogger(__name__)


async def refresh_player_name(client: discord.Client, discord_id: str) -> None:
    try:
        user = await client.fetch_user(int(discord_id))
    except discord.NotFound:
        # Don't retry a deleted account every loop; keep any old name.
        await asyncio.to_thread(players.set_name, discord_id, None)
        return
    except discord.HTTPException as e:
        log.warning("Couldn't look up Discord user %s: %s", discord_id, e)
        return
    await asyncio.to_thread(players.set_name, discord_id, user.name)


async def refresh_stale_names(client: discord.Client) -> None:
    for discord_id in await asyncio.to_thread(players.stale_name_ids):
        await refresh_player_name(client, discord_id)
