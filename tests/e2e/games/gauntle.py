"""Gauntle: a run of eleven mini-games against one clock. Every run ends in a
total time (failing or skipping a game only adds a penalty), so the one
scenario plays the cheapest full run: skip every game that has a Skip button
(it unlocks after 45s, so a run takes about eight minutes) and make one
throwaway move in the two that don't (Ratiole's cut, Angle's three dials)."""

import re
from datetime import date

from playwright.sync_api import Page

from tests.e2e.expect import where
from tests.e2e.harness import Driver, Expected, Player, Solution
from tests.e2e.solutions import game_day

GAMES = 11


def _cut(page: Page) -> None:
    """Ratiole: one straight cut across the whole board."""
    box = page.locator("main canvas").bounding_box()
    assert box, "Ratiole's board"
    y = box["y"] + box["height"] * 0.6
    page.mouse.move(box["x"] + 10, y)
    page.mouse.down()
    page.wait_for_timeout(300)
    page.mouse.move(box["x"] + box["width"] - 10, y, steps=25)
    page.mouse.up()


def _turn_dials(page: Page) -> None:
    """Angle: three rounds of dragging the arm's knob to 12 o'clock."""
    dial = page.get_by_role("application", name="Dial")
    for _ in range(3):
        dial.wait_for()
        box = dial.bounding_box()
        assert box, "Angle's dial"
        cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
        radius = box["width"] * 0.42
        # The knob is the circle furthest from the dial's centre.
        knob = dial.evaluate(
            """svg => {
              const s = svg.getBoundingClientRect();
              const mx = s.x + s.width / 2, my = s.y + s.height / 2;
              const far = r => Math.hypot(r.x + r.width / 2 - mx, r.y + r.height / 2 - my);
              const k = [...svg.querySelectorAll("circle")]
                .map(c => c.getBoundingClientRect())
                .filter(r => r.width > 6 && r.width < 60)
                .sort((a, b) => far(b) - far(a))[0];
              return {x: k.x + k.width / 2, y: k.y + k.height / 2};
            }"""
        )
        page.mouse.move(knob["x"], knob["y"])
        page.mouse.down()
        page.mouse.move(cx + radius, cy - 5, steps=10)
        page.mouse.move(cx, cy - radius, steps=10)
        page.mouse.up()
        page.get_by_role("button", name="Lock in").click()
        page.wait_for_timeout(2500)


def skip_all(player: Player, _solution: Solution) -> Expected:
    page = player.page
    # A "Heads up!" notice about changed games can come before the run.
    player.dismiss(page.get_by_role("dialog").get_by_role("button", name="Start run"))
    page.get_by_role("button", name="Run the Gauntlet").click()
    banner = page.get_by_role("banner")

    skip = page.get_by_role("button", name="Skip", exact=False)
    dial = page.get_by_role("application", name="Dial")
    cut = page.get_by_text("Hold and drag to draw your cut")
    skipped: set[int] = set()
    for _ in range(GAMES):
        # After each game's 3-2-1 countdown, one of these shows.
        skip.or_(dial).or_(cut).first.wait_for(timeout=30000)
        found = re.search(r"game (\d+) of", banner.inner_text())
        assert found, banner.inner_text()
        n = int(found[1])
        if skip.count():
            # It counts down "Skip (45s)", disabled, until it unlocks.
            page.locator("button:enabled", has_text="Skip").wait_for(timeout=90000)
            skip.click()
            skipped.add(n)
        elif dial.count():
            _turn_dials(page)
        else:
            _cut(page)
        if n == GAMES:
            break
        banner.get_by_text(f"game {n + 1} of {GAMES}").wait_for(timeout=30000)
    page.wait_for_url("**/results/**", wait_until="commit", timeout=30000)

    return {
        "puzzle_id": game_day(player.game).isoformat(),
        # 2026-05-13, the first Gauntle, is #1
        "puzzle_number": (game_day(player.game) - date(2026, 5, 13)).days + 1,
        "game_count": GAMES,
        "flawless": False,
        "games": where(
            f"{GAMES} games, games {sorted(skipped)} skipped",
            lambda games: (
                len(games) == GAMES
                and {i + 1 for i, g in enumerate(games) if g["skipped"]} == skipped
            ),
        ),
        # Each skip costs 60-90s; the run total includes them.
        "delta_secs": where("at least 60s per skip", lambda d: d >= 60 * len(skipped)),
        "score": where("whole seconds", lambda s: isinstance(s, int) and s > 0),
    }


DRIVER = Driver(name="gauntle", scenarios={"skip_all": skip_all})
