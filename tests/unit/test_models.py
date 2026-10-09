from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from src.games.models import GameConfig, Reset

BASE = {"name": "demo", "origin": "https://example.com/"}


def test_reset_day_at_shifts_by_reset_time_in_its_timezone() -> None:
    reset = Reset(time="06:00", timezone="America/New_York")
    # 09:00 UTC is 05:00 in New York (EDT), before the 06:00 reset.
    assert reset.day_at(datetime(2026, 10, 8, 9, 0, tzinfo=UTC)) == date(2026, 10, 7)
    assert reset.day_at(datetime(2026, 10, 8, 11, 0, tzinfo=UTC)) == date(2026, 10, 8)


def test_reset_js_config() -> None:
    assert Reset().js_config() == {"minutes": 0, "timezone": None}
    assert Reset(time="01:30", timezone="UTC").js_config() == {
        "minutes": 90,
        "timezone": "UTC",
    }


def test_config_defaults() -> None:
    config = GameConfig.model_validate(BASE)
    assert config.title == "Demo"
    assert config.origin == "https://example.com"
    assert config.triggers == []


@pytest.mark.parametrize(
    "override",
    [
        {"higher_score_wins": "true"},
        {"name": "has_underscore"},
        {"reset": {"timezone": "Mars/Olympus"}},
        {"reset": {"time": "24:00"}},
        {
            "triggers": [
                {"name": "a", "type": "page"},
                {"name": "a", "type": "page"},
            ]
        },
        {"triggers": [{"name": "a", "type": "network", "url": "("}]},
    ],
)
def test_config_rejects(override: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        GameConfig.model_validate({**BASE, **override})
