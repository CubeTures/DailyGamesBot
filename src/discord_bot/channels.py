"""Looking up the results channels and the servers they're in."""

import logging

import discord

log = logging.getLogger(__name__)

Channel = discord.abc.GuildChannel | discord.abc.PrivateChannel | discord.Thread
# A server's results channel.
ResultsChannel = discord.TextChannel | discord.VoiceChannel | discord.Thread
# Results channels by their server's ID.
ResultsChannels = dict[int, ResultsChannel]


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


async def results_channels(
    client: discord.Client, channel_ids: list[int]
) -> ResultsChannels:
    """The configured results channels that work, by their server's ID. A
    server should have only one; if it has more, the first listed is used."""
    channels: ResultsChannels = {}
    for channel_id in channel_ids:
        channel = await fetch_channel(client, channel_id)
        if channel is None:
            continue
        if not isinstance(
            channel, discord.TextChannel | discord.VoiceChannel | discord.Thread
        ):
            log.warning(
                "Results channel %s isn't a server channel that takes messages",
                channel_id,
            )
            continue
        if (other := channels.get(channel.guild.id)) is not None:
            log.error(
                "Results channels %s and %s are both in server %s (%s); using %s."
                " Give each server only one in DISCORD_RESULTS_CHANNEL_IDS.",
                other.id,
                channel_id,
                channel.guild.name,
                channel.guild.id,
                other.id,
            )
            continue
        channels[channel.guild.id] = channel
    return channels
