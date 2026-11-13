"""Costcodle: the price is a page global (productPrice) once the page has
loaded today's product. This is the Classic mode; the
five-product Checkout mode the page opens on is costcodlecheckout.py."""

from tests.e2e.expect import where
from tests.e2e.harness import Driver, Expected, Player, Solution


def _row(guess: float, price: float) -> str:
    """The share row the game shows for a guess (its checkGuess())."""
    percent = guess / price * 100 - 100
    if abs(percent) <= 5:
        return ":white_check_mark:"
    arrow = ":arrow_up:" if percent < 0 else ":arrow_down:"
    return arrow + (":yellow_square:" if abs(percent) <= 25 else ":red_square:")


def play(player: Player, _solution: Solution) -> Expected:
    """Half the price, then the price (read off the page): a win with a row
    that isn't a check."""
    page = player.page
    # The page opens on its Checkout mode, under a notice announcing it; the
    # Classic game (the one captured) is the other tab, also reached by
    # ?mode=classic. A click on the tab can land while the notice closes.
    player.dismiss(page.locator("[data-close-announce]"))
    page.goto(player.url("/?mode=classic"), wait_until="domcontentloaded")
    page.wait_for_function("document.body.dataset.gameMode === 'classic'")
    page.wait_for_function("typeof productPrice === 'number'")
    solution = page.evaluate(
        "({game_number: getGameNumber(), price: productPrice, name: productName})"
    )
    guesses = [f"{solution['price'] * f:.2f}" for f in (0.5, 1)]
    # A one-guess win otherwise lands within half a second of the page load,
    # and the capture's timer rightly reports time_secs 0.
    page.wait_for_timeout(1500)
    for guess in guesses:
        page.locator("#guess-input").fill(guess)
        page.locator("#guess-button").click()
        page.wait_for_timeout(800)
    return {
        "puzzle_id": str(solution["game_number"]),
        "puzzle_number": solution["game_number"],
        "won": True,
        "attempts": 2,
        "score": 2,
        "max_score": 6,
        "guesses": guesses,
        "rows": [_row(float(g), solution["price"]) for g in guesses],
        "product": where(
            f"mentions {solution['name']!r}", lambda p: solution["name"] in p
        ),
    }


DRIVER = Driver(name="costcodle", play=play)
