"""Circuits: the answers come from the puzzle itself. Puzzmo sends the board
in PlayGameScreenQuery's `puzzle.puzzle`, one line per row and one cell per
comma, with each box to fill marked "* ANSWER":

    2
    , FREUDIAN >, * SLIP >V, 'N SLIDE
    SHRINK >, * WRAP >V, * DRESS >V, FOR SUCCESS
    ...

There's no losing: every game ends with the board solved. The driver reads
the board from that response as the page starts the game, makes one wrong
submit in the first box and uses a Bolt on the last (so every count the
capture keeps is nonzero), and fills the rest. The board is in an iframe and
takes typed letters into the selected box; Enter submits.
"""

import re
import time
from collections.abc import Callable

from playwright.sync_api import FrameLocator, Locator

from tests.e2e.expect import between
from tests.e2e.harness import Driver, Expected, Player, Solution
from tests.e2e.solutions import game_day

# A wrong submit: the first that isn't the box's answer.
WRONG = ["TRAFFIC", "BANANA"]

# A box cell: "* SLIP >V" is a box (answer SLIP) with arrows out right and down.
BOX = re.compile(r"^\*\s*(.+?)(?:\s+[>V]+)?$")

# A fresh board's Bolts are still charging; the first is ready after ~100s.
BOLT_CHARGE_SECS = 180


def _start(player: Player) -> tuple[FrameLocator, Solution]:
    """Start today's game; the board, and the puzzle the page was sent."""
    # The page first draws from its own cache ("offline relay data") and
    # only sends this query once that's done, which through the proxy can
    # take over 30s.
    with player.page.expect_response(
        lambda r: "PlayGameScreenQuery" in r.url, timeout=90_000
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
    board = player.page.frame_locator("iframe[src*='runtime.html']")
    board.locator("[data-drop-tile-id]").first.wait_for()
    return board, {
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


def _select(player: Player, board: FrameLocator, tile: str) -> Locator:
    """Select a box. Clicking the selected box deselects it, so click only
    if it isn't already (the selected box has an outline: a box-shadow with a
    nonzero spread, "rgb(0, 0, 0) 0px 0px 0px 4px", where the rest have 0px)."""
    box = board.locator(f'[data-drop-tile-id="{tile}"]')
    selected = (
        "e => parseFloat(getComputedStyle(e.firstElementChild)"
        ".boxShadow.split(' ').at(-1)) > 0"
    )
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


def play(player: Player, _solution: Solution) -> Expected:
    board, solution = _start(player)
    boxes = solution["boxes"]
    n = len(boxes)
    wrong = [1] + [0] * (n - 1)
    bolts = [0] * (n - 1) + [1]
    for box, n_wrong, bolt in zip(boxes, wrong, bolts, strict=True):
        if n_wrong:
            word = next(w for w in WRONG if w != box["answer"])
            _wrong(player, board, box["tile"], word)
        _solve(player, board, box["tile"], box["answer"], bool(bolt))
    return {
        "puzzle_id": solution["date_key"],
        "puzzle_number": solution["number"],
        "date": solution["title"],
        "score": between(1, solution["cap"]),
        "boxes": n,
        "submits": n + 1,
        "wrong": 1,
        "bolts": 1,
        "box_wrong": wrong,
        "box_bolts": bolts,
    }


DRIVER = Driver(name="circuits", play=play)
