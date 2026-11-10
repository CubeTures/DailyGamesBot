"""Fermi: learn() guesses 1 three times and works each answer out from how
far off the results screen says that was (the answer shown on the reveal is
rounded: 1.2 shows as "1"). Guesses are whole numbers, so even the closest
scenario can be off by a bit. There's no losing: scenarios run from spot on
to far off."""

import math
import re

from playwright.sync_api import Locator

from tests.e2e.expect import approx, length, where
from tests.e2e.harness import Driver, Expected, Player, Solution


def _start(player: Player) -> None:
    player.page.get_by_role("button", name="Play Today's →").click()


def _guess(player: Player, n: int, guess: int) -> None:
    """Answer question n (0-2) with `guess`."""
    page = player.page
    if n:
        page.get_by_role("button", name=f"Question {n + 1} →").click()
    page.get_by_role("textbox", name="your guess").fill(str(guess))
    page.get_by_role("button", name=re.compile("Lock it in")).click()
    page.locator(".score-card.target .score-num").wait_for()


def _play(player: Player, guesses: list[int]) -> None:
    _start(player)
    for n, g in enumerate(guesses):
        _guess(player, n, g)
    player.page.get_by_role("button", name="See results →").click()


def _answer_from(factor: Locator) -> float:
    """The answer to a guess of 1, from its row on the results screen:
    "< 1.20×" (too low) means it's 1.2, "> 4.00×" (too high) 0.25."""
    value = float(re.sub(r"[^\d.]", "", factor.inner_text()))
    side = factor.locator("[aria-label]").first
    label = side.get_attribute("aria-label") if side.count() else ""
    return 1 / value if "too high" in (label or "") else value


def learn(player: Player) -> Solution:
    player.open()
    page = player.page
    _play(player, [1, 1, 1])
    factors = page.locator(".q-row .q-factor")
    factors.nth(2).wait_for()
    # Read here, not on the start screen: that can show yesterday's number
    # for a moment.
    number = int(page.get_by_text(re.compile(r"^No\. \d+$")).first.inner_text()[4:])
    return {
        "number": number,
        "answers": [_answer_from(factors.nth(n)) for n in range(3)],
    }


def _factor(guess: float, answer: float) -> float:
    return max(guess / answer, answer / guess)


def _whole(x: float) -> int:
    return max(1, round(x))


def _expected(solution: Solution, guesses: list[int]) -> Expected:
    answers = solution["answers"]
    factors = [_factor(g, a) for g, a in zip(guesses, answers, strict=True)]
    # The day's score: the geometric mean of the factors, each capped at 1,000×.
    score = math.prod(min(f, 1000) for f in factors) ** (1 / 3)
    sides = [
        "exact" if f < 1.005 else "high" if g > a else "low"
        for f, g, a in zip(factors, guesses, answers, strict=True)
    ]
    return {
        "puzzle_id": str(solution["number"]),
        "puzzle_number": solution["number"],
        # Shown rounded (to 3 significant figures or so).
        "score": approx(score, score * 0.02 + 0.01),
        "factors": where(
            f"≈ {[round(f, 2) for f in factors]}",
            lambda got: (
                length(3)(got)
                and all(
                    abs(g - f) <= f * 0.02 + 0.01
                    for g, f in zip(got, factors, strict=True)
                )
            ),
        ),
        "sides": where(
            f"{sides} (an exact guess may show either side)",
            lambda got: (
                length(3)(got)
                and all(w == "exact" or g == w for g, w in zip(got, sides, strict=True))
            ),
        ),
        "share_text": where("the share text", lambda t: t.startswith("Fermi · No.")),
    }


def win(player: Player, solution: Solution) -> Expected:
    """Each answer, to the nearest whole number."""
    guesses = [_whole(a) for a in solution["answers"]]
    _play(player, guesses)
    return _expected(solution, guesses)


def far_off(player: Player, solution: Solution) -> Expected:
    """Guess 1 every time (the learn run's guesses)."""
    guesses = [1, 1, 1]
    _play(player, guesses)
    return _expected(solution, guesses)


def mixed(player: Player, solution: Solution) -> Expected:
    a = solution["answers"]
    guesses = [_whole(a[0]), _whole(a[1] * 10), _whole(a[2] / 10)]
    _play(player, guesses)
    return _expected(solution, guesses)


DRIVER = Driver(
    name="fermi",
    learn=learn,
    scenarios={"win": win, "far_off": far_off, "mixed": mixed},
)
