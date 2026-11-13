import pytest

from src.games.loader import ConfigError, check_modes, modes_of
from src.games.models import Game


def _game(name: str, **config: str) -> Game:
    return Game.model_validate(
        {"name": name, "origin": "https://example.com", **config}
    )


def _games(*games: Game) -> dict[str, Game]:
    return {game.name: game for game in games}


def test_modes_stack_under_the_game_they_are_modes_of() -> None:
    games = _games(
        _game("zeta", mode="Classic"),
        _game("beta", mode="Speed", mode_of="zeta"),
        _game("alpha", mode="Hard", mode_of="zeta"),
        _game("solo"),
    )
    check_modes(games)
    expected = ["zeta", "alpha", "beta"]
    assert [g.name for g in modes_of(games, games["beta"])] == expected
    assert [g.name for g in modes_of(games, games["zeta"])] == expected
    assert [g.name for g in modes_of(games, games["solo"])] == ["solo"]
    assert games["alpha"].group == "zeta"
    assert games["solo"].group == "solo"


@pytest.mark.parametrize(
    "games",
    [
        # mode_of names no game, or itself
        [_game("a", mode="X", mode_of="nope")],
        [_game("a", mode="X", mode_of="a")],
        # a mode of a mode
        [
            _game("a", mode="X"),
            _game("b", mode="Y", mode_of="a"),
            _game("c", mode="Z", mode_of="b"),
        ],
        # a missing mode, on either side
        [_game("a"), _game("b", mode="Y", mode_of="a")],
        [_game("a", mode="X"), _game("b", mode_of="a")],
        # a mode with nothing to stack with
        [_game("a", mode="X")],
        # the same mode twice
        [_game("a", mode="X"), _game("b", mode="X", mode_of="a")],
    ],
)
def test_check_modes_rejects(games: list[Game]) -> None:
    with pytest.raises(ConfigError):
        check_modes(_games(*games))
