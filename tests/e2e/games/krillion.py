"""Krillion: answers are free text, scored by the server, and there's no
answer list to learn. A nonsense answer is just rejected ("no echo"); a round
is only missed when its 25s clock runs out. So:

- "misses" lets every round time out (fully deterministic, ~3.5 minutes);
- "answered" and "mixed" try answers from a small bank, picked by keywords in
  the prompt, until one is accepted. Which ones land varies by day, so the
  expected fields come from the server's own /api/submit responses.
"""

import re
from typing import Any

from playwright.sync_api import Response

from tests.e2e.expect import where
from tests.e2e.harness import Driver, Expected, Player, Solution

ROUNDS = 7

# Candidate answers by prompt keyword (a regex searched in the prompt).
BANK: dict[str, list[str]] = {
    r"\bcar|vehicle|automo": [
        "Ferrari",
        "Porsche",
        "Toyota",
        "Ford",
        "BMW",
        "Honda",
        "Lamborghini",
    ],
    r"countr|nation": [
        "Canada",
        "Japan",
        "Chad",
        "France",
        "Brazil",
        "Panama",
        "Peru",
        "Egypt",
    ],
    r"\bcit(y|ies)|capital": ["Paris", "London", "Tokyo", "Chicago", "Rome", "Berlin"],
    r"animal|pet|mammal|bird|fish|insect": [
        "dog",
        "cat",
        "lion",
        "eagle",
        "shark",
        "horse",
        "bee",
    ],
    r"colou?r": ["red", "blue", "green", "purple", "orange", "black"],
    r"fruit|vegetable|food|eat|snack|dish|ingredient": [
        "apple",
        "banana",
        "pizza",
        "carrot",
        "bread",
        "cheese",
        "rice",
    ],
    r"drink|beverage": ["coffee", "tea", "water", "beer", "wine", "milk"],
    r"sport|game|grass|ball": [
        "soccer",
        "football",
        "golf",
        "tennis",
        "cricket",
        "rugby",
        "baseball",
    ],
    r"shirt|cloth|wear|garment|outfit": [
        "collar",
        "sleeve",
        "button",
        "pocket",
        "cuff",
        "hat",
        "shoes",
    ],
    r"symptom|sick|ill|cold|flu|disease": [
        "cough",
        "fever",
        "sneeze",
        "headache",
        "runny nose",
        "chills",
    ],
    r"body|organ|bone": ["heart", "arm", "leg", "brain", "liver", "knee"],
    r"ceremon|celebrat|holiday|party|stage of life": [
        "wedding",
        "graduation",
        "birthday",
        "funeral",
        "baptism",
        "bar mitzvah",
    ],
    r"filter": ["coffee maker", "air purifier", "water", "pool", "vacuum", "furnace"],
    r"instrument|music": ["guitar", "piano", "drums", "violin", "flute"],
    r"job|profession|occupation|career": [
        "doctor",
        "teacher",
        "nurse",
        "chef",
        "lawyer",
    ],
    r"kitchen|tool|utensil": ["knife", "spoon", "fork", "hammer", "pan"],
    r"weather": ["rain", "snow", "wind", "fog", "hail"],
    r"movie|film": ["Titanic", "Jaws", "Star Wars", "Frozen"],
}
GENERIC = [
    "water",
    "dog",
    "red",
    "apple",
    "paper",
    "phone",
    "tree",
    "car",
    "book",
    "coffee",
]


def _candidates(prompt: str) -> list[str]:
    picked: list[str] = []
    for pattern, answers in BANK.items():
        if re.search(pattern, prompt, re.IGNORECASE):
            picked += answers
    return [*dict.fromkeys(picked + GENERIC)]


def _today(player: Player) -> dict[str, Any]:
    res = player.fetch("/api/today")
    assert res.ok, f"Krillion /api/today: {res.status}"
    return res.json()


def _answer(player: Player, prompt: str) -> dict[str, Any] | None:
    """Try candidates until one is accepted or the clock runs out; the
    accepted /api/submit response, if any."""
    page = player.page
    box = page.get_by_role("textbox", name="Your answer")
    for candidate in _candidates(prompt):
        if not box.is_visible():
            return None
        try:
            with page.expect_response(_is_submit, timeout=8000) as info:
                box.fill(candidate)
                page.keyboard.press("Enter")
            body = info.value.json()
        except Exception:
            return None  # the round ended mid-answer
        if body.get("accepted"):
            return body
    return None


def _is_submit(response: Response) -> bool:
    return response.url.endswith("/api/submit") and response.request.method == "POST"


def _dive(player: Player, answer_rounds: set[int]) -> list[dict[str, Any] | None]:
    """Play every round, answering those in `answer_rounds` and letting the
    others time out; each round's accepted submit response (None for a miss)."""
    page = player.page
    prompts = [p["text"] for p in _today(player)["prompts"]]
    page.get_by_role("button", name="▼ BEGIN DESCENT ▼").click(
        force=True
    )  # bobs forever
    box = page.get_by_role("textbox", name="Your answer")
    accepted: list[dict[str, Any] | None] = []
    for n, prompt in enumerate(prompts):
        box.wait_for(timeout=20000)
        result = _answer(player, prompt) if n in answer_rounds else None
        accepted.append(result)
        if result is None:
            box.wait_for(state="hidden", timeout=40000)  # let the clock run out
        # The last round's button surfaces to the results, which is when the
        # day is recorded.
        last = n == len(prompts) - 1
        page.get_by_role("button", name="SURFACE ▲" if last else "DESCEND ▼").click(
            force=True, timeout=20000
        )
    return accepted


def _expected(player: Player, accepted: list[dict[str, Any] | None]) -> Expected:
    today = _today(player)
    tiers = [r["tier"] if r else "miss" for r in accepted]
    score = sum(r["score"] for r in accepted if r)
    answers = [r["answer"] if r else None for r in accepted]
    return {
        "puzzle_id": today["date"],
        "puzzle_number": today["dayNumber"],
        "score": score,
        "max_score": 700,
        "depth_m": score * 10,
        "tiers": tiers,
        "round_scores": [r["score"] if r else 0 for r in accepted],
        "misses": tiers.count("miss"),
        "answers": where(
            f"each round's answer as accepted: {answers}",
            lambda got: (
                len(got) == ROUNDS
                and all(
                    (g["answer"] or None) == a
                    for g, a in zip(got, answers, strict=True)
                )
            ),
        ),
        "share_text": where(
            f"starts 'Krillion #{today['dayNumber']}'",
            lambda t: t.startswith(f"Krillion #{today['dayNumber']} "),
        ),
    }


def misses(player: Player, solution: Solution) -> Expected:
    """There's no losing; missing every round scores 0."""
    return _expected(player, _dive(player, set()))


def answered(player: Player, solution: Solution) -> Expected:
    accepted = _dive(player, set(range(ROUNDS)))
    return _expected(player, accepted)


def mixed(player: Player, solution: Solution) -> Expected:
    accepted = _dive(player, {0, 2, 4, 6})
    return _expected(player, accepted)


DRIVER = Driver(
    name="krillion",
    scenarios={"answered": answered, "misses": misses, "mixed": mixed},
)
