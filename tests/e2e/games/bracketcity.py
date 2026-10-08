"""Bracket City: there's no answer list anywhere, so learn() reveals every
clue (peek, then reveal) and reads each answer off the puzzle text: the
clue's "[expression]" is replaced by its answer in the game's displayState.

The game runs in an iframe of The Atlantic's page, where the site's sticky
header covers it, so this plays the iframe's own page. That's the frame that
reports (see vars.js); the outer page only adds a second, silent copy of the
capture script.
"""

import re
from collections.abc import Iterator
from contextlib import suppress
from datetime import date

from playwright.sync_api import Page

from tests.e2e.expect import where
from tests.e2e.harness import Driver, Expected, Player, Solution
from tests.e2e.solutions import game_day

STATE = """() => JSON.parse(localStorage.getItem(
  Object.keys(localStorage).find(k => k.startsWith("bracketPuzzle_")) ?? "") ?? "null")"""


EMBED_PATH = "/games-embed/bracket-city/"

# Wrong guesses; each costs 2 points.
WRONG = ["zzz", "qzx", "xqj", "jjjj"]

# A clue that hasn't gone after this many tries means the driver is stuck.
MAX_STEPS = 60


def _start(player: Player) -> Page:
    game = player.page
    if EMBED_PATH not in game.url:
        game.goto(player.url(EMBED_PATH))
    answer = game.get_by_role("textbox", name="Answer")
    # The Atlantic occasionally fails a load (blank page); one reload fixes it.
    try:
        answer.wait_for(timeout=20000)
    except Exception:
        game.reload()
        answer.wait_for()
    # The welcome dialog opens for new players. Typing (unlike clicking)
    # doesn't wait for overlay handlers, so close it before anything is typed.
    welcome = game.get_by_role("alertdialog").get_by_role("button", name="Close")
    with suppress(Exception):
        welcome.click(timeout=5000)
    return game


def _click_clue(player: Player, game: Page, expression: str) -> None:
    """Click a clue (peek at its first letter, or reveal it once peeked) and
    confirm the "You sure you want to peek...?" prompt."""
    game.locator(f'[data-expression="{_css(expression)}"]').first.click()
    ok = game.get_by_role("dialog").get_by_role("button", name="OK")
    ok.click(timeout=5000)
    player.page.wait_for_timeout(500)


def _active_clue(game: Page) -> str | None:
    clue = game.locator(".active-clue[data-expression]").first
    return clue.get_attribute("data-expression", timeout=3000) if clue.count() else None


def _text(state: dict[str, object]) -> str:
    html = state.get("displayState") or state["initialPuzzle"]
    return re.sub(r"<[^>]+>", "", str(html))


def _replaced(before: str, after: str, expression: str) -> str:
    """What `[expression]` in `before` became in `after`."""
    target = f"[{expression}]"
    start = before.index(target)
    suffix = before[start + len(target) :]
    assert after.startswith(before[:start]) and after.endswith(suffix)
    return after[start : len(after) - len(suffix)]


def _state(player: Player) -> dict[str, object]:
    return player.page.evaluate(STATE)


def _clues(game: Page) -> Iterator[str]:
    """Each active clue in turn, until there are none left."""
    last = None
    for _ in range(MAX_STEPS):
        expression = _active_clue(game)
        if expression is None:
            return
        assert expression != last, f"clue {expression!r} didn't clear"
        last = expression
        yield expression
    raise AssertionError(f"still clues left after {MAX_STEPS}")


def _reveal_all(player: Player) -> dict[str, str]:
    """Peek and reveal every clue, innermost first; returns each answer."""
    game = _start(player)
    answers: dict[str, str] = {}
    for expression in _clues(game):
        # Peek (which also saves the state the first time), then reveal.
        _click_clue(player, game, expression)
        before = _text(_state(player))
        _click_clue(player, game, expression)
        answers[expression] = _replaced(before, _text(_state(player)), expression)
    return answers


def _css(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def learn(player: Player) -> Solution:
    player.open(EMBED_PATH)
    answers = _reveal_all(player)
    assert answers, "revealed nothing"
    return {"date": game_day(player.game).isoformat(), "answers": answers}


def _type(player: Player, game: Page, text: str) -> None:
    box = game.get_by_role("textbox", name="Answer")
    box.focus()
    player.page.keyboard.type(text, delay=30)
    # The Enter key doesn't submit here; the on-page button does.
    game.get_by_role("button", name="[enter]").click()
    player.page.wait_for_timeout(600)


def _solve(
    player: Player, solution: Solution, *, wrong: int = 0, peeks: int = 0
) -> None:
    """Type each active clue's answer; first `wrong` wrong guesses, and peek at
    the first `peeks` clues before answering them."""
    game = _start(player)
    # The first keystroke starts the puzzle (saving its state) and re-renders,
    # clearing the box; get that out of the way before typing for real.
    game.get_by_role("textbox", name="Answer").focus()
    player.page.keyboard.press("a")
    player.page.wait_for_function(f"({STATE})()?.progress === 'inProgress'")
    game.get_by_role("textbox", name="Answer").fill("")
    answers = {a.lower() for a in solution["answers"].values()}
    for guess in [w for w in WRONG if w not in answers][:wrong]:
        _type(player, game, guess)
    for expression in _clues(game):
        if peeks:
            peeks -= 1
            _click_clue(player, game, expression)
        _type(player, game, solution["answers"][expression])


def _expected(
    solution: Solution, score: float, rank: object, **counts: int
) -> Expected:
    number = (date.fromisoformat(solution["date"]) - date(2025, 4, 8)).days + 1
    return {
        "puzzle_id": solution["date"],
        "puzzle_number": number,
        "score": score,
        "max_score": 100,
        "rank": rank,
        "hard_mode": False,
        **counts,
    }


def win(player: Player, solution: Solution) -> Expected:
    _solve(player, solution)
    return _expected(
        solution,
        100,
        where(
            "Puppet Master (or Kingmaker if keystrokes were over the minimum)",
            lambda r: r in ("Puppet Master", "Kingmaker"),
        ),
        wrong_guesses=0,
        peeks=0,
        reveals=0,
    )


def reveal_all(player: Player, solution: Solution) -> Expected:
    """There's no losing; revealing everything is the worst result."""
    _reveal_all(player)
    clues = len(solution["answers"])
    return _expected(
        solution, 0, "Tourist", wrong_guesses=0, peeks=clues, reveals=clues
    )


def mixed(player: Player, solution: Solution) -> Expected:
    _solve(player, solution, wrong=2, peeks=1)
    # 100, minus 2 per wrong guess and 5 per peek.
    return _expected(solution, 91, "Power Broker", wrong_guesses=2, peeks=1, reveals=0)


DRIVER = Driver(
    name="bracketcity",
    learn=learn,
    scenarios={"win": win, "reveal_all": reveal_all, "mixed": mixed},
)
