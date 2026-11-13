"""Costcodle Checkout: the five products and their prices come from the
site's own games.json, picked by today's game number as the page picks them
(scripts/checkout/daily.js). The page opens on Checkout, so no mode switch."""

from tests.e2e.harness import Driver, Expected, Player, Solution

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


def learn(player: Player) -> Solution:
    page = player.open()
    page.wait_for_function("!!window.CostcodleDaily")
    game_number: int = page.evaluate(_GAME_NUMBER)
    return page.evaluate(
        """async (n) => {
          const catalog = await (await fetch("./games.json")).json();
          const products = CostcodleDaily.checkoutProductIds(n).map(id => {
            const e = catalog[`game-${id}`];
            const cents = typeof e.price === "number" ? Math.round(e.price * 100)
              : Math.round(Number(String(e.price).replace(/[$,\\s]/g, "")) * 100);
            return {name: e.short || e.name, cents};
          });
          return {game_number: n, products};
        }""",
        game_number,
    )


def _play(player: Player, solution: Solution, factors: list[float]) -> list[int]:
    """Guess price × each factor; returns each guess in cents."""
    page = player.page
    player.dismiss(page.locator("[data-close-announce]"))
    guesses = [
        round(p["cents"] * f)
        for p, f in zip(solution["products"], factors, strict=True)
    ]
    # A quick game otherwise lands within a second or two of the page load.
    page.wait_for_timeout(1500)
    for i, cents in enumerate(guesses):
        page.locator("#input-row .guess-input").fill(f"{cents / 100:.2f}")
        page.locator(".guess-button").click()
        if i < len(guesses) - 1:
            # The receipt prints the price, then Next brings the next product.
            page.locator("[data-next-round]").click(timeout=15000)
    return guesses


def _expected(solution: Solution, guesses: list[int]) -> Expected:
    products = solution["products"]
    offs = [abs(g - p["cents"]) for g, p in zip(guesses, products, strict=True)]
    total = sum(offs)

    def row(off: int, price: int) -> str:
        pct = off / price
        if pct <= 0.05:
            return ":white_check_mark:"
        return ":yellow_square:" if pct <= 0.25 else ":red_square:"

    number = solution["game_number"] - 1147
    return {
        "puzzle_id": str(number),
        "puzzle_number": number,
        "score": total / 100,
        "total_cents": total,
        "rating": next(
            (r for limit, r in _RATINGS if total <= limit), "Forgot your card"
        ),
        "items": [
            {
                "name": p["name"],
                "guess_cents": g,
                "price_cents": p["cents"],
                "off_cents": o,
            }
            for p, g, o in zip(products, guesses, offs, strict=True)
        ],
        "rows": [row(o, p["cents"]) for o, p in zip(offs, products, strict=True)],
    }


def exact(player: Player, solution: Solution) -> Expected:
    return _expected(solution, _play(player, solution, [1] * 5))


def far_off(player: Player, solution: Solution) -> Expected:
    return _expected(solution, _play(player, solution, [3, 0.3, 2, 0.5, 4]))


def mixed(player: Player, solution: Solution) -> Expected:
    # Within 5%, within 25% and further, both directions.
    return _expected(solution, _play(player, solution, [1.03, 0.85, 1.2, 0.5, 1]))


DRIVER = Driver(
    name="costcodlecheckout",
    learn=learn,
    scenarios={"exact": exact, "far_off": far_off, "mixed": mixed},
)
