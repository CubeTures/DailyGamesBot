"""Keeps players' Discord usernames current for the launcher's scoreboard."""

import asyncio

import discord

from src import results


async def refresh_player_name(client: discord.Client, discord_id: str) -> None:
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


async def refresh_stale_names(client: discord.Client) -> None:
    for discord_id in await asyncio.to_thread(results.stale_player_ids):
        await refresh_player_name(client, discord_id)
