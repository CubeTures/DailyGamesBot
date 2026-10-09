"""Looking up the results channel and the server it's in."""

import logging

import discord

log = logging.getLogger(__name__)

Channel = discord.abc.GuildChannel | discord.abc.PrivateChannel | discord.Thread


async def fetch_channel(client: discord.Client, channel_id: int) -> Channel | None:
    """The channel, from the cache or else from Discord."""
    channel = client.get_channel(channel_id)
    if channel is not None:
        return channel
    try:
        return await client.fetch_channel(channel_id)
    except discord.HTTPException as e:
        log.warning("Can't open channel %s: %s", channel_id, e)
        return None


async def results_guild(
    client: discord.Client, channel_id: int
) -> discord.Guild | None:
    """The server the results channel is in."""
    channel = await fetch_channel(client, channel_id)
    if channel is None:
        return None
    if not isinstance(channel, discord.abc.GuildChannel):
        log.warning("Results channel %s isn't in a server; no game roles", channel_id)
        return None
    return channel.guild
