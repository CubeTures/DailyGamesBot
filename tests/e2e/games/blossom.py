"""Blossom: Merriam-Webster's Phaser game on a canvas, so it's played with
the keyboard. The game caches today's puzzle, every valid word included, in
localStorage, so learn() reads it from there. There's no losing: every game
is 12 words, so the scenarios are the best words and the worst.
"""

import json
from typing import Any

from playwright.sync_api import Position

from tests.e2e.expect import where
from tests.e2e.harness import Driver, Expected, Player, Solution

KEY = "gameData-blossom-word-game"
# The game's date key: the browser's local date, en-US ("10/15/2026").
TODAY = "new Date().toLocaleDateString('en-US')"

# The PLAY button on the title screen, in canvas coordinates.
PLAY: Position = {"x": 240, "y": 405}


def _data(player: Player) -> dict[str, Any]:
    return player.page.evaluate(f"JSON.parse(localStorage.getItem('{KEY}'))")


def _state(player: Player) -> dict[str, Any]:
    """Today's first attempt: words, points_per_word, score..."""
    return player.page.evaluate(
        f"JSON.parse(localStorage.getItem('{KEY}'))?.puzzleStates?.[{TODAY}]?.[0]"
        " ?? {words: []}"
    )


def _loaded(player: Player) -> None:
    player.page.wait_for_function(
        f"window.blossom?.loaded && JSON.parse(localStorage.getItem('{KEY}'))"
        f"?.puzzleCache?.[{TODAY}]"
    )


def learn(player: Player) -> Solution:
    player.open()
    _loaded(player)
    puzzle = player.page.evaluate(
        f"JSON.parse(localStorage.getItem('{KEY}')).puzzleCache[{TODAY}]"
    )
    return {
        "game_id": puzzle["GameId"],
        "letters": puzzle["Center"] + puzzle["Letters"],
        "words": puzzle["Words"],
    }


def _start(player: Player) -> None:
    """Turn the tips off (each one blocks typing until closed), then press
    PLAY."""
    page = player.page
    _loaded(player)
    data = _data(player)
    # Tips show while their count is under the game's limit for them.
    data["tooltipShowCount"] = {"1": 99, "2": 99, "4": 99, "8": 99}
    page.evaluate("([k, v]) => localStorage.setItem(k, v)", [KEY, json.dumps(data)])
    page.reload(wait_until="domcontentloaded")
    _loaded(player)
    page.wait_for_timeout(1500)
    page.locator("#gameWrapper canvas").click(position=PLAY)
    page.wait_for_timeout(2500)


def _play(player: Player, words: list[str]) -> None:
    _start(player)
    page = player.page
    for i, word in enumerate(words):
        # Keys are dropped while a word's animation plays (a pangram's runs
        # for a few seconds), so clear what got through and retype.
        for _ in range(3):
            for _ in range(len(word) + 2):
                page.keyboard.press("Backspace")
            page.keyboard.type(word, delay=60)
            page.keyboard.press("Enter")
            # Bounded: the word has to land in the saved state.
            for _ in range(12):
                if len(_state(player)["words"]) > i:
                    break
                page.wait_for_timeout(250)
            else:
                page.wait_for_timeout(2000)
                continue
            break
        found = _state(player)["words"]
        assert found[i:] == [word], f"driver problem: typed {word!r}, got {found[i:]}"
        # Keys typed during the word's animation are dropped, so a word typed
        # too soon goes in without its first letters (UNDETERRED as DETERRED).
        page.wait_for_timeout(3000)


def _is_pangram(word: str) -> bool:
    return len(word) >= 7 and len(set(word)) == 7


def _base_points(word: str) -> int:
    """A word's points before bonus letters (the game's calculateScore)."""
    n = len(word)
    points = {4: 2, 5: 4, 6: 6}.get(n, 12 + 3 * (n - 7))
    return points + (7 if _is_pangram(word) else 0)


def _expected(solution: Solution, words: list[str]) -> Expected:
    base = [_base_points(w) for w in words]

    def scored(word_scores: list[dict[str, Any]]) -> bool:
        # Each word scores its base plus 5 per bonus letter it uses.
        return [s["word"] for s in word_scores] == words and all(
            s["points"] >= b and (s["points"] - b) % 5 == 0
            for s, b in zip(word_scores, base, strict=True)
        )

    return {
        "puzzle_id": str(solution["game_id"]),
        "puzzle_number": solution["game_id"],
        "score": where(
            f"at least {sum(base)}, plus bonus letters",
            lambda s: s >= sum(base) and (s - sum(base)) % 5 == 0,
        ),
        "words": 12,
        "pangrams": sum(_is_pangram(w) for w in words),
        "longest_word": max(len(w) for w in words),
        "word_scores": where("the words typed, each scored", scored),
    }


def best(player: Player, solution: Solution) -> Expected:
    """The 12 longest words, pangrams first."""
    words = sorted(solution["words"], key=lambda w: (not _is_pangram(w), -len(w)))
    words = words[:12]
    _play(player, words)
    return _expected(solution, words)


def worst(player: Player, solution: Solution) -> Expected:
    """The 12 shortest words."""
    words = sorted(solution["words"], key=len)[:12]
    _play(player, words)
    return _expected(solution, words)


DRIVER = Driver(
    name="blossom",
    learn=learn,
    scenarios={"best": best, "worst": worst},
)
