"""Farflung: five prompts, a country pinned for each. The day's deck is served
encrypted, so there's no solution to learn: the driver pins the same five big
countries every day and reads how each did from the game's own status line
("Brazil: Miss, +0 km") as it goes. Every expedition ends in a distance, so
there's one outcome; most days that's five misses, sometimes a find or two.
"""

import datetime as dt
import re

from tests.e2e.expect import between, where
from tests.e2e.harness import Driver, Expected, Player, Solution
from tests.e2e.solutions import game_day

FIRST_DAY = dt.date(2026, 10, 5)

# Points on the "Whole world" view at 1280x720: Brazil, Russia, Canada,
# Australia, Mongolia.
PINS = [(300, 480), (720, 170), (200, 230), (790, 530), (680, 300)]

# Tier names as the game shows them -> fields.js's emoji.
EMOJI = {
    "Miss": ":black_large_square:",
    "Common": ":white_large_square:",
    "Well known": ":yellow_square:",
    "Uncommon": ":green_square:",
    "Rare": ":blue_square:",
    "Elusive": ":purple_square:",
    "Farflung": ":orange_square:",
}
LANDS = [
    (500, "The edge"),
    (350, "The ice"),
    (250, "The mountains"),
    (100, "The plains"),
]

# The map's status after a drop: "<country>: <tier>, +<km> km", sometimes
# followed by ". New Location".
DROPPED = re.compile(
    r"^(?P<country>.+): (?P<tier>[A-Za-z ]+), \+?(?P<km>\d+) km(\. .*)?$"
)


def _drop(player: Player, x: int, y: int) -> dict[str, str | int]:
    page = player.page
    page.get_by_role("button", name="Whole world").click()
    page.wait_for_timeout(1200)
    page.mouse.click(x, y)
    page.get_by_role("button", name="Drop pin").click()
    status = (
        page.get_by_role("status").filter(has_text=re.compile(r", \+?\d+ km")).first
    )
    status.wait_for(timeout=15_000)
    match = DROPPED.match((status.text_content() or "").strip())
    assert match, f"driver problem: no pin result in {status.text_content()!r}"
    return {
        "country": match["country"],
        "tier": match["tier"],
        "km": int(match["km"]),
    }


def finish(player: Player, solution: Solution) -> Expected:
    page = player.page
    page.set_viewport_size({"width": 1280, "height": 720})
    page.get_by_role("button", name="Play Daily Expedition").click()
    pins: list[dict[str, str | int]] = []
    for i, (x, y) in enumerate(PINS):
        if i:
            # Enabled once the drop's animation is over.
            page.get_by_role("button", name="Next prompt").click(timeout=20_000)
        pins.append(_drop(player, x, y))
    # Camp posts the run to the server, whose answer has the percentile.
    page.get_by_role("button", name="On to camp").click(timeout=20_000)

    day = game_day(player.game)
    km = sum(int(p["km"]) for p in pins)
    return {
        "puzzle_id": day.isoformat(),
        "puzzle_number": (day - FIRST_DAY).days + 1,
        "score": km,
        "max_score": 500,
        "km": km,
        "land": next((name for low, name in LANDS if km >= low), "The woods"),
        "misses": sum(p["tier"] == "Miss" for p in pins),
        "timed": False,
        "time_secs": between(1, 600),
        "further_than": where(
            "a fraction, or none", lambda v: v is None or 0 <= v <= 1
        ),
        "row": "".join(EMOJI[str(p["tier"])] for p in pins),
        "pins": where(
            "the countries pinned, with their tiers and km",
            lambda got: (
                [{k: g[k] for k in ("country", "tier", "km")} for g in got] == pins
            ),
        ),
    }


DRIVER = Driver(name="farflung", scenarios={"finish": finish})
