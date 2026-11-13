"""Clues by Sam: who's a criminal is in the cards' React props, but the game
only accepts a verdict once it's deducible (otherwise it's an error), so the
order matters too. The game's own hint gives it: after "Show hint",
state.hint.reveals lists the cards identifiable right now. There's no losing,
so the driver takes a hint at every step and gets the first card wrong once.
"""

import math
from typing import Any

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from tests.e2e.expect import where
from tests.e2e.harness import Driver, Expected, Player, Solution
from tests.e2e.solutions import game_day

# Each card's `criminal` flag, from the React props of its grid cell.
CRIMINALS = """() => [...document.querySelectorAll(".card")].map(c => {
  let f = c[Object.keys(c).find(k => k.startsWith("__reactFiber"))];
  while (f && !(f.memoizedProps && "card" in f.memoizedProps)) f = f.return;
  return f?.memoizedProps.card.criminal ?? null;
})"""


def _state(player: Player) -> dict[str, Any]:
    day = game_day(player.game).isoformat()
    return (
        player.page.evaluate(f"JSON.parse(localStorage.getItem('state-{day}'))") or {}
    )


def _start(player: Player) -> None:
    page = player.page
    player.dismiss(page.get_by_role("button", name="Continue"))
    page.get_by_role("button", name="Start").click()
    page.locator(".card").first.wait_for()


def _guess(player: Player, index: int, criminal: bool) -> None:
    page = player.page
    page.locator(".card").nth(index).click()
    verdict = page.get_by_role("button", name="Criminal" if criminal else "Innocent")
    # The card's dialog ignores clicks for a moment after it opens; a verdict
    # it takes, right or wrong, closes it.
    page.wait_for_timeout(300)
    for _ in range(5):
        verdict.click()
        try:
            verdict.wait_for(state="hidden", timeout=1000)
            break
        except PlaywrightTimeoutError:
            pass
    else:
        raise AssertionError(f"card {index}'s dialog didn't take the verdict")
    page.wait_for_timeout(700)


def _hint(player: Player) -> list[int]:
    """Press "Show hint"; the cards it says can be identified now."""
    player.page.get_by_role("button", name="Show hint").click()
    player.page.wait_for_timeout(500)
    state = _state(player)
    hint: dict[str, Any] | None = state.get("hint")
    assert hint, "no hint in the game's state"
    flipped: list[int] = state.get("flippedCards") or []
    # It can name cards already flipped, too.
    return [i for i in hint["reveals"] if i not in flipped]


def play(player: Player, _solution: Solution) -> Expected:
    _start(player)
    criminals: list[bool] = player.page.evaluate(CRIMINALS)
    assert None not in criminals, "couldn't read the cards' verdicts"
    hints = 0
    wrong = 1
    for _ in range(len(criminals)):
        if _state(player).get("completeTime"):
            break
        step = _hint(player)
        hints += 1
        assert step, "the hint names no card to identify"
        for index in step:
            if wrong:
                wrong -= 1
                _guess(player, index, not criminals[index])
            _guess(player, index, criminals[index])
    width = 4
    # The game's own solve time, which its results screen shows rounded up.
    complete_ms: int = _state(player)["completeTime"]
    return {
        "puzzle_id": game_day(player.game).isoformat(),
        "score": 1 + hints,
        "mistakes": 1,
        "hints": hints,
        "double_hints": 0,
        "time_secs": math.ceil(complete_ms / 1000),
        "rows": where(
            f"{len(criminals) // width} rows of {width}, not all green",
            lambda rows: (
                len(rows) == len(criminals) // width
                and all(r.count(":") == 2 * width for r in rows)
                and any(r != ":green_square:" * width for r in rows)
            ),
        ),
    }


DRIVER = Driver(name="cluesbysam", play=play)
