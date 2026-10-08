"""Fermi: each question's answer is shown once it's guessed, so learn()
guesses 1 three times and reads them off. There's no losing: scenarios run
from spot on to far off."""

import math
import re

from tests.e2e.expect import approx, length, where
from tests.e2e.harness import Driver, Expected, Player, Solution

# Answers can be shown with a scale word ("1.2 billion").
SCALES = {"thousand": 1e3, "million": 1e6, "billion": 1e9, "trillion": 1e12}


def _number(text: str) -> float:
    match = re.match(r"\s*([\d.,]+)\s*([a-z]*)", text.lower())
    assert match, f"not a number: {text!r}"
    value = float(match[1].replace(",", ""))
    return value * SCALES.get(match[2], 1)


def _start(player: Player) -> None:
    player.page.get_by_role("button", name="Play Today's →").click()


def _guess(player: Player, n: int, guess: float) -> float:
    """Answer question n (0-2) with `guess`; returns the answer it reveals."""
    page = player.page
    if n:
        page.get_by_role("button", name=f"Question {n + 1} →").click()
    page.get_by_role("textbox", name="your guess").fill(f"{guess:g}")
    page.get_by_role("button", name=re.compile("Lock it in")).click()
    answer = page.locator(".score-card.target .score-num")
    answer.wait_for()
    return _number(answer.inner_text())


def _play(player: Player, guesses: list[float]) -> list[float]:
    _start(player)
    answers = [_guess(player, n, g) for n, g in enumerate(guesses)]
    player.page.get_by_role("button", name="See results →").click()
    return answers


def learn(player: Player) -> Solution:
    player.open()
    number = int(
        player.page.get_by_text(re.compile(r"^No\. \d+$")).first.inner_text()[4:]
    )
    return {"number": number, "answers": _play(player, [1, 1, 1])}


def _factor(guess: float, answer: float) -> float:
    return max(guess / answer, answer / guess)


def _expected(solution: Solution, guesses: list[float]) -> Expected:
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
    guesses = solution["answers"]
    _play(player, guesses)
    return _expected(solution, guesses)


def far_off(player: Player, solution: Solution) -> Expected:
    """Guess 1 every time (the learn run's guesses)."""
    guesses = [1.0, 1.0, 1.0]
    _play(player, guesses)
    return _expected(solution, guesses)


def mixed(player: Player, solution: Solution) -> Expected:
    a = solution["answers"]
    # Guesses are whole numbers.
    guesses: list[float] = [a[0], a[1] * 10, max(1, round(a[2] / 10))]
    _play(player, guesses)
    return _expected(solution, guesses)


DRIVER = Driver(
    name="fermi",
    learn=learn,
    scenarios={"win": win, "far_off": far_off, "mixed": mixed},
)
