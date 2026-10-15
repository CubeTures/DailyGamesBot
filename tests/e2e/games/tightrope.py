"""Tightrope: Britannica's daily trivia, nine multiple-choice questions on a
15-second timer each; three wrong and you fall. The game's own quiz API
(through the proxy) gives every question with its correct answer, so learn()
reads it from there.

Britannica sits behind Cloudflare, which starts challenging the browser (a
"security verification" page, or a 403 on the quiz API) after many plays in
a short time; failures then are that, not the capture. Wait and rerun.
"""

from typing import Any

from tests.e2e.expect import between, where
from tests.e2e.harness import Driver, Expected, Player, Solution
from tests.e2e.solutions import game_day

# The game's difficulty bonus for crossing, by weekday (Monday first).
BONUS = [200, 220, 240, 260, 280, 300, 320]

RIGHT = ":white_check_mark:"
WRONG = ":broken_heart:"
UNSEEN = ":white_large_square:"


def learn(player: Player) -> Solution:
    day = game_day(player.game)
    # From the page: Cloudflare turns away the API request made outside it.
    page = player.open()
    data: dict[str, Any] = page.evaluate(
        "async url => { const r = await fetch(url);"
        " if (!r.ok) throw new Error(`Tightrope API: ${r.status}`); return r.json(); }",
        f"/ajax/quiz/tightrope?date={day:%Y%m%d}",
    )
    return {
        "id": data["id"],
        "weekday": day.weekday(),
        "questions": [
            {"answers": q["answers"], "correct": q["correctAnswerIndex"]}
            for q in data["questions"]
        ],
    }


def _start(player: Player) -> None:
    page = player.page
    # The How to Play dialog opens on a browser's first visit and covers the
    # Play button; the game skips it once its settings say it's been seen.
    page.evaluate(
        "localStorage.setItem('TR_USER_SETTINGS', JSON.stringify("
        "{isSoundEnabled: false, knowsHowToPlay: true, knowsReviewAnswers: true}))"
    )
    page.reload(wait_until="domcontentloaded")
    page.get_by_test_id("PlayButton").click()
    page.get_by_test_id("AnswerButton").first.wait_for()


def _answer(player: Player, n: int, text: str) -> None:
    """Answer question n (from 0) with the option reading `text`."""
    page = player.page
    card = page.get_by_test_id("QuestionCard")
    card.filter(has_text=f"{n + 1}/9").wait_for(timeout=30_000)
    button = page.get_by_test_id("AnswerButton").filter(has_text=text).first
    # Answers unlock once the question has shown for a moment.
    page.wait_for_function(
        "t => [...document.querySelectorAll('[data-testid=AnswerButton]')]"
        ".some(b => b.innerText.trim() === t && !b.disabled)",
        arg=text,
    )
    button.click()
    # Let the reveal and the walk to the next flag play.
    page.wait_for_timeout(2500)


def _play(player: Player, solution: Solution, right: list[bool]) -> None:
    _start(player)
    for n, ok in enumerate(right):
        q = solution["questions"][n]
        pick = q["correct"] if ok else (q["correct"] + 1) % len(q["answers"])
        _answer(player, n, q["answers"][pick])


def _expected(solution: Solution, right: list[bool]) -> Expected:
    won = len(right) == 9
    correct = sum(right)
    weekday: int = solution["weekday"]
    bonus = BONUS[weekday] if won else 0
    bar = "".join(RIGHT if ok else WRONG for ok in right) + UNSEEN * (9 - len(right))
    return {
        "puzzle_id": str(solution["id"]),
        "puzzle_number": solution["id"],
        "won": won,
        "answer_points": 100 * correct,
        # 10 per second left, up to 15 s, on each right answer
        "time_bonus": between(0, 150 * correct),
        "difficulty_bonus": bonus,
        "score": between(100 * correct + bonus, 250 * correct + bonus),
        "correct": correct,
        "wrong": len(right) - correct,
        "rank": where("a rank", bool) if won else None,
        "bar": bar + (" :tada:" if won else " :face_with_head_bandage:"),
    }


def _run(player: Player, solution: Solution, right: list[bool]) -> Expected:
    _play(player, solution, right)
    return _expected(solution, right)


def win(player: Player, solution: Solution) -> Expected:
    return _run(player, solution, [True] * 9)


def lose(player: Player, solution: Solution) -> Expected:
    return _run(player, solution, [True, False, False, False])


def mixed(player: Player, solution: Solution) -> Expected:
    return _run(player, solution, [False, True, True, False, *[True] * 5])


DRIVER = Driver(
    name="tightrope",
    learn=learn,
    scenarios={"win": win, "lose": lose, "mixed": mixed},
)
