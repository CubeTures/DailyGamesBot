"""Turns a captured result into the Discord message announcing it.

Each game can have a games/<name>/announcement.j2 Jinja template (see
games/README.md for what's in scope); games without one use DEFAULT_TEMPLATE.
Preview one against made-up fields with:

    uv run python3 -m src.announce wordle '{"won": true, "score": 3, ...}'
"""

import re
from collections import Counter
from typing import Any, cast

from jinja2 import TemplateError
from jinja2.sandbox import SandboxedEnvironment

from src.games.models import Game
from src.results import StoredResult

DISCORD_MAX_LENGTH = 2000

# Always in scope (None when the game doesn't report them), so templates can
# test `score is not none` without first checking it's defined.
STANDARD_FIELDS = ("won", "score", "max_score", "attempts", "time_secs", "share_text")

DEFAULT_TEMPLATE = """\
{{ player }} {{ "didn't solve" if won is false else "finished" }} **{{ game }}**
{%- if score is not none %} with {{ score }}
{%- if max_score is not none %}/{{ max_score }}{% endif %}{% endif %}
{%- if time_secs %} in {{ time_secs | duration }}{% endif %}
{{ "\n" + share_text if share_text }}
"""


def duration(secs: float | None) -> str:
    """Seconds as "1:05" or "1:02:03"."""
    if secs is None:
        return ""
    total_minutes, seconds = divmod(round(secs), 60)
    hours, minutes = divmod(total_minutes, 60)
    return f"{hours}:{minutes:02}:{seconds:02}" if hours else f"{minutes}:{seconds:02}"


def tiles(guess: str, answer: str) -> str:
    """A Wordle-style emoji row scoring `guess` against `answer`."""
    guess, answer = guess.upper(), answer.upper()
    row = ["⬛"] * len(guess)
    # Letters of the answer not matched exactly; each can light one 🟨.
    unmatched = Counter(a for g, a in zip(guess, answer, strict=False) if g != a)
    for i, letter in enumerate(guess):
        if i < len(answer) and letter == answer[i]:
            row[i] = "🟩"
        elif unmatched[letter] > 0:
            row[i] = "🟨"
            unmatched[letter] -= 1
    return "".join(row)


# Characters Discord reads as markdown, mentions or emoji shortcodes.
_MARKDOWN_RE = re.compile(r"([\\*_~`|<>:\[\]])")


def md(value: object) -> str:
    """`value` on one line with its markdown escaped, so text a player typed
    shows as typed."""
    return _MARKDOWN_RE.sub(r"\\\1", " ".join(str(value).split()))


def spoiler(value: object) -> str:
    """`value` as a Discord ||spoiler||, escaped as by `md`."""
    return f"||{md(value)}||"


# Sandboxed: templates only format data, they shouldn't reach into Python.
_env = SandboxedEnvironment(trim_blocks=True, lstrip_blocks=True)
# Jinja types this dict as holding only its built-in filters.
cast(dict[str, Any], _env.filters).update(
    duration=duration, tiles=tiles, md=md, spoiler=spoiler
)


def check_template(template: str) -> None:
    """Raise ValueError if `template` isn't valid Jinja."""
    try:
        _env.parse(template)
    except TemplateError as e:
        raise ValueError(f"bad announcement template: {e}") from e


def mention(discord_id: str) -> str:
    return f"<@{discord_id}>"


def _render_first_working(
    templates: list[str], context: dict[str, Any], game_title: str
) -> str:
    for template in templates:
        try:
            return _env.from_string(template).render(context).strip()
        except Exception as e:
            print(f"Announcement template for {game_title} failed: {e!r}")
    return ""


def render(
    game: Game,
    *,
    player: str,
    puzzle_id: str,
    fields: dict[str, Any],
    game_mention: str | None = None,
) -> str:
    """The announcement text, falling back to DEFAULT_TEMPLATE if the game's
    template fails. `game_mention` (the game's role mention) stands in for
    the title as `game` when given."""
    game_name = game_mention or game.title
    context = {
        **dict.fromkeys(STANDARD_FIELDS),
        **fields,
        # After the fields, so a field can't shadow these.
        "game": game_name,
        "player": player,
        "puzzle_id": puzzle_id,
        "fields": fields,
    }
    templates = (
        [game.announcement_template] if game.announcement_template is not None else []
    )
    text = _render_first_working([*templates, DEFAULT_TEMPLATE], context, game.title)
    text = text or f"{player} finished **{game_name}**"
    if len(text) > DISCORD_MAX_LENGTH:
        text = text[: DISCORD_MAX_LENGTH - 1] + "…"
    return text


def render_result(
    game: Game, result: StoredResult, game_mention: str | None = None
) -> str:
    return render(
        game,
        player=mention(result.discord_id),
        puzzle_id=result.puzzle_id,
        fields=result.data,
        game_mention=game_mention,
    )


def main() -> None:
    import json

    from src.games.registry import game_from_argv

    game, [fields_json] = game_from_argv("src.announce", "'<fields as JSON>'")
    fields: dict[str, Any] = json.loads(fields_json)
    print(
        render(
            game,
            player="@player",
            puzzle_id=str(fields.get("puzzle_id", "")),
            fields=fields,
        )
    )


if __name__ == "__main__":
    main()
