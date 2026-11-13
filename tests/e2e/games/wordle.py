"""Wordle: the answer comes from NYT's own puzzle API (through the proxy)."""

from tests.e2e.expect import length, where
from tests.e2e.harness import Driver, Expected, Player, Solution
from tests.e2e.solutions import game_day

# Valid guesses; the first that isn't today's answer is the wrong one.
WORDS = ["crane", "pilot"]

GREEN_ROW = ":green_square:" * 5


def learn(player: Player) -> Solution:
    day = game_day(player.game)
    puzzle = player.fetch(f"/svc/wordle/v2/{day}.json")
    assert puzzle.ok, f"Wordle API: {puzzle.status}"
    data = puzzle.json()
    return {"answer": data["solution"], "print_date": data["print_date"]}


def _start(player: Player) -> None:
    page = player.page
    player.dismiss(
        page.get_by_text("Continue to Wordle"),
        page.get_by_role("dialog").get_by_role("button", name="Close"),
    )
    page.get_by_test_id("Play").click()
    # The board takes keys once its first row is there.
    page.locator('[role="group"][aria-label="Row 1"]').wait_for()


def _guess(player: Player, word: str) -> None:
    page = player.page
    # On-screen keys rather than the keyboard: clicks wait for the overlay
    # handlers (a modal opening mid-word would swallow typed letters).
    for key in [*word, "↵"]:
        page.locator(f'button[data-key="{key}"]').click()
    # Let the row flip before the next guess.
    page.wait_for_timeout(2500)


def play(player: Player, solution: Solution) -> Expected:
    """A wrong word, then the answer: a win with a row that isn't all green."""
    guesses = [next(w for w in WORDS if w != solution["answer"]), solution["answer"]]
    _start(player)
    for word in guesses:
        _guess(player, word)
    return {
        "puzzle_id": solution["print_date"],
        "won": True,
        "attempts": 2,
        "score": 2,
        "max_score": 6,
        "rows": where(
            "2 rows, only the last all green",
            lambda rows: (
                length(2)(rows) and rows[0] != GREEN_ROW and rows[1] == GREEN_ROW
            ),
        ),
        "guesses": guesses,
        "hard_mode": False,
    }


DRIVER = Driver(name="wordle", learn=learn, play=play)
