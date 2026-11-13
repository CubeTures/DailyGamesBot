"""Connections: the groups come from NYT's own puzzle API (through the proxy)."""

from tests.e2e.expect import length, where
from tests.e2e.harness import Driver, Expected, Player, Solution
from tests.e2e.solutions import game_day

# The groups' colours, easiest first.
COLORS = ["yellow", "green", "blue", "purple"]


def learn(player: Player) -> Solution:
    day = game_day(player.game)
    puzzle = player.fetch(f"/svc/connections/v2/{day}.json")
    assert puzzle.ok, f"Connections API: {puzzle.status}"
    data = puzzle.json()
    return {
        "print_date": data["print_date"],
        # Easiest (yellow) first, as `level` in the game's state.
        "groups": [[c["content"] for c in cat["cards"]] for cat in data["categories"]],
    }


def _start(player: Player) -> None:
    page = player.page
    player.dismiss(page.get_by_role("dialog").get_by_role("button", name="Close"))
    page.get_by_test_id("moment-btn-play").or_(
        page.get_by_role("button", name="Play")
    ).first.click()


def _submit(player: Player, words: list[str]) -> None:
    page = player.page
    deselect = page.get_by_role("button", name="Deselect All")
    if deselect.is_enabled():
        deselect.click()
    for word in words:
        page.get_by_text(word, exact=True).filter(visible=True).last.click()
    page.get_by_role("button", name="Submit").click()
    # The guess animates (and a solved row slides up) before the next one.
    page.wait_for_timeout(3000)


def play(player: Player, solution: Solution) -> Expected:
    """One one-away guess (three of the first group and one of the second),
    then every group: a win with a mistake."""
    groups = solution["groups"]
    _start(player)
    _submit(player, [*groups[0][:3], groups[1][0]])
    for group in groups:
        _submit(player, group)
    return {
        "puzzle_id": solution["print_date"],
        "won": True,
        "mistakes": 1,
        "score": 3,
        "max_score": 4,
        "attempts": 5,
        "groups_found": 4,
        "rows": where(
            "a one-away row (3 yellow + 1 green, in board order), then the groups",
            lambda rows: (
                length(5)(rows)
                and rows[0].count(":yellow_square:") == 3
                and rows[0].count(":green_square:") == 1
                and rows[1:] == [f":{c}_square:" * 4 for c in COLORS]
            ),
        ),
    }


DRIVER = Driver(name="connections", learn=learn, play=play)
