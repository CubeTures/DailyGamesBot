"""Bracket City: there's no losing and no answer list anywhere, so the driver
makes one wrong guess and then reveals every clue (peek, then reveal), the
surest way to the end.

The game runs in an iframe of The Atlantic's page, where the site's sticky
header covers it, so this plays the iframe's own page. That's the frame that
reports (see vars.js); the outer page only adds a second, silent copy of the
capture script.
"""

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

# A wrong guess; it costs 2 points.
WRONG = "qzxj"

# The game's ranks and the score each needs.
RANKS = [
    ("Kingmaker", 100),
    ("Power Broker", 90),
    ("Mayor", 80),
    ("Chief of Police", 65),
    ("Council Member", 45),
    ("Resident", 20),
    ("Commuter", 10),
]

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


def _css(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _wrong_guess(player: Player, game: Page) -> None:
    """Type a wrong answer. The first keystroke starts the puzzle (saving its
    state) and re-renders, clearing the box, so get that out of the way
    first."""
    box = game.get_by_role("textbox", name="Answer")
    box.focus()
    player.page.keyboard.press("a")
    player.page.wait_for_function(f"({STATE})()?.progress === 'inProgress'")
    box.fill("")
    box.focus()
    player.page.keyboard.type(WRONG, delay=30)
    # The Enter key doesn't submit here; the on-page button does.
    game.get_by_role("button", name="[enter]").click()
    player.page.wait_for_timeout(600)


def play(player: Player, _solution: Solution) -> Expected:
    game = _start(player)
    _wrong_guess(player, game)
    clues = 0
    for expression in _clues(game):
        # Peek at its first letter, then reveal it.
        _click_clue(player, game, expression)
        _click_clue(player, game, expression)
        clues += 1
    day = game_day(player.game)
    score = max(0, 100 - 2 - 20 * clues)
    return {
        "puzzle_id": day.isoformat(),
        "puzzle_number": (day - date(2025, 4, 8)).days + 1,
        # 100, less 2 for the wrong guess and 5 + 15 per clue, floored at 0.
        "score": score,
        "max_score": 100,
        "rank": next((r for r, low in RANKS if score >= low), "Tourist"),
        "hard_mode": False,
        "wrong_guesses": 1,
        "peeks": clues,
        "reveals": clues,
        "keystrokes": where("a number > 0", lambda k: k > 0),
        "min_keystrokes": where("a number > 0", lambda k: k > 0),
    }


DRIVER = Driver(name="bracketcity", play=play)
