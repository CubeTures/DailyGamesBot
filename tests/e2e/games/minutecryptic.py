"""Minute Cryptic: one clue, solved letter by letter. The surest way to the
end needs no answer: take one hint, then reveal every letter (the game's
"gave_up" ending). Par and the help on offer come from the game's own
mc-puzzle state afterwards."""

from typing import Any

from tests.e2e.harness import Driver, Expected, Player, Solution


def _start(player: Player) -> None:
    page = player.page
    # Promos for new visitors ("Three free cryptic courses").
    player.dismiss(page.get_by_text("not now", exact=True))
    answer = page.get_by_role("group", name="Puzzle answer")
    # The promo can open just after "play" is clicked, swallowing the click.
    for _ in range(3):
        page.get_by_role("button", name="play", exact=True).click()
        try:
            answer.wait_for(timeout=5000)
            return
        except Exception:
            pass
    answer.wait_for()


def _help(player: Player, kind: str) -> None:
    """Take one hint: "show fodder", "show definition" or "show letter"."""
    page = player.page
    dialog = page.get_by_role("dialog")
    if not dialog.is_visible():
        page.get_by_role("button", name="hints").click()
    back = dialog.get_by_role("button", name="Back")
    if back.is_visible():
        back.click()
    dialog.get_by_role("button", name=kind).click()
    page.wait_for_timeout(500)


def play(player: Player, _solution: Solution) -> Expected:
    _start(player)
    page = player.page
    # The answer's letter cells: "Letter 1 of 9, ..." or, for answers of
    # several words, "Word 2, letter 1 of 2, ...".
    letters = (
        page.get_by_role("group", name="Puzzle answer")
        .locator('[aria-label*="letter " i][aria-label*=" of "]')
        .count()
    )
    assert letters, "no letter cells"
    _help(player, "show fodder")
    for _ in range(letters):
        _help(player, "show letter")
    puzzle: dict[str, Any] = page.evaluate(
        "JSON.parse(localStorage.getItem('mc-puzzle'))"
    )
    details: dict[str, Any] = puzzle.get("parDetails") or {}
    par: int = details.get("averagePar") or puzzle["par"]
    return {
        "puzzle_id": puzzle["date"],
        "won": False,
        "score": 1 + letters - par,
        "par": par,
        "hints": 1,
        "letters_revealed": letters,
        "help_available": len(puzzle["hints"]) + len(puzzle["puzzlePieces"]),
    }


DRIVER = Driver(name="minutecryptic", play=play)
