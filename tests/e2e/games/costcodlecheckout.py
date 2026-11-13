"""Costcodle Checkout: five products, each priced by a guess. There's no
losing, so this guesses $1.00 for every product and needs no prices: the
result is checked against the guesses and for adding up (each product's
off_cents is its price less a dollar, and the total is their sum). The page
opens on Checkout, so no mode switch."""

from typing import Any

from tests.e2e.expect import ALL, where
from tests.e2e.harness import Driver, Expected, Player, Solution

PRODUCTS = 5
GUESS_CENTS = 100

# Today's game number as scripts/checkout/daily.js getGameNumber() counts it.
_GAME_NUMBER = """() => {
  const d = new Date();
  return Math.floor((Date.UTC(d.getFullYear(), d.getMonth(), d.getDate())
    - Date.UTC(2023, 8, 21)) / 864e5) + 2;
}"""

_RATINGS = [
    (500, "Executive member"),
    (1500, "Gold star member"),
    (3000, "Bulk buyer"),
    (6000, "Free sample hunter"),
    (15000, "Lost in aisle 12"),
]


def _rating(total: int) -> str:
    return next((r for limit, r in _RATINGS if total <= limit), "Forgot your card")


def _row(off: int, price: int) -> str:
    pct = off / price
    if pct <= 0.05:
        return ":white_check_mark:"
    return ":yellow_square:" if pct <= 0.25 else ":red_square:"


def _items_add_up(items: list[dict[str, Any]]) -> bool:
    return len(items) == PRODUCTS and all(
        i["name"]
        and i["guess_cents"] == GUESS_CENTS
        and i["price_cents"] > 0
        and i["off_cents"] == abs(GUESS_CENTS - i["price_cents"])
        for i in items
    )


def play(player: Player, _solution: Solution) -> Expected:
    page = player.page
    player.dismiss(page.locator("[data-close-announce]"))
    game_number: int = page.evaluate(_GAME_NUMBER)
    # A quick game otherwise lands within a second or two of the page load.
    page.wait_for_timeout(1500)
    for i in range(PRODUCTS):
        page.locator("#input-row .guess-input").fill(f"{GUESS_CENTS / 100:.2f}")
        page.locator(".guess-button").click()
        if i < PRODUCTS - 1:
            # The receipt prints the price, then Next brings the next product.
            page.locator("[data-next-round]").click(timeout=15000)

    number = game_number - 1147
    return {
        "puzzle_id": str(number),
        "puzzle_number": number,
        "items": where(
            f"{PRODUCTS} named products, each guessed at {GUESS_CENTS}¢ and off"
            " by |price - guess|",
            _items_add_up,
        ),
        ALL: where(
            "total_cents the sum of off_cents, score it in dollars, and the"
            " rating and rows to go with them",
            _adds_up,
        ),
    }


def _adds_up(fields: dict[str, Any]) -> bool:
    items = fields["items"]
    total = sum(i["off_cents"] for i in items)
    return (
        fields["total_cents"] == total
        and fields["score"] == total / 100
        and fields["rating"] == _rating(total)
        and fields["rows"] == [_row(i["off_cents"], i["price_cents"]) for i in items]
    )


DRIVER = Driver(name="costcodlecheckout", play=play)
