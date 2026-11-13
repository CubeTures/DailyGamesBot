import json
import re

import pytest

from src.games.models import Game
from src.launcher import build


def _game(name: str, **config: str) -> Game:
    return Game.model_validate(
        {"name": name, "origin": "https://example.com", **config}
    )


@pytest.fixture(autouse=True)
def games(monkeypatch: pytest.MonkeyPatch) -> None:
    games = [
        _game("zeta", title="Zeta", mode="Classic"),
        _game("zetafast", title="Zeta Fast", mode="Speed", mode_of="zeta"),
        _game("solo", title="Solo"),
    ]
    monkeypatch.setattr(build, "GAMES_BY_NAME", {game.name: game for game in games})


def _json_script(page: str, element_id: str) -> object:
    match = re.search(
        rf'<script id="{element_id}" type="application/json">(.*?)</script>', page
    )
    assert match
    return json.loads(match.group(1))


def test_full_title() -> None:
    assert build.full_title(build.GAMES_BY_NAME["zeta"]) == "Zeta Classic"
    assert build.full_title(build.GAMES_BY_NAME["zetafast"]) == "Zeta Speed"
    assert build.full_title(build.GAMES_BY_NAME["solo"]) == "Solo"


def test_modes_render_as_one_stack() -> None:
    page = build.render_launcher()
    assert page.count('class="stack"') == 1
    stack = page.split('<div class="stack" data-group="zeta">', 1)[1]
    assert stack.index('data-game="zeta"') < stack.index('data-game="zetafast"')
    assert 'data-game="solo"' in page
    assert _json_script(page, "modes") == {
        "zeta": [
            {"game": "zeta", "mode": "Classic"},
            {"game": "zetafast", "mode": "Speed"},
        ]
    }
    assert _json_script(page, "full-titles") == {
        "solo": "Solo",
        "zeta": "Zeta Classic",
        "zetafast": "Zeta Speed",
    }
