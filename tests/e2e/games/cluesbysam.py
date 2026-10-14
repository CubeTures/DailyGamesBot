"""Clues by Sam: who's a criminal is in the cards' React props, but the game
only accepts a verdict once it's deducible (otherwise it's an error), so the
order matters too. learn() gets that order from the game's own hint: after
"Show hint", state.hint.reveals lists the cards identifiable right now.
"""

from typing import Any

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

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


def learn(player: Player) -> Solution:
    player.open()
    _start(player)
    criminals: list[bool] = player.page.evaluate(CRIMINALS)
    assert None not in criminals, "couldn't read the cards' verdicts"
    steps: list[list[int]] = []
    for _ in range(len(criminals)):
        if _state(player).get("completeTime"):
            break
        step = _hint(player)
        assert step, "the hint names no card to identify"
        for index in step:
            _guess(player, index, criminals[index])
        steps.append(step)
    return {
        "date": game_day(player.game).isoformat(),
        "criminals": criminals,
        # Cards to identify, a hint's worth at a time; each is deducible once
        # the ones before it are flipped.
        "steps": steps,
    }


def _play(
    player: Player, solution: Solution, *, wrong: int = 0, hints: int = 0
) -> None:
    """Identify every card in the learned order, getting the first `wrong`
    cards wrong once first, and pressing "Show hint" before the last `hints`
    steps."""
    criminals = solution["criminals"]
    steps = solution["steps"]
    _start(player)
    for n, step in enumerate(steps):
        if n >= len(steps) - hints:
            _hint(player)
        for index in step:
            if wrong:
                wrong -= 1
                _guess(player, index, not criminals[index])
            _guess(player, index, criminals[index])


def _expected(solution: Solution, mistakes: int, hints: int) -> Expected:
    return {
        "puzzle_id": solution["date"],
        "score": mistakes + hints,
        "mistakes": mistakes,
        "hints": hints,
        "double_hints": 0,
    }


def win(player: Player, solution: Solution) -> Expected:
    _play(player, solution)
    return _expected(solution, 0, 0) | {
        "rows": [":green_square:" * 4] * (len(solution["criminals"]) // 4)
    }


def hinted(player: Player, solution: Solution) -> Expected:
    """There's no losing; a hint at every step is the other end."""
    _play(player, solution, hints=len(solution["steps"]))
    return _expected(solution, 0, len(solution["steps"]))


def mixed(player: Player, solution: Solution) -> Expected:
    _play(player, solution, wrong=2, hints=1)
    return _expected(solution, 2, 1)


DRIVER = Driver(
    name="cluesbysam",
    learn=learn,
    scenarios={"win": win, "hinted": hinted, "mixed": mixed},
)
