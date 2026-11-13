"""Posts newly captured results in the results channel of each server the
player is registered with.

A co-op game's results are posted together, one message per shared game
(puzzle_id) in each server any of its players is registered with. They're
all saved at once, from the first solve reported (see capture/endpoints.py).
Its starts are posted in the
starter's servers with a link for others to join them.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from urllib.parse import quote, urlsplit

import discord

from src import announce
from src.discord_bot.channels import ResultsChannel, ResultsChannels
from src.discord_bot.roles import game_role
from src.games.models import Game
from src.games.registry import GAMES_BY_NAME
from src.settings import LAUNCHER_URL
from src.store import guilds, results, starts

# Results older than this when the bot first sees them (e.g. saved while it
# was down) are marked announced without being posted.
MAX_ANNOUNCE_AGE = timedelta(hours=6)
# Starts older than this when first seen aren't worth joining any more.
MAX_START_AGE = timedelta(minutes=30)

log = logging.getLogger(__name__)


# Renders a message given the game role's mention (None without a role).
Render = Callable[[str | None], str]


async def announce_pending_results(channels: ResultsChannels) -> None:
    await _announce_pending_starts(channels)
    pending = await asyncio.to_thread(results.unannounced)
    coop_done: set[tuple[str, str]] = set()
    for result in pending:
        game = GAMES_BY_NAME.get(result.game)
        if game is None or _is_stale(result.captured_at, MAX_ANNOUNCE_AGE):
            await asyncio.to_thread(results.mark_announced, result.id)
        elif game.coop:
            if (game.name, result.puzzle_id) not in coop_done:
                coop_done.add((game.name, result.puzzle_id))
                await _announce_shared_game(channels, game, result.puzzle_id)
        elif await _announce(channels, game, result):
            await asyncio.to_thread(results.mark_announced, result.id)


async def _announce(
    channels: ResultsChannels, game: Game, result: results.StoredResult
) -> bool:
    """Post the result in each of its player's servers it hasn't been posted
    in yet; False if one failed and it should be retried."""

    def render(game_mention: str | None) -> str:
        return announce.render_result(game, result, game_mention=game_mention)

    return await _post_in_servers(
        channels,
        game,
        render,
        servers=await _servers_of([result.discord_id]),
        done=await asyncio.to_thread(results.announced_in, result.id),
        mark_done=lambda guild_id: asyncio.to_thread(
            results.mark_announced_in, result.id, guild_id
        ),
        what=f"result {result.id}",
    )


async def _announce_shared_game(
    channels: ResultsChannels, game: Game, puzzle_id: str
) -> None:
    """Post one message for all the results of a co-op game's shared game."""
    shared = await asyncio.to_thread(results.of_puzzle, game.name, puzzle_id)
    # The servers it went to, for any of its results.
    done: set[str] = set()
    for result in shared:
        done |= await asyncio.to_thread(results.announced_in, result.id)

    def render(game_mention: str | None) -> str:
        return announce.render_coop(game, shared, game_mention=game_mention)

    async def mark_done(guild_id: str) -> None:
        for result in shared:
            await asyncio.to_thread(results.mark_announced_in, result.id, guild_id)

    ok = await _post_in_servers(
        channels,
        game,
        render,
        servers=await _servers_of([r.discord_id for r in shared]),
        done=done,
        mark_done=mark_done,
        what=f"{game.name} game {puzzle_id}",
    )
    if ok:
        for result in shared:
            await asyncio.to_thread(results.mark_announced, result.id)


async def _announce_pending_starts(channels: ResultsChannels) -> None:
    for start in await asyncio.to_thread(starts.unannounced):
        game = GAMES_BY_NAME.get(start.game)
        finished = await asyncio.to_thread(
            results.of_puzzle, start.game, start.puzzle_id
        )
        if game is None or finished or _is_stale(start.captured_at, MAX_START_AGE):
            await asyncio.to_thread(starts.mark_announced, start.id)
            continue

        def render(
            game_mention: str | None,
            game: Game = game,
            start: starts.StoredStart = start,
        ) -> str:
            return announce.render_started(
                game, start, join_url(start), game_mention=game_mention
            )

        ok = await _post_in_servers(
            channels,
            game,
            render,
            servers=await _servers_of([start.discord_id]),
            done=await asyncio.to_thread(starts.announced_in, start.id),
            mark_done=lambda guild_id, start=start: asyncio.to_thread(
                starts.mark_announced_in, start.id, guild_id
            ),
            what=f"start {start.id}",
        )
        if ok:
            await asyncio.to_thread(starts.mark_announced, start.id)


def join_url(start: starts.StoredStart) -> str:
    """The launcher's link into the started game: it lets whoever clicks it
    in with their own token (see launcher/server.py's /join/)."""
    url = urlsplit(start.url or "")
    path = url.path + (f"?{url.query}" if url.query else "")
    return f"{LAUNCHER_URL}/join/{start.game}?to={quote(path or '/', safe='')}"


async def _servers_of(discord_ids: list[str]) -> list[str]:
    """The servers any of the players is registered with, in order."""
    servers: dict[str, None] = {}
    for discord_id in discord_ids:
        for guild in await asyncio.to_thread(guilds.of_player, discord_id):
            servers[guild.id] = None
    return list(servers)


async def _post_in_servers(
    channels: ResultsChannels,
    game: Game,
    render: Render,
    *,
    servers: list[str],
    done: set[str],
    mark_done: Callable[[str], Awaitable[object]],
    what: str,
) -> bool:
    """Post a message in the results channel of each of `servers` not in
    `done`; False if one failed and it should be retried."""
    ok = True
    for guild_id in servers:
        channel = channels.get(int(guild_id))
        if channel is None or guild_id in done:
            continue
        try:
            text, allowed_mentions = await _message(channel, game, render)
            await channel.send(text, allowed_mentions=allowed_mentions)
        except discord.HTTPException as e:
            log.warning("Couldn't announce %s in server %s: %s", what, guild_id, e)
            ok = False  # Try again next loop.
            continue
        await mark_done(guild_id)
    return ok


def _is_stale(captured_at: datetime, age: timedelta) -> bool:
    return datetime.now(UTC) - captured_at > age


async def _message(
    channel: ResultsChannel, game: Game, render: Render
) -> tuple[str, discord.AllowedMentions]:
    """The announcement, pinging the game's role but not the players named.

    The role's mention stands in for the game's title; a template that
    doesn't show the title gets the mention added on a line of its own."""
    role = await game_role(channel.guild, game)
    if role is None:
        return render(None), discord.AllowedMentions.none()
    text = render(role.mention)
    if role.mention not in text:
        ping = f"\n-# {role.mention}"
        text = announce.truncate(text, announce.DISCORD_MAX_LENGTH - len(ping)) + ping
    return text, discord.AllowedMentions(everyone=False, users=False, roles=[role])
