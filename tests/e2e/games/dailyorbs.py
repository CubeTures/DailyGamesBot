"""Daily Orbs: four puzzles a day in varying formats; six orbs win the day.
The game-day API lists every puzzle with its answers, so learn() just reads
it. Winning plays two "bijection" (match column A to column B) puzzles to
the end, three orbs each; losing gives up on all four, which works in any
format. A day with fewer than two bijection puzzles skips the winning
scenarios.
"""

import datetime as dt
from typing import Any

import pytest

from tests.e2e.harness import Driver, Expected, Player, Solution

API = "/__host/api.dailyorbs.com/api"
FIRST_DAY = dt.date(2026, 4, 17)
COLORS = ["orange", "purple", "green", "blue"]


def learn(player: Player) -> Solution:
    response = player.context.request.get(player.url(f"{API}/game-day"))
    assert response.ok, f"Daily Orbs API: {response.status}"
    data = response.json()
    puzzles = data["puzzles"]
    return {
        "date": data["dateKey"],
        "puzzles": [
            {
                "id": puzzles[c]["id"],
                "color": c,
                "type": puzzles[c]["type"],
                # itemA -> itemB, as the game stores them
                "pairs": {p["itemA"]: p["itemB"] for p in puzzles[c].get("pairs", [])},
            }
            for c in COLORS
            if c in puzzles
        ],
    }


def _day_state(player: Player, date: str) -> dict[str, Any]:
    return player.page.evaluate(
        "(key) => JSON.parse(localStorage.getItem(key) || 'null')", f"daily-orbs-{date}"
    )


def _open(player: Player, puzzle: dict[str, Any]) -> None:
    page = player.page
    page.goto(player.url(f"/{puzzle['id']}"))
    # The 6-orb "Victory" modal.
    player.dismiss(page.get_by_role("button", name="Yay", exact=True))
    # All four puzzles are mounted side by side; only the open one is visible.
    page.get_by_role("button", name="Reveal Answers").filter(visible=True).wait_for()


def _bijection(player: Player, date: str, puzzle: dict[str, Any], wrong: int) -> None:
    """Match every pair, after `wrong` mismatches (a heart each)."""
    page = player.page
    _open(player, puzzle)
    pid = puzzle["id"]
    page.wait_for_function(
        "([key, id]) => JSON.parse(localStorage.getItem(key) || 'null')"
        "?.snapshots?.[id]?.bijectionShuffledB?.length > 0",
        arg=[f"daily-orbs-{date}", pid],
    )
    # The cards' on-screen order; matched ones are removed from both columns.
    snapshot = _day_state(player, date)["snapshots"][pid]
    column_a: list[str] = snapshot["bijectionShuffledA"]
    column_b: list[str] = snapshot["bijectionShuffledB"]
    slots_a = page.locator(".bijection-blob-a:visible .bijection-card-slot")
    slots_b = page.locator(".bijection-blob-b:visible .bijection-card-slot")

    def pick(a: str, b: str) -> None:
        slots_a.nth(column_a.index(a)).locator(".bijection-card").click()
        slot = slots_b.nth(column_b.index(b))
        # Media cards (images, video) have a separate select button.
        select = slot.locator(".bijection-card-select")
        (select if select.count() else slot.locator(".bijection-card")).click()
        page.wait_for_timeout(600)

    def orbs() -> int:
        state = _day_state(player, date)
        return next(p["orbs"] for p in state["puzzles"] if p["puzzleId"] == pid)

    pairs: dict[str, str] = puzzle["pairs"]
    for _ in range(wrong):
        a = column_a[0]
        pick(a, next(b for b in column_b if b != pairs[a]))
    # The third orb can come before the last pair (starThresholds), and once
    # the day is won the board stops taking picks.
    while column_a and orbs() < 3:
        a = column_a[0]
        b = pairs[a]
        pick(a, b)
        column_a.remove(a)
        column_b.remove(b)
    assert orbs() == 3, f"driver problem: {pid} ended with {orbs()} orbs, not 3"


def _give_up(player: Player, puzzle: dict[str, Any]) -> None:
    page = player.page
    _open(player, puzzle)
    page.get_by_role("button", name="Reveal Answers").filter(visible=True).click()
    page.get_by_role("button", name="Reveal", exact=True).filter(visible=True).click()
    page.wait_for_timeout(600)


def _number(date: str) -> int:
    """2026-04-17, the first Daily Orbs, is #1."""
    return (dt.date.fromisoformat(date) - FIRST_DAY).days + 1


def _orb_rows(colors: list[str]) -> str:
    return "".join(f":{c}_circle:" * 3 for c in colors)


def _puzzles(solution: Solution, orbs: dict[str, int]) -> list[dict[str, Any]]:
    return [
        {"id": p["id"], "color": p["color"], "orbs": orbs.get(p["color"], 0)}
        for p in solution["puzzles"]
    ]


def _win(player: Player, solution: Solution, wrong: int) -> Expected:
    matching = [p for p in solution["puzzles"] if p["type"] == "bijection"][:2]
    if len(matching) < 2:
        pytest.skip("today has fewer than two bijection puzzles")
    for i, puzzle in enumerate(matching):
        _bijection(player, solution["date"], puzzle, wrong if i == 0 else 0)
    colors = [p["color"] for p in matching]
    hearts = f":{colors[0]}_heart:" * wrong
    return {
        "puzzle_id": solution["date"],
        "puzzle_number": _number(solution["date"]),
        "won": True,
        "score": 6,
        "max_score": 6,
        "hearts_lost": wrong,
        "row": hearts + _orb_rows(colors) + ":trophy:",
        "puzzles": _puzzles(solution, {c: 3 for c in colors}),
    }


def win(player: Player, solution: Solution) -> Expected:
    return _win(player, solution, wrong=0)


def mixed(player: Player, solution: Solution) -> Expected:
    """A win with one mismatch first."""
    return _win(player, solution, wrong=1)


def lose(player: Player, solution: Solution) -> Expected:
    """Give up on every puzzle: all four closed with no orbs."""
    for puzzle in solution["puzzles"]:
        _give_up(player, puzzle)
    return {
        "puzzle_id": solution["date"],
        "puzzle_number": _number(solution["date"]),
        "won": False,
        "score": 0,
        "max_score": 6,
        "hearts_lost": 0,
        "row": "",
        "puzzles": _puzzles(solution, {}),
    }


DRIVER = Driver(
    name="dailyorbs",
    learn=learn,
    scenarios={"win": win, "lose": lose, "mixed": mixed},
)
