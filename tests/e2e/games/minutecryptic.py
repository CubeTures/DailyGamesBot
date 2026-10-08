"""Minute Cryptic: the answer is in the game's own mc-puzzle state as soon as
today's puzzle has started (one letter typed)."""

from playwright.sync_api import Locator

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


def _cell(player: Player, index: int) -> Locator:
    return player.page.locator(f'[aria-label^="Letter {index + 1} of "]')


def _key(player: Player, letter: str) -> None:
    player.page.locator(f'[data-skbtn="{letter.upper()}"]').click()


def learn(player: Player) -> Solution:
    player.open()
    _start(player)
    _key(player, "A")
    puzzle = player.page.evaluate("JSON.parse(localStorage.getItem('mc-puzzle'))")
    return {
        "date": puzzle["date"],
        "answer": puzzle["answer"],
        "par": (puzzle.get("parDetails") or {}).get("averagePar") or puzzle["par"],
        "help_available": len(puzzle["hints"]) + len(puzzle["puzzlePieces"]),
    }


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


def _close_help(player: Player) -> None:
    close = player.page.get_by_role("dialog").get_by_role("button", name="Close")
    if close.is_visible():
        close.click()


def _type_answer(player: Player, answer: str) -> None:
    """Fill every cell not already revealed, then check."""
    letters = [c for c in answer if c.isalpha()]
    for i, letter in enumerate(letters):
        cell = _cell(player, i)
        if "revealed" in (cell.get_attribute("aria-label") or ""):
            continue
        cell.click()
        _key(player, letter)
    # The game times the solve itself (to the second); make it nonzero.
    player.page.wait_for_timeout(1500)
    player.page.get_by_role("button", name="check").click()


def _expected(solution: Solution, hints: int, letters: int, won: bool) -> Expected:
    par = solution["par"]
    return {
        "puzzle_id": solution["date"],
        "won": won,
        "score": hints + letters - par,
        "par": par,
        "hints": hints,
        "letters_revealed": letters,
        "help_available": solution["help_available"],
    }


def win(player: Player, solution: Solution) -> Expected:
    _start(player)
    _type_answer(player, solution["answer"])
    return _expected(solution, hints=0, letters=0, won=True)


def lose(player: Player, solution: Solution) -> Expected:
    """Reveal every letter: the game's "gave_up" ending."""
    _start(player)
    letters = sum(c.isalpha() for c in solution["answer"])
    for _ in range(letters):
        _help(player, "show letter")
    return _expected(solution, hints=0, letters=letters, won=False)


def mixed(player: Player, solution: Solution) -> Expected:
    _start(player)
    _help(player, "show fodder")
    _help(player, "show letter")
    _close_help(player)
    _type_answer(player, solution["answer"])
    return _expected(solution, hints=1, letters=1, won=True)


DRIVER = Driver(
    name="minutecryptic",
    learn=learn,
    scenarios={"win": win, "lose": lose, "mixed": mixed},
)
