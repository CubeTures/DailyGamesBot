"""Connections: the groups come from NYT's own puzzle API (through the proxy)."""

from tests.e2e.expect import length, where
from tests.e2e.harness import Driver, Expected, Player, Solution
from tests.e2e.solutions import game_day


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


def _one_away(groups: list[list[str]], group: int, n: int) -> list[list[str]]:
    """n distinct wrong guesses: three of `group` plus one of the next."""
    other = groups[(group + 1) % 4]
    return [[*groups[group][:3], other[i]] for i in range(n)]


def win(player: Player, solution: Solution) -> Expected:
    groups = solution["groups"]
    _start(player)
    for group in groups:
        _submit(player, group)
    return {
        "puzzle_id": solution["print_date"],
        "won": True,
        "mistakes": 0,
        "score": 4,
        "max_score": 4,
        "attempts": 4,
        "groups_found": 4,
        "rows": [
            ":yellow_square:" * 4,
            ":green_square:" * 4,
            ":blue_square:" * 4,
            ":purple_square:" * 4,
        ],
    }


def lose(player: Player, solution: Solution) -> Expected:
    _start(player)
    for guess in _one_away(solution["groups"], 0, 4):
        _submit(player, guess)
    return {
        "puzzle_id": solution["print_date"],
        "won": False,
        "mistakes": 4,
        "score": -4,
        "attempts": 4,
        "groups_found": 0,
        "rows": where(
            "4 one-away rows (3 yellow + 1 green, in board order)",
            lambda rows: (
                length(4)(rows)
                and all(
                    r.count(":yellow_square:") == 3 and r.count(":green_square:") == 1
                    for r in rows
                )
            ),
        ),
    }


def mixed(player: Player, solution: Solution) -> Expected:
    groups = solution["groups"]
    _start(player)
    _submit(player, groups[0])
    for guess in _one_away(groups, 1, 2):
        _submit(player, guess)
    for group in groups[1:]:
        _submit(player, group)
    return {
        "puzzle_id": solution["print_date"],
        "won": True,
        "mistakes": 2,
        "score": 2,
        "attempts": 6,
        "groups_found": 4,
        "rows": length(6),
    }


DRIVER = Driver(
    name="connections",
    learn=learn,
    scenarios={"win": win, "lose": lose, "mixed": mixed},
)
