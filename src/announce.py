"""Turns a captured result into the Discord message announcing it.

Each game can have a games/<name>/announcement.j2 Jinja template (see
games/README.md for what's in scope); games without one use DEFAULT_TEMPLATE. Preview
one against made-up fields with:

    uv run python3 -m src.announce wordle '{"won": true, "score": 3, ...}'
"""

from collections import Counter
from typing import Any, cast

from jinja2 import TemplateError
from jinja2.sandbox import SandboxedEnvironment

# Discord rejects longer messages.
MAX_LENGTH = 2000

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
    minutes, s = divmod(round(secs), 60)
    h, m = divmod(minutes, 60)
    return f"{h}:{m:02}:{s:02}" if h else f"{m}:{s:02}"


def tiles(guess: str, answer: str) -> str:
    """A Wordle-style emoji row scoring `guess` against `answer`."""
    guess, answer = guess.upper(), answer.upper()
    row = ["⬛"] * len(guess)
    # Letters of the answer not matched exactly; each can light one 🟨.
    unmatched = Counter(a for g, a in zip(guess, answer, strict=False) if g != a)
    for i, g in enumerate(guess):
        if i < len(answer) and g == answer[i]:
            row[i] = "🟩"
        elif unmatched[g] > 0:
            row[i] = "🟨"
            unmatched[g] -= 1
    return "".join(row)


# Sandboxed: templates only format data, they shouldn't reach into Python.
_env = SandboxedEnvironment(trim_blocks=True, lstrip_blocks=True)
# Jinja types this dict as holding only its built-in filters.
cast(dict[str, Any], _env.filters).update(duration=duration, tiles=tiles)


def check(template: str) -> str:
    """Raise ValueError if `template` isn't valid Jinja."""
    try:
        _env.parse(template)
    except TemplateError as e:
        raise ValueError(f"bad announcement template: {e}") from e
    return template


def render(
    template: str | None,
    *,
    game: str,
    player: str,
    puzzle_id: str,
    fields: dict[str, Any],
) -> str:
    """The announcement text; falls back to DEFAULT_TEMPLATE if `template` fails."""
    context = {
        **dict.fromkeys(STANDARD_FIELDS),
        **fields,
        # After the fields, so a field can't shadow these.
        "game": game,
        "player": player,
        "puzzle_id": puzzle_id,
        "fields": fields,
    }
    text = ""
    for source in (template, DEFAULT_TEMPLATE):
        if source is None:
            continue
        try:
            text = _env.from_string(source).render(context).strip()
        except Exception as e:
            print(f"Announcement template for {game} failed: {e!r}")
            continue
        break
    if not text:
        text = f"{player} finished **{game}**"
    if len(text) > MAX_LENGTH:
        text = text[: MAX_LENGTH - 1] + "…"
    return text


if __name__ == "__main__":
    import json
    import sys

    from src.proxy.config import GAME_CONFIGS

    by_name = {g.name: g for g in GAME_CONFIGS.values()}
    if len(sys.argv) != 3 or sys.argv[1] not in by_name:
        sys.exit(
            f"usage: python -m src.announce <{'|'.join(sorted(by_name))}>"
            " '<fields as JSON>'"
        )
    config = by_name[sys.argv[1]]
    sample: dict[str, Any] = json.loads(sys.argv[2])
    print(
        render(
            config.announcement,
            game=config.title,
            player="@player",
            puzzle_id=str(sample.get("puzzle_id", "")),
            fields=sample,
        )
    )
