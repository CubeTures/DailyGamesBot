"""Chess.com's daily puzzle: the page fetches every recent day's puzzle,
solution included, from its GetDailyPuzzlesByRange RPC. learn() reads today's
PGN from that response; python-chess turns it into squares to click.

The player's moves are every other one from the start position; the site
plays the replies. A wrong (but legal) move breaks a heart and is undone with
"Retry".
"""

import io
from contextlib import suppress

import chess
import chess.pgn
from playwright.sync_api import Response

from tests.e2e.harness import Driver, Expected, Player, Solution
from tests.e2e.solutions import game_day

HEARTS = 5

# The board's corner, square size and orientation, for clicking squares.
GEOMETRY = """() => {
  const b = document.querySelector("wc-chess-board");
  const r = b.getBoundingClientRect();
  return {x: r.x, y: r.y, size: r.width / 8, flipped: b.classList.contains("flipped")};
}"""


def _is_puzzles(response: Response) -> bool:
    return "DailyPuzzleService/GetDailyPuzzlesByRange" in response.url


def learn(player: Player) -> Solution:
    day = game_day(player.game).isoformat()
    with player.page.expect_response(_is_puzzles) as info:
        player.open()
    puzzle = next(
        (p for p in info.value.json()["dailyPuzzles"] if p["date"] == day), None
    )
    assert puzzle, f"no daily puzzle for {day} in GetDailyPuzzlesByRange"
    game = chess.pgn.read_game(io.StringIO(puzzle["pgn"]))
    assert game, "unreadable PGN"
    return {
        "date": day,
        "fen": game.board().fen(),
        "moves": [m.uci() for m in game.mainline_moves()],
    }


def _click(player: Player, square: str) -> None:
    geo = player.page.evaluate(GEOMETRY)
    file, rank = ord(square[0]) - ord("a"), int(square[1]) - 1
    col, row = (7 - file, rank) if geo["flipped"] else (file, 7 - rank)
    size = geo["size"]
    player.page.mouse.click(
        geo["x"] + (col + 0.5) * size, geo["y"] + (row + 0.5) * size
    )
    player.page.wait_for_timeout(250)


def _move(player: Player, move: chess.Move) -> None:
    _click(player, chess.square_name(move.from_square))
    _click(player, chess.square_name(move.to_square))
    if move.promotion:
        symbol = chess.piece_symbol(move.promotion)
        player.page.locator(f".promotion-piece[class*='{symbol}']").first.click()
    # The site's reply (or the "Incorrect" state) animates in.
    player.page.wait_for_timeout(1500)


def _wrong(board: chess.Board, right: chess.Move) -> chess.Move:
    """A legal move that isn't the solution's (nor mate, which any puzzle
    accepts)."""
    for move in board.legal_moves:
        if move == right:
            continue
        board.push(move)
        mate = board.is_checkmate()
        board.pop()
        if not mate:
            return move
    raise AssertionError("no wrong move available")


def _play(player: Player, solution: Solution, *, mistakes: int, finish: bool) -> None:
    """Make `mistakes` wrong moves (each retried) on the first move, then play
    the solution if `finish`."""
    page = player.page
    board = chess.Board(solution["fen"])
    # The board loads White-side-up and only flips for a Black puzzle once
    # the position is set up; clicking before then hits the wrong squares.
    flipped = "true" if board.turn == chess.BLACK else "false"
    page.wait_for_function(
        f"document.querySelector('wc-chess-board')?.classList.contains('flipped') === {flipped}"
        " && document.querySelectorAll('wc-chess-board .piece').length > 0"
    )
    # First visits get a "Daily Chess Puzzle" welcome modal over the board.
    # Board clicks are raw mouse clicks, which no overlay handler sees, so
    # close it first.
    welcome = page.locator(".modal-first-time-modal").get_by_role(
        "button", name="Close"
    )
    with suppress(Exception):
        welcome.click(timeout=5000)
    page.wait_for_timeout(1000)
    moves = [chess.Move.from_uci(m) for m in solution["moves"]]
    for _ in range(mistakes):
        _move(player, _wrong(board, moves[0]))
        retry = page.get_by_role("button", name="Retry")
        if retry.is_visible():
            retry.click()
            page.wait_for_timeout(800)
    if not finish:
        return
    for n, move in enumerate(moves):
        if n % 2 == 0:  # the player's; the site plays the rest
            _move(player, move)
        board.push(move)


def _expected(solution: Solution, mistakes: int) -> Expected:
    return {
        "puzzle_id": solution["date"],
        "won": mistakes < HEARTS,
        "score": mistakes,
        "max_score": HEARTS,
    }


def win(player: Player, solution: Solution) -> Expected:
    _play(player, solution, mistakes=0, finish=True)
    return _expected(solution, 0)


def lose(player: Player, solution: Solution) -> Expected:
    _play(player, solution, mistakes=HEARTS, finish=False)
    return _expected(solution, HEARTS)


def mixed(player: Player, solution: Solution) -> Expected:
    _play(player, solution, mistakes=2, finish=True)
    return _expected(solution, 2)


DRIVER = Driver(
    name="chess",
    learn=learn,
    scenarios={"win": win, "lose": lose, "mixed": mixed},
)
