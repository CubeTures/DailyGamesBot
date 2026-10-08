"""Wordle: the answer comes from NYT's own puzzle API (through the proxy)."""

from tests.e2e.expect import length, where
from tests.e2e.harness import Driver, Expected, Player, Solution
from tests.e2e.solutions import game_day

# Valid guesses; whichever aren't today's answer are the wrong ones.
WORDS = ["crane", "pilot", "mound", "shaky", "fizzy", "blond", "vivid", "jumpy"]

GREEN_ROW = ":green_square:" * 5


def learn(player: Player) -> Solution:
    day = game_day(player.game)
    puzzle = player.context.request.get(player.url(f"/svc/wordle/v2/{day}.json"))
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


def _wrong(solution: Solution, n: int) -> list[str]:
    return [w for w in WORDS if w != solution["answer"]][:n]


def _play(player: Player, solution: Solution, guesses: list[str]) -> None:
    _start(player)
    for word in guesses:
        _guess(player, word)


def win(player: Player, solution: Solution) -> Expected:
    _play(player, solution, [solution["answer"]])
    return {
        "puzzle_id": solution["print_date"],
        "won": True,
        "attempts": 1,
        "score": 1,
        "max_score": 6,
        "rows": [GREEN_ROW],
        "guesses": [solution["answer"]],
        "hard_mode": False,
    }


def lose(player: Player, solution: Solution) -> Expected:
    wrong = _wrong(solution, 6)
    _play(player, solution, wrong)
    return {
        "puzzle_id": solution["print_date"],
        "won": False,
        "attempts": 6,
        "score": None,
        "rows": where(
            "6 rows, none all green",
            lambda rows: len(rows) == 6 and GREEN_ROW not in rows,
        ),
        "guesses": wrong,
    }


def mixed(player: Player, solution: Solution) -> Expected:
    guesses = [*_wrong(solution, 2), solution["answer"]]
    _play(player, solution, guesses)
    return {
        "puzzle_id": solution["print_date"],
        "won": True,
        "attempts": 3,
        "score": 3,
        "rows": where(
            "3 rows, the last all green",
            lambda rows: length(3)(rows) and rows[-1] == GREEN_ROW,
        ),
        "guesses": guesses,
    }


DRIVER = Driver(
    name="wordle",
    learn=learn,
    scenarios={"win": win, "lose": lose, "mixed": mixed},
)
