import sqlite3
from datetime import date
from pathlib import Path

from src.store import guilds, hidden_games, players, results, subscriptions


def _result(puzzle_id: str = "p1", discord_id: str = "1") -> results.NewResult:
    return results.NewResult(
        game="wordle",
        discord_id=discord_id,
        puzzle_id=puzzle_id,
        game_day=date(2026, 10, 8),
        data={"score": 3},
        trigger="t",
    )


def test_save_keeps_first_capture_and_marks_name_stale() -> None:
    assert results.save(_result())
    assert not results.save(_result())
    assert players.stale_name_ids() == ["1"]
    players.set_name("1", "alice")
    assert players.stale_name_ids() == []
    [stored] = results.on_day(date(2026, 10, 8), "1", None)
    assert stored.player_name == "alice"
    assert results.on_day(date(2026, 10, 9), "1", None) == []


def test_announcing() -> None:
    results.save(_result("a"))
    results.save(_result("b"))
    first, second = results.unannounced()
    results.mark_announced(first.id)
    assert [r.id for r in results.unannounced()] == [second.id]


def test_announcing_per_server() -> None:
    results.save(_result())
    [result] = results.unannounced()
    assert results.announced_in(result.id) == set()
    results.mark_announced_in(result.id, "g1")
    results.mark_announced_in(result.id, "g1")
    assert results.announced_in(result.id) == {"g1"}


def test_first_server_is_primary_until_changed() -> None:
    assert guilds.primary("1") is None
    assert guilds.register("1", "g1")
    assert not guilds.register("1", "g1")
    assert guilds.register("1", "g2")
    assert guilds.primary("1") == "g1"
    guilds.set_primary("1", "g3")
    assert guilds.primary("1") == "g3"
    guilds.save_name("g1", "Old name")
    guilds.save_name("g1", "Server one")
    assert guilds.of_player("1") == [
        guilds.PlayerGuild("g1", "Server one"),
        guilds.PlayerGuild("g2", None),
        guilds.PlayerGuild("g3", None),
    ]
    assert guilds.is_registered("1", "g2")
    assert not guilds.is_registered("2", "g2")


def test_scoreboard_shows_only_a_shared_servers_players() -> None:
    day = date(2026, 10, 8)
    for discord_id in ("me", "friend", "stranger", "outsider"):
        results.save(_result(discord_id=discord_id))
    guilds.register("me", "g1")
    guilds.register("friend", "g1")
    guilds.register("stranger", "g2")
    guilds.register("outsider", "g2")

    def players_shown(viewer: str, guild_id: str | None) -> set[str]:
        return {r.discord_id for r in results.on_day(day, viewer, guild_id)}

    assert players_shown("me", "g1") == {"me", "friend"}
    assert players_shown("me", None) == {"me"}
    # Not registered there, so only their own results.
    assert players_shown("me", "g2") == {"me"}
    assert players_shown("stranger", "g2") == {"stranger", "outsider"}
    assert players_shown("me", results.ALL_GUILDS) == {"me", "friend"}
    guilds.register("me", "g2")
    assert players_shown("me", results.ALL_GUILDS) == {
        "me",
        "friend",
        "stranger",
        "outsider",
    }
    assert players_shown("friend", results.ALL_GUILDS) == {"me", "friend"}


def test_players() -> None:
    assert players.add("1")
    assert not players.add("1")
    players.set_name("1", None)
    assert players.all_ids() == ["1"]


def test_tokens_last_until_reset() -> None:
    assert players.add("1")
    token = players.token_for("1")
    assert players.token_for("1") == token
    assert players.discord_id_for(token) == "1"
    assert players.reset_token("1")
    assert not players.reset_token("1")
    assert players.discord_id_for(token) is None
    new = players.token_for("1")
    assert new != token
    assert players.discord_id_for(new) == "1"
    assert players.discord_id_for("") is None
    assert players.token_for("2") != new
    assert players.all_ids() == ["1", "2"]


def test_subscriptions_sync_only_the_latest_choice() -> None:
    on = subscriptions.Subscription("1", "wordle", True)
    subscriptions.save(on)
    assert subscriptions.subscribed_games("1") == ["wordle"]
    assert subscriptions.unsynced() == [on]
    subscriptions.save(subscriptions.Subscription("1", "wordle", False))
    subscriptions.mark_synced(on)  # stale: the player changed it since
    assert subscriptions.unsynced() == [
        subscriptions.Subscription("1", "wordle", False)
    ]
    assert subscriptions.subscribed_games("1") == []


def test_hidden_games_are_per_player() -> None:
    hidden_games.set_level("1", "wordle", "card")
    hidden_games.set_level("1", "wordle", "all")
    hidden_games.set_level("1", "connections", "card")
    assert hidden_games.levels("1") == {"wordle": "all", "connections": "card"}
    assert hidden_games.levels("2") == {}
    hidden_games.set_level("1", "wordle", "shown")
    assert hidden_games.levels("1") == {"connections": "card"}


def test_migrates_old_databases(scratch_db: Path) -> None:
    conn = sqlite3.connect(scratch_db)
    conn.executescript(
        """
        CREATE TABLE results (
            id INTEGER PRIMARY KEY, game TEXT NOT NULL, discord_id TEXT NOT NULL,
            puzzle_id TEXT NOT NULL, data TEXT NOT NULL, trigger TEXT NOT NULL,
            url TEXT, captured_at TEXT NOT NULL,
            UNIQUE (game, discord_id, puzzle_id)
        );
        CREATE TABLE players (
            discord_id TEXT PRIMARY KEY, name TEXT,
            name_stale INTEGER NOT NULL DEFAULT 0
        );
        INSERT INTO results (game, discord_id, puzzle_id, data, trigger, captured_at)
        VALUES ('wordle', '1', '2026-01-02', '{}', 't', '2026-01-02T12:00:00+00:00'),
               ('wordle', '1', '77', '{}', 't', '2026-01-03T12:00:00+00:00');
        INSERT INTO players (discord_id) VALUES ('1');
        """
    )
    conn.commit()
    conn.close()

    assert results.unannounced() == []  # old results count as announced
    assert [r.puzzle_id for r in results.on_day(date(2026, 1, 2), "1", None)] == [
        "2026-01-02"
    ]
    assert [r.puzzle_id for r in results.on_day(date(2026, 1, 3), "1", None)] == ["77"]
    assert guilds.unregistered_players() == ["1"]
    assert guilds.register("1", "g")
    assert guilds.primary("1") == "g"
    assert players.all_ids() == ["1"]
    assert players.discord_id_for(players.token_for("1")) == "1"
