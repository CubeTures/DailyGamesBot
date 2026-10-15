"""TimeGuessr: five photos, each guessed by a pin on the map and a year. The
daily's photos, with their years, are in localStorage tg_progress_daily as
soon as it opens, so learn() reads them there. There's no losing; scenarios
set the year exactly or far off and drop the pin wherever the map's centre is,
so only the year part of each round's score is known."""

import re
from typing import Any

from tests.e2e.expect import between, length, where
from tests.e2e.harness import Driver, Expected, Player, Solution

ROUNDS = 5
# The year slider's range.
FIRST_YEAR, LAST_YEAR = 1900, 2026


def _progress(player: Player) -> dict[str, Any] | None:
    return player.page.evaluate(
        "() => JSON.parse(localStorage.getItem('tg_progress_daily') || 'null')"
    )


def _open(player: Player) -> None:
    player.open()
    player.page.get_by_role("slider").wait_for()


def learn(player: Player) -> Solution:
    _open(player)
    progress = _progress(player)
    assert progress, "no tg_progress_daily"
    # playArray ends with a {scoringVersion} entry that isn't a photo.
    photos = [p for p in progress["playArray"] if "Year" in p]
    assert len(photos) == ROUNDS, photos
    return {
        "number": int(progress["dailyNumber"]),
        "years": [int(p["Year"]) for p in photos],
    }


def _guess(player: Player, year: int) -> None:
    page = player.page
    page.get_by_role("slider").fill(str(year))
    guess = page.get_by_role("button", name="Make guess")
    # The map takes clicks once MapKit has started.
    for _ in range(20):
        page.locator(".mk-map-view:visible").click()
        if guess.is_visible():
            break
        page.wait_for_timeout(500)
    guess.click()


def _play(player: Player, years: list[int]) -> None:
    _open(player)
    page = player.page
    for n, year in enumerate(years):
        if n:
            page.get_by_role("button", name="Next Round").click()
            page.get_by_role("button", name="Place your pin on the map").wait_for()
        _guess(player, year)
    page.get_by_role("button", name="Final Score").click()
    page.wait_for_url(re.compile(r"/final-score"))


def _expected(solution: Solution, guesses: list[int]) -> Expected:
    off = [abs(g - y) for g, y in zip(guesses, solution["years"], strict=True)]
    exact = off.count(0)
    year_bars = [
        ":date:" + ":green_square:" * 3
        if o == 0
        else ":date:" + ":black_large_square:" * 3
        for o in off
    ]
    return {
        "puzzle_id": str(solution["number"]),
        "puzzle_number": solution["number"],
        # Each exact year is 5,000; the pins land anywhere.
        "score": between(exact * 5000, exact * 5000 + ROUNDS * 5000),
        "max_score": 50000,
        "exact_years": exact,
        "rounds": where(
            f"5 rounds, {off} years off",
            lambda rounds: (
                length(ROUNDS)(rounds)
                and [r["years_off"] for r in rounds] == off
                and all(
                    r["year_score"] == 5000
                    for r, o in zip(rounds, off, strict=True)
                    if o == 0
                )
                and all(
                    r["score"] == r["place_score"] + r["year_score"] for r in rounds
                )
            ),
        ),
        "rows": where(
            f"5 rows ending {year_bars}",
            lambda rows: (
                length(ROUNDS)(rows)
                and all(
                    row.startswith(":earth_americas:") and row.endswith(bar)
                    for row, bar in zip(rows, year_bars, strict=True)
                )
            ),
        ),
    }


def exact_years(player: Player, solution: Solution) -> Expected:
    guesses = solution["years"]
    _play(player, guesses)
    return _expected(solution, guesses)


def far_off(player: Player, solution: Solution) -> Expected:
    """Each year at whichever end of the slider is further from it, which is
    always over 20 years off (no year green)."""
    guesses = [
        FIRST_YEAR if y - FIRST_YEAR > LAST_YEAR - y else LAST_YEAR
        for y in solution["years"]
    ]
    _play(player, guesses)
    return _expected(solution, guesses)


DRIVER = Driver(
    name="timeguessr",
    learn=learn,
    scenarios={"exact_years": exact_years, "far_off": far_off},
)
