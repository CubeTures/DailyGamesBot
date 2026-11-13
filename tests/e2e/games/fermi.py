"""Fermi: three questions, each answered with a number. There's no losing, so
the driver guesses 1 every time and needs no answers. The result is checked
against the results screen and for adding up: the score is the geometric mean
of the three factors (each capped at 1,000×), as shown rounded."""

import math
import re
from typing import Any

from tests.e2e.expect import ALL, length, where
from tests.e2e.harness import Driver, Expected, Player, Solution

QUESTIONS = 3


def _guess(player: Player, n: int) -> None:
    """Answer question n (0-2) with 1."""
    page = player.page
    if n:
        page.get_by_role("button", name=f"Question {n + 1} →").click()
    page.get_by_role("textbox", name="your guess").fill("1")
    page.get_by_role("button", name=re.compile("Lock it in")).click()
    page.locator(".score-card.target .score-num").wait_for()


def _adds_up(fields: dict[str, Any]) -> bool:
    factors = fields["factors"]
    score = math.prod(min(f, 1000) for f in factors) ** (1 / QUESTIONS)
    return abs(fields["score"] - score) <= score * 0.02 + 0.01


def play(player: Player, _solution: Solution) -> Expected:
    page = player.page
    page.get_by_role("button", name="Play Today's →").click()
    for n in range(QUESTIONS):
        _guess(player, n)
    page.get_by_role("button", name="See results →").click()
    page.locator(".q-row .q-factor").nth(QUESTIONS - 1).wait_for()
    # Read here, not on the start screen: that can show yesterday's number
    # for a moment.
    number = int(page.get_by_text(re.compile(r"^No\. \d+$")).first.inner_text()[4:])
    return {
        "puzzle_id": str(number),
        "puzzle_number": number,
        "factors": where(
            f"{QUESTIONS} factors ≥ 1",
            lambda got: length(QUESTIONS)(got) and all(f >= 1 for f in got),
        ),
        "sides": where(
            f"{QUESTIONS} of high/low/exact",
            lambda got: (
                length(QUESTIONS)(got)
                and all(s in ("high", "low", "exact") for s in got)
            ),
        ),
        "share_text": where(
            f"the share text for No. {number}",
            lambda t: t.startswith(f"Fermi · No. {number:03d}"),
        ),
        ALL: where("score the geometric mean of the factors", _adds_up),
    }


DRIVER = Driver(name="fermi", play=play)
