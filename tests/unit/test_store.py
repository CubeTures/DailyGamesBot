import sqlite3
from datetime import date
from pathlib import Path

from src.store import hidden_games, players, results, subscriptions


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
    [stored] = results.on_day(date(2026, 10, 8))
    assert stored.player_name == "alice"
    assert results.on_day(date(2026, 10, 9)) == []


def test_announcing() -> None:
    results.save(_result("a"))
    results.save(_result("b"))
    first, second = results.unannounced()
    results.mark_announced(first.id)
    assert [r.id for r in results.unannounced()] == [second.id]


def test_players() -> None:
    assert players.add("1")
    assert not players.add("1")
    players.set_name("1", None)
    assert players.all_ids() == ["1"]


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
    assert [r.puzzle_id for r in results.on_day(date(2026, 1, 2))] == ["2026-01-02"]
    assert [r.puzzle_id for r in results.on_day(date(2026, 1, 3))] == ["77"]
    assert players.all_ids() == ["1"]
