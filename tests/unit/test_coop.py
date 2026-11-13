"""Co-op games (`coop = true`): start reports, the shared game's combined
announcement, the scoreboard's daily sums and the launcher's join links."""

import asyncio
import json
import urllib.error
import urllib.request
from datetime import date, timedelta
from http.client import HTTPMessage
from pathlib import Path
from typing import IO, Any, cast

import pytest
from mitmproxy.test import tflow

from src import announce
from src.discord_bot import announcer
from src.discord_bot.channels import ResultsChannels
from src.games import loader
from src.games.models import Game
from src.games.registry import GAMES_BY_NAME
from src.proxy.capture.endpoints import handle_capture_request
from src.store import guilds, players, results, starts

CWF = GAMES_BY_NAME["crosswithfriends"]
WORDLE = GAMES_BY_NAME["wordle"]
DAY = date(2026, 11, 12)

# The roster every player's result of shared game "g1" carries.
ROSTER = [
    {"id": "a", "name": "Taxing Raven", "score": 18},
    {"id": "b", "name": "Stunning Marten", "score": 5},
    {"id": "c", "name": "Not *Proxied*", "score": 9},
]


def _save(
    discord_id: str,
    player_id: str,
    puzzle_id: str = "g1",
    game_day: date = DAY,
    **data: Any,
) -> None:
    fields = {
        "title": "NY Times Mini",
        "player_id": player_id,
        "score": next(p["score"] for p in ROSTER if p["id"] == player_id),
        "time_secs": 33,
        "players": ROSTER,
        **data,
    }
    results.save(
        results.NewResult(
            game=CWF.name,
            discord_id=discord_id,
            puzzle_id=puzzle_id,
            game_day=game_day,
            data=fields,
            trigger="record-solve",
        )
    )


def _post(game: Game, path: str, discord_id: str, body: dict[str, Any]) -> Any:
    flow = tflow.tflow()
    flow.request.method = "POST"
    flow.request.path = path
    flow.request.text = json.dumps(body)
    flow.request.headers["cookie"] = f"dgb_token={players.token_for(discord_id)}"
    assert handle_capture_request(flow, game)
    assert flow.response is not None
    return flow.response.json()


def _post_start(
    game: Game, puzzle_id: str, discord_id: str = "1", player_id: str | None = None
) -> Any:
    fields = {"title": "NY Times Mini", "player_id": player_id}
    return _post(
        game,
        "/__dgb/start",
        discord_id,
        {
            "puzzle_id": puzzle_id,
            "fields": fields,
            "url": "http://crosswithfriends.localhost:8080/beta/game/g1",
        },
    )


def _post_solve(discord_id: str, player_id: str) -> Any:
    """Report shared game g1 solved, as the record-solve trigger does."""
    fields = {
        "puzzle_id": "g1",
        "title": "NY Times Mini",
        "player_id": player_id,
        "score": next(p["score"] for p in ROSTER if p["id"] == player_id),
        "time_secs": 33,
        "players": ROSTER,
    }
    body = {"puzzle_id": "g1", "game_day": str(DAY), "fields": fields}
    return _post(CWF, "/__dgb/result", discord_id, body)


def test_a_solve_credits_everyone_who_played_through_the_proxy() -> None:
    # 1 and 2 play; 2 leaves before the solve, which 1's page reports.
    _post_start(CWF, "g1", "1", player_id="a")
    _post_start(CWF, "g1", "2", player_id="b")
    assert _post_solve("1", "a") == {"status": "saved"}
    shared = results.of_puzzle(CWF.name, "g1")
    assert {(r.discord_id, r.data["player_id"], r.data["score"]) for r in shared} == {
        ("1", "a", 18),
        ("2", "b", 5),
    }
    # Every other page in the game reports the same solve.
    assert _post_solve("2", "b") == {"status": "duplicate"}
    assert len(results.of_puzzle(CWF.name, "g1")) == 2


def test_a_solve_credits_its_reporter_without_a_start() -> None:
    assert _post_solve("3", "c") == {"status": "saved"}
    [result] = results.of_puzzle(CWF.name, "g1")
    assert (result.discord_id, result.data["score"]) == ("3", 9)


def test_start_is_saved_once_per_shared_game() -> None:
    assert _post_start(CWF, "g1", "1") == {"status": "saved"}
    assert _post_start(CWF, "g1", "2") == {"status": "duplicate"}
    [start] = starts.unannounced()
    assert (start.discord_id, start.puzzle_id) == ("1", "g1")
    assert announcer.join_url(start) == (
        "http://localhost:8080/join/crosswithfriends?to=%2Fbeta%2Fgame%2Fg1"
    )


def test_start_of_a_finished_game_or_non_coop_game_is_not_saved() -> None:
    _save("1", "a")
    assert _post_start(CWF, "g1") == {"status": "finished"}
    assert _post_start(WORDLE, "g2") == {"error": "not a co-op game"}
    assert starts.unannounced() == []


def test_start_triggers_need_coop(tmp_path: Path) -> None:
    game_dir = tmp_path / "solo"
    game_dir.mkdir()
    (game_dir / "config.toml").write_text(
        'name = "solo"\norigin = "https://example.com"\n'
        '[[triggers]]\nname = "s"\ntype = "page"\nreport = "start"\n'
    )
    (game_dir / "fields.js").write_text("export default { puzzle_id: 1 };\n")
    with pytest.raises(loader.ConfigError, match="coop"):
        loader.load_game(game_dir)


def test_coop_announcement_ranks_everyone_in_the_shared_game() -> None:
    _save("1", "a", puzzle_id="g0", game_day=DAY - timedelta(days=1))
    _save("1", "a")
    _save("2", "b")
    text = announce.render_coop(CWF, results.of_puzzle(CWF.name, "g1"))
    assert text.splitlines() == [
        ":sun_with_face: 3 players played **Cross with Friends** NY Times Mini",
        "32 squares in 0:33",
        "1. <@1> 18 squares :fire: 2",
        # Not captured through the proxy: their name from the site, escaped.
        "2. Not \\*Proxied\\* 9 squares",
        "3. <@2> 5 squares",
    ]


def test_scoreboard_sums_a_players_coop_day(launcher: str) -> None:
    _save("1", "a")
    _save("1", "a", puzzle_id="g2", score=4, time_secs=60)
    token = players.token_for("1")
    status, body = _get(f"{launcher}/api/results?day={DAY}&token={token}")
    assert status == 200
    [row] = body
    assert row["data"] == {"score": 22, "time_secs": 93, "puzzles": 2}
    assert row["announcement"].count(":sun_with_face:") == 2


def test_join_link_enters_the_game_with_the_clickers_token(launcher: str) -> None:
    token = players.token_for("1")
    request = urllib.request.Request(
        f"{launcher}/join/crosswithfriends?to=%2Fbeta%2Fgame%2Fg1",
        headers={"Cookie": f"dgb_token={token}"},
    )
    with pytest.raises(urllib.error.HTTPError) as redirect:
        urllib.request.build_opener(_NoRedirect).open(request)
    assert redirect.value.code == 302
    assert redirect.value.headers["Location"] == (
        f"http://crosswithfriends.localhost:8080/__dgb/enter?token={token}"
        "&to=%2Fbeta%2Fgame%2Fg1"
    )
    with pytest.raises(urllib.error.HTTPError) as locked:
        urllib.request.urlopen(f"{launcher}/join/crosswithfriends?to=%2F")
    assert locked.value.code == 401


class _Channel:
    """A results channel that records what's sent."""

    def __init__(self, guild_id: int) -> None:
        self.guild = type("Guild", (), {"id": guild_id})()
        self.sent: list[str] = []

    async def send(self, text: str, **_: Any) -> None:
        self.sent.append(text)


def test_bot_posts_a_shared_game_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def no_role(*_: Any) -> None:
        return None

    monkeypatch.setattr(announcer, "game_role", no_role)
    guilds.register("1", "10")
    guilds.register("2", "10")
    guilds.register("2", "20")
    _save("1", "a")
    _save("2", "b")
    channels = {10: _Channel(10), 20: _Channel(20)}
    run = lambda: asyncio.run(  # noqa: E731
        announcer.announce_pending_results(cast(ResultsChannels, channels))
    )
    run()
    run()
    assert len(channels[10].sent) == 1
    assert len(channels[20].sent) == 1
    assert "1. <@1> 18 squares" in channels[10].sent[0]
    assert results.unannounced() == []


def test_bot_posts_starts_with_a_join_link(monkeypatch: pytest.MonkeyPatch) -> None:
    async def no_role(*_: Any) -> None:
        return None

    monkeypatch.setattr(announcer, "game_role", no_role)
    guilds.register("1", "10")
    _post_start(CWF, "g1", "1")
    channels = {10: _Channel(10)}
    asyncio.run(announcer.announce_pending_results(cast(ResultsChannels, channels)))
    assert channels[10].sent == [
        ":sun_with_face: <@1> started **Cross with Friends** NY Times Mini\n"
        "[Help them complete the puzzle](http://localhost:8080/join/crosswithfriends"
        "?to=%2Fbeta%2Fgame%2Fg1)!"
    ]
    assert starts.unannounced() == []


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: IO[bytes],
        code: int,
        msg: str,
        headers: HTTPMessage,
        newurl: str,
    ) -> None:
        return None


def _get(url: str) -> tuple[int, Any]:
    with urllib.request.urlopen(url) as response:
        return response.status, json.load(response)
