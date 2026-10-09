"""PokeDoku: everything is server-side, keyed on a session cookie, so each
fresh browser context gets a fresh grid. The API's /puzzle/stats/<id> lists
the answers players gave for every cell (with `invalid` set on wrong ones),
which is where learn() finds a valid, distinct Pokémon per cell.

Each guess's response says whether it was right, so a scenario also checks
the server agreed with what it meant to do before checking the capture.
"""

from typing import Any

from playwright.sync_api import Response

from tests.e2e.expect import ANY_POSITIVE, NOT_NONE, between
from tests.e2e.harness import Driver, Expected, Player, Solution

API = "/__host/api.pokedoku.com/api"

# Guesses for "wrong" cells; any that's valid for the cell is skipped.
WRONG = [
    "magikarp",
    "caterpie",
    "rattata",
    "pidgey",
    "weedle",
    "zubat",
    "sentret",
    "wurmple",
    "bidoof",
    "patrat",
    "spearow",
    "ekans",
    "meowth",
    "psyduck",
]

# Centres of the 3x3 grid's cells, row by row: the one element whose nine
# children are all big squares.
CELLS = """() => {
  const grid = [...document.querySelectorAll("div")].find(d => d.children.length === 9
    && [...d.children].every(c => { const b = c.getBoundingClientRect();
      return b.width > 60 && Math.abs(b.width - b.height) < 10; }));
  return grid ? [...grid.children].map(c => { const b = c.getBoundingClientRect();
    return [b.x + b.width / 2, b.y + b.height / 2]; }) : null;
}"""


def _get(player: Player, path: str) -> Any:
    return player.page.evaluate(
        "async (url) => { const r = await fetch(url, {credentials: 'include'});"
        " if (!r.ok) throw new Error(url + ': ' + r.status); return r.json(); }",
        f"{API}{path}",
    )


def _start(player: Player) -> None:
    page = player.page
    page.get_by_role("dialog", name="How To Play PokeDoku").get_by_role(
        "button", name="Close"
    ).click()
    page.wait_for_function(f"({CELLS})() !== null")


def learn(player: Player) -> Solution:
    player.open()
    _start(player)
    puzzle = _get(player, "/puzzle/current")
    pokemon = {p["id"]: p for p in _get(player, "/pokemon/all") if not p.get("hidden")}
    stats = _get(player, f"/puzzle/stats/{puzzle['id']}")["answerStats"]
    valid: dict[int, list[str]] = {}
    for cell in range(9):
        answers = stats.get(str(cell + 1), {}).get("answerAggregates", {}).values()
        ranked = sorted(
            (a for a in answers if not a["invalid"] and a["pokemonId"] in pokemon),
            key=lambda a: -a["aggCount"],
        )
        valid[cell] = [pokemon[a["pokemonId"]]["name"] for a in ranked]
    # One distinct pick per cell; plain names (no forms) search cleanly.
    picks: list[str] = []
    for cell in range(9):
        options = [n for n in valid[cell] if n not in picks]
        plain = [n for n in options if "-" not in n]
        assert options, f"no known valid answer for cell {cell + 1}"
        picks.append((plain or options)[0])
    return {
        "date": puzzle["date"],
        "id": puzzle["id"],
        "picks": picks,
        "valid": {str(c): v for c, v in valid.items()},
    }


def _is_guess(response: Response) -> bool:
    return response.url.endswith("/api/puzzle/solution/guess")


def _guess(player: Player, cell: int, name: str) -> bool:
    """Guess `name` for `cell` (0-8, row by row); whether it was right."""
    page = player.page
    x, y = page.evaluate(CELLS)[cell]
    page.mouse.click(x, y)
    dialog = page.get_by_role("dialog", name="Make your guess")
    dialog.get_by_role("searchbox").fill(name.replace("-", " "))
    option = dialog.get_by_role("img", name=name, exact=True)
    select = option.locator("xpath=following::button[1]")
    # The misclick guard (on by default) turns "Select" into "Sure?" first.
    select.click()
    with page.expect_response(_is_guess) as info:
        select.click()
    page.wait_for_timeout(800)
    return bool(info.value.json()["result"])


def _play(player: Player, solution: Solution, right: set[int]) -> list[str | None]:
    """Guess every cell once: right for cells in `right`, else a Pokémon that
    doesn't fit. Returns the grid as the capture should report it."""
    _start(player)
    used: set[str] = set()
    grid: list[str | None] = []
    for cell in range(9):
        if cell in right:
            name = solution["picks"][cell]
        else:
            name = next(
                w
                for w in WRONG
                if w not in used and w not in solution["valid"][str(cell)]
            )
        used.add(name)
        ok = _guess(player, cell, name)
        assert ok == (cell in right), (
            f"driver problem, not capture: guessing {name} in cell {cell + 1} was"
            f" {'right' if ok else 'wrong'}, meant to be the opposite"
        )
        grid.append(name if ok else None)
    return grid


def _expected(solution: Solution, grid: list[str | None]) -> Expected:
    correct = sum(c is not None for c in grid)
    empty = 9 - correct
    return {
        "puzzle_id": solution["date"],
        "puzzle_number": solution["id"],
        # 100 per empty cell, plus each correct cell's pick rate (%).
        "score": 900
        if correct == 0
        else between(100 * empty, 100 * empty + 100 * correct),
        "uniqueness_percentile": NOT_NONE,
        "correct": correct,
        "max_correct": 9,
        "attempts": 9,
        "cells": grid,
    }


def win(player: Player, solution: Solution) -> Expected:
    return _expected(solution, _play(player, solution, set(range(9))))


def lose(player: Player, solution: Solution) -> Expected:
    return _expected(solution, _play(player, solution, set()))


def mixed(player: Player, solution: Solution) -> Expected:
    return _expected(solution, _play(player, solution, {0, 4, 8}))


def give_up(player: Player, solution: Solution) -> Expected:
    page = player.page
    _start(player)
    page.get_by_role("button", name="Give up").first.click()
    page.get_by_role("alertdialog").get_by_role("button", name="Run").click()
    return _expected(solution, [None] * 9) | {"attempts": ANY_POSITIVE}


DRIVER = Driver(
    name="pokedoku",
    learn=learn,
    scenarios={"win": win, "lose": lose, "mixed": mixed, "give_up": give_up},
)
