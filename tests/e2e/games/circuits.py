"""Circuits: the answers come from the puzzle itself. Puzzmo sends the board
in PlayGameScreenQuery's `puzzle.puzzle`, one line per row and one cell per
comma, with each box to fill marked "* ANSWER":

    2
    , FREUDIAN >, * SLIP >V, 'N SLIDE
    SHRINK >, * WRAP >V, * DRESS >V, FOR SUCCESS
    ...

There's no losing: every game ends with the board solved, and scenarios run
from no mistakes to a wrong submit in every box. The board is in an iframe
and takes typed letters into the selected box; Enter submits.
"""

import re
import time
from collections.abc import Callable

from playwright.sync_api import FrameLocator, Locator

from tests.e2e.expect import between
from tests.e2e.harness import Driver, Expected, Player, Solution
from tests.e2e.solutions import game_day

# Wrong submits; whichever aren't the box's answer.
WRONG = ["TRAFFIC", "BANANA", "PURPLE", "MOUNTAIN", "WHISKER", "LANTERN"]

# A box cell: "* SLIP >V" is a box (answer SLIP) with arrows out right and down.
BOX = re.compile(r"^\*\s*(.+?)(?:\s+[>V]+)?$")

# A fresh board's Bolts are still charging; the first is ready after ~100s.
BOLT_CHARGE_SECS = 180


def learn(player: Player) -> Solution:
    player.open()
    with player.page.expect_response(
        lambda r: "PlayGameScreenQuery" in r.url
    ) as response:
        player.page.get_by_role("link", name="Play Today's Circuits").click()
    puzzle = response.value.json()["data"]["startOrFindGameplay"]["gamePlayed"][
        "puzzle"
    ]
    # Each box's answer and tile, in board (reading) order; the board's tiles
    # are "col-row".
    boxes: list[dict[str, str]] = []
    for row, line in enumerate(puzzle["puzzle"].split("\n")[1:]):
        for col, cell in enumerate(line.split(",")):
            if match := BOX.match(cell.strip()):
                boxes.append({"answer": match[1], "tile": f"{col}-{row}"})
    assert boxes, f"no boxes in the puzzle: {puzzle['puzzle']!r}"
    return {
        "date_key": game_day(player.game).isoformat(),
        "number": puzzle["seriesNumber"],
        "title": puzzle["dailyTitle"],
        "cap": puzzle["difficultyPointsCap"],
        "boxes": boxes,
    }


def _wait(
    player: Player, test: Callable[[], bool], what: str, timeout: float = 10
) -> None:
    deadline = time.monotonic() + timeout
    while not test():
        assert time.monotonic() < deadline, f"timed out waiting for {what}"
        player.page.wait_for_timeout(200)


def _start(player: Player) -> FrameLocator:
    player.page.get_by_role("link", name="Play Today's Circuits").click()
    board = player.page.frame_locator("iframe[src*='runtime.html']")
    board.locator("[data-drop-tile-id]").first.wait_for()
    return board


def _select(player: Player, board: FrameLocator, tile: str) -> Locator:
    """Select a box. Clicking the selected box deselects it, so click only
    if it isn't already (the selected box has a 3px outline)."""
    box = board.locator(f'[data-drop-tile-id="{tile}"]')
    selected = "e => getComputedStyle(e.firstElementChild).boxShadow.endsWith(' 3px')"
    if not box.evaluate(selected):
        box.click()
    _wait(player, lambda: box.evaluate(selected), f"box {tile} to be selected")
    return box


def _submit(player: Player, box: Locator, word: str) -> None:
    """Type the rest of `word` after whatever the box shows (a Bolt's
    letters) and submit it."""
    shown = box.text_content() or ""
    assert word.startswith(shown), f"box shows {shown!r}, not a prefix of {word!r}"
    player.page.keyboard.type(word[len(shown) :])
    player.page.keyboard.press("Enter")


def _wrong(player: Player, board: FrameLocator, tile: str, word: str) -> None:
    box = _select(player, board, tile)
    _submit(player, box, word)
    # A wrong submit is cleared from the box.
    _wait(player, lambda: box.text_content() == "", f"{word} to be rejected")


def _solve(
    player: Player, board: FrameLocator, tile: str, answer: str, bolt: bool = False
) -> None:
    box = _select(player, board, tile)
    if bolt:
        button = board.get_by_text("Use Bolt!", exact=True)
        _wait(
            player,
            lambda: button.evaluate("e => getComputedStyle(e).cursor") == "pointer",
            "a Bolt to charge",
            BOLT_CHARGE_SECS,
        )
        button.click()
        _wait(player, lambda: bool(box.text_content()), "a Bolt's letter")
    _submit(player, box, answer)
    # A solved box stops being a drop target.
    box.wait_for(state="detached")


def _wrong_words(answer: str, n: int) -> list[str]:
    return [w for w in WRONG if w != answer][:n]


def _play(
    player: Player, solution: Solution, wrong: list[int], bolts: list[int]
) -> Expected:
    """Fill every box in order, after `wrong[i]` wrong submits in box i,
    using `bolts[i]` (0 or 1) Bolts on it."""
    board = _start(player)
    for box, n_wrong, bolt in zip(solution["boxes"], wrong, bolts, strict=True):
        for word in _wrong_words(box["answer"], n_wrong):
            _wrong(player, board, box["tile"], word)
        _solve(player, board, box["tile"], box["answer"], bool(bolt))
    n = len(solution["boxes"])
    return {
        "puzzle_id": solution["date_key"],
        "puzzle_number": solution["number"],
        "date": solution["title"],
        "score": between(1, solution["cap"]),
        "boxes": n,
        "submits": n + sum(wrong),
        "wrong": sum(wrong),
        "bolts": sum(bolts),
        "box_wrong": wrong,
        "box_bolts": bolts,
    }


def win(player: Player, solution: Solution) -> Expected:
    n = len(solution["boxes"])
    return _play(player, solution, [0] * n, [0] * n)


def mixed(player: Player, solution: Solution) -> Expected:
    """Two wrong submits in the first box, and a Bolt on the last."""
    n = len(solution["boxes"])
    return _play(player, solution, [2] + [0] * (n - 1), [0] * (n - 1) + [1])


def misses(player: Player, solution: Solution) -> Expected:
    """A wrong submit in every box."""
    n = len(solution["boxes"])
    return _play(player, solution, [1] * n, [0] * n)


DRIVER = Driver(
    name="circuits",
    learn=learn,
    scenarios={"win": win, "mixed": mixed, "misses": misses},
)
