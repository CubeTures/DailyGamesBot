"""Daily Orbs: four puzzles a day in varying formats; six orbs win the day.
The game-day API lists every puzzle with its answers, so learn() just reads
it. Winning plays two puzzles to three orbs each, in any of these formats
(between them, every day since launch has at least two):

- bijection: match each card in column A to one in column B
- themed: a textbox per clue
- open-ended: one textbox taking any of a list of answers
- categorization: put each item in one of a few categories

The fifth, long-list (one textbox, answers checked against a word list), is
rare and never needed. Losing gives up on all four, which works in any format.
"""

import datetime as dt
from collections.abc import Callable
from typing import Any

import pytest

from tests.e2e.harness import Driver, Expected, Player, Solution

API = "/__host/api.dailyorbs.com/api"
FIRST_DAY = dt.date(2026, 4, 17)
COLORS = ["orange", "purple", "green", "blue"]

# A wrong answer for the text formats: costs a heart, uses up nothing.
WRONG_TEXT = "zzzq"

Puzzle = dict[str, Any]


def _name(answer: str | dict[str, Any]) -> str:
    # An answer is its name, or {"name": ..., "display": ...}.
    return answer if isinstance(answer, str) else answer["name"]


def _puzzle(color: str, data: dict[str, Any]) -> Puzzle:
    kind = data["type"]
    puzzle: Puzzle = {
        "id": data["id"],
        "color": color,
        "type": kind,
        # Correct answers for the third orb.
        "needs": data["starThresholds"][-1],
    }
    if kind == "bijection":
        # itemA -> itemB, as the game stores them
        puzzle["pairs"] = {p["itemA"]: p["itemB"] for p in data["pairs"]}
    elif kind == "themed":
        # A clue's answer, in on-screen order.
        puzzle["answers"] = [_name(c["answers"][0]) for c in data["clues"]]
        # Typing is restricted (digits only, a suffix...), so WRONG_TEXT may
        # not get through.
        puzzle["masked"] = "inputMask" in data or any(
            "inputMask" in c for c in data["clues"]
        )
    elif kind == "open-ended":
        puzzle["answers"] = [_name(a) for a in data["answers"]]
        puzzle["masked"] = "inputMask" in data
    elif kind == "categorization":
        # item id -> its category
        puzzle["items"] = {i["id"]: i["category"] for i in data["items"]}
        puzzle["categories"] = data["categories"]
    return puzzle


def learn(player: Player) -> Solution:
    response = player.context.request.get(player.url(f"{API}/game-day"))
    assert response.ok, f"Daily Orbs API: {response.status}"
    data = response.json()
    puzzles = data["puzzles"]
    return {
        "date": data["dateKey"],
        "puzzles": [_puzzle(c, puzzles[c]) for c in COLORS if c in puzzles],
    }


def _day_state(player: Player, date: str) -> dict[str, Any]:
    return player.page.evaluate(
        "(key) => JSON.parse(localStorage.getItem(key) || 'null')", f"daily-orbs-{date}"
    )


def _progress(player: Player, date: str, puzzle: Puzzle) -> dict[str, Any]:
    """The puzzle's entry in the day state: orbs, livesLeft, totalFound..."""
    state = _day_state(player, date)
    return next(p for p in state["puzzles"] if p["puzzleId"] == puzzle["id"])


def _orbs(player: Player, date: str, puzzle: Puzzle) -> int:
    return _progress(player, date, puzzle)["orbs"]


def _check_three_orbs(player: Player, date: str, puzzle: Puzzle) -> None:
    orbs = _orbs(player, date, puzzle)
    assert orbs == 3, f"driver problem: {puzzle['id']} ended with {orbs} orbs, not 3"


def _open(player: Player, puzzle: Puzzle) -> None:
    page = player.page
    page.goto(player.url(f"/{puzzle['id']}"))
    # The 6-orb "Victory" modal.
    player.dismiss(page.get_by_role("button", name="Yay", exact=True))
    # All four puzzles are mounted side by side; only the open one is visible.
    page.get_by_role("button", name="Reveal Answers").filter(visible=True).wait_for()


def _bijection(player: Player, date: str, puzzle: Puzzle, wrong: int) -> None:
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

    pairs: dict[str, str] = puzzle["pairs"]
    for _ in range(wrong):
        a = column_a[0]
        pick(a, next(b for b in column_b if b != pairs[a]))
    # The third orb can come before the last pair (starThresholds), and once
    # the day is won the board stops taking picks.
    while column_a and _orbs(player, date, puzzle) < 3:
        a = column_a[0]
        b = pairs[a]
        pick(a, b)
        column_a.remove(a)
        column_b.remove(b)
    _check_three_orbs(player, date, puzzle)


def _typed(player: Player, date: str, puzzle: Puzzle, wrong: int) -> None:
    """Themed and open-ended: type answers into the first textbox, after
    `wrong` wrong ones (a heart each). Open-ended has the one textbox;
    themed has one per clue, and a solved clue's goes, so the first is
    always the next clue's."""
    page = player.page
    _open(player, puzzle)
    box = page.get_by_role("textbox").filter(visible=True).first

    def submit(text: str) -> None:
        box.fill(text)
        box.press("Enter")
        page.wait_for_timeout(600)

    for _ in range(wrong):
        submit(WRONG_TEXT)
    for answer in puzzle["answers"]:
        if _orbs(player, date, puzzle) >= 3:
            break
        found = _progress(player, date, puzzle)["totalFound"]
        submit(answer)
        now = _progress(player, date, puzzle)["totalFound"]
        assert now == found + 1, (
            f"driver problem: {answer!r} wasn't accepted in {puzzle['id']}"
        )
    _check_three_orbs(player, date, puzzle)


def _categorization(player: Player, date: str, puzzle: Puzzle, wrong: int) -> None:
    """Put each item in its category, after putting the first `wrong` in
    another one (a heart each, and the item is used up)."""
    page = player.page
    _open(player, puzzle)
    items: dict[str, str] = dict(puzzle["items"])

    def pick(item: str, category: str) -> None:
        row = page.locator(f'[data-cat-item="{item}"]').filter(visible=True)
        # The category buttons are in a popover the row opens.
        if not row.locator(".cat-popover-visible").count():
            row.locator(".cat-name").click()
        row.locator("button.cat-btn").filter(
            has=page.get_by_text(category, exact=True)
        ).click()
        page.wait_for_timeout(600)

    for item in list(items)[:wrong]:
        right = items.pop(item)
        pick(item, next(c for c in puzzle["categories"] if c != right))
    for item, category in items.items():
        if _orbs(player, date, puzzle) >= 3:
            break
        pick(item, category)
    _check_three_orbs(player, date, puzzle)


SOLVERS: dict[str, Callable[[Player, str, Puzzle, int], None]] = {
    "bijection": _bijection,
    "themed": _typed,
    "open-ended": _typed,
    "categorization": _categorization,
}


def _solvable(puzzle: Puzzle) -> bool:
    kind = puzzle["type"]
    if kind in ("themed", "open-ended"):
        # A few themed puzzles take more answers than they have clues.
        return len(puzzle["answers"]) >= puzzle["needs"]
    if kind == "categorization":
        return len(puzzle["items"]) >= puzzle["needs"]
    return kind in SOLVERS


def _can_miss(puzzle: Puzzle) -> bool:
    """Whether a wrong answer still leaves three orbs reachable."""
    kind = puzzle["type"]
    if kind in ("themed", "open-ended"):
        return not puzzle["masked"]
    if kind == "categorization":
        return len(puzzle["items"]) - 1 >= puzzle["needs"]
    return True


def _give_up(player: Player, puzzle: Puzzle) -> None:
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
    """Three orbs in each of two puzzles; `wrong` mistakes in the first."""
    playable: list[Puzzle] = [p for p in solution["puzzles"] if _solvable(p)]
    if len(playable) < 2:
        pytest.skip(f"today has fewer than two puzzles in {sorted(SOLVERS)}")
    first = next((p for p in playable if _can_miss(p)), None) if wrong else playable[0]
    if first is None:
        pytest.skip("no puzzle today can take a mistake and still give 3 orbs")
    played = [first, next(p for p in playable if p is not first)]
    for i, puzzle in enumerate(played):
        SOLVERS[puzzle["type"]](
            player, solution["date"], puzzle, wrong if i == 0 else 0
        )
    colors = [p["color"] for p in played]
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
    """A win with one mistake first."""
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
