"""Cross with Friends: a new shared game of the newest mini, solo. The
surest way to the end with a square of the player's own: type a letter in
the first square, trying A to Z with Check until it's right, then reveal
the rest of the puzzle (revealed squares count for nobody)."""

import re
import string

from tests.e2e.expect import ANY_POSITIVE, NOT_NONE, where
from tests.e2e.harness import Driver, Expected, Player, Solution


def _menu(player: Player, button: str, item: str) -> None:
    """Pick e.g. Check > Square from the toolbar."""
    page = player.page
    page.get_by_role("button", name=button, exact=True).click()
    page.get_by_role("menuitem", name=item, exact=True).click()
    if (button, item) == ("Reveal", "Puzzle"):
        # "Are you sure you want to show the puzzle?"
        page.locator('[role="alertdialog"], [role="dialog"]').get_by_role(
            "button", name=re.compile("^reveal$", re.IGNORECASE)
        ).click()
    page.wait_for_timeout(300)


def _start(player: Player) -> str:
    """Open a new game of the newest mini; return its game ID."""
    page = player.page
    page.goto(player.url("/?mini=1&midi=0&standard=0&large=0"))
    href = page.locator('a[href*="/play/"]').first.get_attribute("href")
    assert href, "no mini puzzles listed"
    page.goto(player.url(f"{href}?new=1"))
    page.wait_for_url(re.compile(r"/game/"))
    page.locator("td.grid--cell .cell:not(.black)").first.wait_for()
    match = re.search(r"/game/([^/?#]+)", page.url)
    assert match, page.url
    return match.group(1)


def play(player: Player, _solution: Solution) -> Expected:
    gid = _start(player)
    page = player.page
    first = page.locator("td.grid--cell .cell:not(.black)").first
    for letter in string.ascii_uppercase:
        first.click()
        page.keyboard.type(letter)
        first.click()  # Typing moved the cursor on; check this square.
        _menu(player, "Check", "Square")
        if "good" in (first.get_attribute("class") or ""):
            break
    else:
        raise AssertionError("no letter checked right")
    _menu(player, "Reveal", "Puzzle")
    page.locator(".clock--solved").wait_for()
    total = page.locator("td.grid--cell .cell:not(.black)").count()
    return {
        "puzzle_id": gid,
        "title": NOT_NONE,
        "pid": NOT_NONE,
        "player_id": NOT_NONE,
        "score": 1,
        "total_squares": total,
        "revealed": total - 1,
        "time_secs": ANY_POSITIVE,
        "players": where(
            "just the player, with 1 square",
            lambda players: len(players) == 1 and players[0]["score"] == 1,
        ),
    }


DRIVER = Driver(name="crosswithfriends", play=play)
