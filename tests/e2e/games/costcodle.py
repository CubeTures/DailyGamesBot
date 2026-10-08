"""Costcodle: the price comes from the site's own games.json, read off the
page once it has loaded today's product."""

from tests.e2e.expect import where
from tests.e2e.harness import Driver, Expected, Player, Solution


def learn(player: Player) -> Solution:
    page = player.open()
    page.wait_for_function("typeof productPrice === 'number'")
    return page.evaluate(
        "({game_number: getGameNumber(), price: productPrice, name: productName})"
    )


def _row(guess: float, price: float) -> str:
    """The share row the game shows for a guess (its checkGuess())."""
    percent = guess / price * 100 - 100
    if abs(percent) <= 5:
        return ":white_check_mark:"
    arrow = ":arrow_up:" if percent < 0 else ":arrow_down:"
    return arrow + (":yellow_square:" if abs(percent) <= 25 else ":red_square:")


def _play(player: Player, solution: Solution, factors: list[float]) -> list[str]:
    """Guess price × each factor; returns the guesses as the game stores them."""
    page = player.page
    page.wait_for_function("typeof productPrice === 'number'")
    guesses = [f"{solution['price'] * f:.2f}" for f in factors]
    for guess in guesses:
        page.locator("#guess-input").fill(guess)
        page.locator("#guess-button").click()
        page.wait_for_timeout(800)
    return guesses


def _expected(solution: Solution, guesses: list[str], won: bool) -> Expected:
    return {
        "puzzle_id": str(solution["game_number"]),
        "puzzle_number": solution["game_number"],
        "won": won,
        "attempts": len(guesses),
        "score": len(guesses) if won else None,
        "max_score": 6,
        "guesses": guesses,
        "rows": [_row(float(g), solution["price"]) for g in guesses],
        "product": where(
            f"mentions {solution['name']!r}", lambda p: solution["name"] in p
        ),
    }


def win(player: Player, solution: Solution) -> Expected:
    return _expected(solution, _play(player, solution, [1]), won=True)


def lose(player: Player, solution: Solution) -> Expected:
    # Far and near, both directions.
    guesses = _play(player, solution, [3, 0.3, 2, 0.5, 1.2, 0.85])
    return _expected(solution, guesses, won=False)


def mixed(player: Player, solution: Solution) -> Expected:
    guesses = _play(player, solution, [0.5, 1.15, 1.02])
    return _expected(solution, guesses, won=True)


DRIVER = Driver(
    name="costcodle",
    learn=learn,
    scenarios={"win": win, "lose": lose, "mixed": mixed},
)
