"""PokeDoku: everything is server-side, keyed on a session cookie, so each
fresh browser context gets a fresh grid. The API's /puzzle/stats/<id> lists
the answers players gave for every cell (with `invalid` set on wrong ones),
which is where the driver finds a valid Pokémon for the first cell.

The one path guesses the first cell right and the second wrong, then gives
up, so the capture sees a guess's response, a named Pokémon, empty cells and
the give-up. Each guess's response says whether it was right, so the driver
also checks the server agreed with what it meant to do.
"""

from typing import Any

from playwright.sync_api import Response

from tests.e2e.expect import ANY_POSITIVE, NOT_NONE, between
from tests.e2e.harness import Driver, Expected, Player, Solution

API = "/__host/api.pokedoku.com/api"

# Guesses for the wrong cell; any that's valid for it is skipped.
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


def _learn(player: Player) -> Solution:
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
    # Plain names (no forms) search cleanly.
    options = valid[0]
    assert options, "no known valid answer for cell 1"
    plain = [n for n in options if "-" not in n]
    return {
        "date": puzzle["date"],
        "id": puzzle["id"],
        "pick": (plain or options)[0],
        "wrong": next(w for w in WRONG if w not in valid[1]),
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


def play(player: Player, _solution: Solution) -> Expected:
    page = player.page
    _start(player)
    solution = _learn(player)
    guesses = [(0, solution["pick"], True), (1, solution["wrong"], False)]
    for cell, name, right in guesses:
        ok = _guess(player, cell, name)
        assert ok == right, (
            f"driver problem, not capture: guessing {name} in cell {cell + 1} was"
            f" {'right' if ok else 'wrong'}, meant to be the opposite"
        )
    page.get_by_role("button", name="Give up").first.click()
    page.get_by_role("alertdialog").get_by_role("button", name="Run").click()
    return {
        "puzzle_id": solution["date"],
        "puzzle_number": solution["id"],
        # 100 per empty cell, plus the right cell's pick rate (%).
        "score": between(800, 900),
        "uniqueness_percentile": NOT_NONE,
        "correct": 1,
        "max_correct": 9,
        # Giving up sets it to 9.
        "attempts": ANY_POSITIVE,
        "cells": [solution["pick"], *[None] * 8],
    }


DRIVER = Driver(name="pokedoku", play=play)
