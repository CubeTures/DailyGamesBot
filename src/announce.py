"""Turns a captured result into the Discord message announcing it.

Each game can have a games/<name>/announcement.j2 Jinja template (see
games/README.md for what's in scope); games without one use DEFAULT_TEMPLATE.
Preview one against made-up fields with:

    uv run python3 -m src.announce wordle '{"won": true, "score": 3, ...}'
"""

import logging
import re
from collections import Counter
from typing import Any, cast

from jinja2 import TemplateError
from jinja2.sandbox import SandboxedEnvironment

from src.games.models import Game
from src.store.results import StoredResult
from src.store.starts import StoredStart

DISCORD_MAX_LENGTH = 2000

log = logging.getLogger(__name__)

# Always in scope (None when the game doesn't report them), so templates can
# test `score is not none` without first checking it's defined.
STANDARD_FIELDS = ("won", "score", "max_score", "attempts", "time_secs", "share_text")

DEFAULT_TEMPLATE = """\
{{ player }} {{ "didn't solve" if won is false else "finished" }} **{{ game }}**
{{- " :fire: %d" % streak if streak > 1 }}
{%- if score is not none %} with {{ score }}
{%- if max_score is not none %}/{{ max_score }}{% endif %}{% endif %}
{%- if time_secs %} in {{ time_secs | duration }}{% endif %}
{{ "\n" + share_text if share_text }}
"""

# A co-op game's shared game, for one without an announcement.j2.
DEFAULT_COOP_TEMPLATE = """\
:sun_with_face: {{ players | length | plural("player") }} played **{{ game }}**
{{- " " + (title | md) if title }}
{% for p in players %}
{{ loop.index }}. {{ p.player }} {{ p.score }}
{% endfor %}
"""

# A co-op game someone started, for one without a started.j2.
DEFAULT_STARTED_TEMPLATE = """\
:sun_with_face: {{ player }} started **{{ game }}**{{ " " + (title | md) if title }}
Join them at {{ join_url }}
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


def plural(count: float, noun: str, nouns: str | None = None) -> str:
    """`count` and `noun`, plural unless it's 1: "1 hint", "3 guesses"."""
    return f"{count} {noun if count == 1 else nouns or noun + 's'}"


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
    duration=duration,
    tiles=tiles,
    md=md,
    spoiler=spoiler,
    plural=plural,
)


def check_template(template: str) -> None:
    """Raise ValueError if `template` isn't valid Jinja."""
    try:
        _env.parse(template)
    except TemplateError as e:
        raise ValueError(f"bad announcement template: {e}") from e


def mention(discord_id: str) -> str:
    return f"<@{discord_id}>"


def truncate(text: str, limit: int = DISCORD_MAX_LENGTH) -> str:
    """`text` cut to `limit` characters, ending in "…" if it was cut."""
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _render_first_working(
    templates: list[str], context: dict[str, Any], game_title: str
) -> str:
    for template in templates:
        try:
            return _env.from_string(template).render(context).strip()
        except Exception as e:
            log.warning("Announcement template for %s failed: %r", game_title, e)
    return ""


def render(
    game: Game,
    *,
    player: str,
    puzzle_id: str,
    fields: dict[str, Any],
    streak: int,
    game_mention: str | None = None,
) -> str:
    """The announcement text, falling back to DEFAULT_TEMPLATE if the game's
    template fails. `game_mention` (the game's role mention) stands in for
    the title as `game` when given. `streak` is the game days in a row the
    player has played it, this one included; templates show it from 2."""
    game_name = game_mention or game.title
    context = {
        **dict.fromkeys(STANDARD_FIELDS),
        **fields,
        # After the fields, so a field can't shadow these.
        "game": game_name,
        "player": player,
        "puzzle_id": puzzle_id,
        "streak": streak,
        "fields": fields,
    }
    templates = (
        [game.announcement_template] if game.announcement_template is not None else []
    )
    text = _render_first_working([*templates, DEFAULT_TEMPLATE], context, game.title)
    return truncate(text or f"{player} finished **{game_name}**")


def coop_players(game: Game, shared: list[StoredResult]) -> list[dict[str, Any]]:
    """Everyone in a co-op game's shared game, ranked by score: the roster
    in the results' `players` field (the fullest of them), each entry with
    `player` added, a mention for those whose result was captured (matched
    by their `player_id` field) and their escaped name for the rest, and
    `streak` (as for a result; None for the rest)."""
    captured = {
        str(r.data["player_id"]): r
        for r in shared
        if r.data.get("player_id") is not None
    }
    rosters: list[list[Any]] = [
        cast(list[Any], r.data["players"])
        for r in shared
        if isinstance(r.data.get("players"), list)
    ]
    roster = max(rosters, key=len) if rosters else []
    ranked: list[dict[str, Any]] = []
    for entry in roster:
        if not isinstance(entry, dict):
            continue
        fields = cast(dict[str, Any], entry)
        result = captured.get(str(fields.get("id")))
        name = fields.get("name") or "Someone"
        ranked.append(
            {
                **fields,
                "player": mention(result.discord_id) if result else md(name),
                "discord_id": result.discord_id if result else None,
                "streak": result.streak if result else None,
            }
        )
    sign = -1 if game.higher_score_wins else 1

    def rank(p: dict[str, Any]) -> tuple[bool, float]:
        """Scoreless last, then best score first."""
        score = p.get("score")
        if not isinstance(score, int | float):
            return (True, 0.0)
        return (False, sign * float(score))

    return sorted(ranked, key=rank)


def render_coop(
    game: Game, shared: list[StoredResult], game_mention: str | None = None
) -> str:
    """The announcement of a co-op game's shared game, from every captured
    result of it: the first one's fields, with `players` ranked (see
    coop_players)."""
    game_name = game_mention or game.title
    first = shared[0]
    context = {
        **dict.fromkeys(STANDARD_FIELDS),
        **first.data,
        "game": game_name,
        "puzzle_id": first.puzzle_id,
        "players": coop_players(game, shared),
        "fields": first.data,
    }
    templates = (
        [game.announcement_template] if game.announcement_template is not None else []
    )
    text = _render_first_working(
        [*templates, DEFAULT_COOP_TEMPLATE], context, game.title
    )
    return truncate(text or f"**{game_name}** was solved")


def render_started(
    game: Game, start: StoredStart, join_url: str, game_mention: str | None = None
) -> str:
    """The post that a player started a co-op game, with `join_url` to join."""
    game_name = game_mention or game.title
    context = {
        **start.data,
        "game": game_name,
        "player": mention(start.discord_id),
        "puzzle_id": start.puzzle_id,
        "join_url": join_url,
        "fields": start.data,
    }
    templates = [game.started_template] if game.started_template is not None else []
    text = _render_first_working(
        [*templates, DEFAULT_STARTED_TEMPLATE], context, game.title
    )
    return truncate(text or f"{mention(start.discord_id)} started **{game_name}**")


def render_result(
    game: Game, result: StoredResult, game_mention: str | None = None
) -> str:
    return render(
        game,
        player=mention(result.discord_id),
        puzzle_id=result.puzzle_id,
        fields=result.data,
        game_mention=game_mention,
        streak=result.streak,
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
            streak=fields.get("streak", 1),
        )
    )


if __name__ == "__main__":
    main()
