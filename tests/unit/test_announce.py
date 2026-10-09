from datetime import UTC, datetime

from src import announce
from src.games.registry import GAMES_BY_NAME
from src.store.results import StoredResult

WORDLE = GAMES_BY_NAME["wordle"]


def test_duration() -> None:
    assert announce.duration(None) == ""
    assert announce.duration(5) == "0:05"
    assert announce.duration(65.4) == "1:05"
    assert announce.duration(3723) == "1:02:03"


def test_tiles_scores_repeated_letters_once() -> None:
    assert announce.tiles("crane", "crane") == "🟩" * 5
    assert announce.tiles("eerie", "there") == "🟨⬛🟨⬛🟩"
    assert announce.tiles("abc", "xyz") == "⬛⬛⬛"


def test_md_and_spoiler_escape_markdown() -> None:
    assert announce.md("a *b*\n_c_ <@1>") == r"a \*b\* \_c\_ \<@1\>"
    assert announce.spoiler("x|y") == r"||x\|y||"


def test_render_default_template() -> None:
    game = WORDLE.model_copy(update={"announcement_template": None})
    text = announce.render(
        game,
        player="@p",
        puzzle_id="1",
        fields={"won": True, "score": 3, "max_score": 6, "time_secs": 65},
    )
    assert text == "@p finished **Wordle** with 3/6 in 1:05"


def test_render_falls_back_when_template_fails() -> None:
    game = WORDLE.model_copy(update={"announcement_template": "{{ 1 / 0 }}"})
    text = announce.render(game, player="@p", puzzle_id="1", fields={"won": False})
    assert text == "@p didn't solve **Wordle**"


def test_render_truncates_to_discord_limit() -> None:
    game = WORDLE.model_copy(update={"announcement_template": "{{ 'x' * 3000 }}"})
    text = announce.render(game, player="@p", puzzle_id="1", fields={})
    assert len(text) == announce.DISCORD_MAX_LENGTH
    assert text.endswith("…")


def test_render_result_uses_game_mention() -> None:
    game = WORDLE.model_copy(update={"announcement_template": None})
    result = StoredResult(
        id=1,
        game="wordle",
        discord_id="42",
        player_name=None,
        puzzle_id="1",
        data={},
        captured_at=datetime.now(UTC),
    )
    text = announce.render_result(game, result, game_mention="<@&9>")
    assert text == "<@42> finished **<@&9>**"
