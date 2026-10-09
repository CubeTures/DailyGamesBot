"""The format of a game's config.toml.

games/schema.json is generated from these models (see games/schema.py), so
editors can check config.toml as it's written.
"""

import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Annotated, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

from src.settings import LAUNCHER_PORT

ICON_MIME_TYPES = {
    ".png": "image/png",
    ".svg": "image/svg+xml",
    ".webp": "image/webp",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}

# fields.js is written as a module so editors treat it as JavaScript; capture
# swaps this for `return` to run it as a function body.
FIELDS_EXPORT_RE = re.compile(r"^export\s+default\s*", re.MULTILINE)

LOCAL_TIMEZONE = "local"

NonEmptyStr = Annotated[str, StringConstraints(min_length=1)]

JsExpr = Annotated[
    str,
    StringConstraints(pattern=r"\S"),
    Field(description="A JavaScript expression, evaluated in the game's page."),
]


def _valid_regex(pattern: str) -> str:
    try:
        re.compile(pattern)
    except re.error as e:
        raise ValueError(f"bad regex: {e}") from e
    return pattern


def _valid_timezone(name: str) -> str:
    if name != LOCAL_TIMEZONE:
        try:
            ZoneInfo(name)
        except (ZoneInfoNotFoundError, ValueError) as e:
            raise ValueError(f"unknown timezone {name!r}") from e
    return name


class _StrictModel(BaseModel):
    # strict: TOML is typed, so "8081" for a port is a mistake, not a coercion.
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


class Reset(_StrictModel):
    """When the game's daily puzzle changes. The solve timer starts afresh
    each game day."""

    time: str = Field(
        default="00:00",
        pattern=r"^([01]\d|2[0-3]):[0-5]\d$",
        description="24-hour HH:MM.",
    )
    timezone: Annotated[str, AfterValidator(_valid_timezone)] = Field(
        default=LOCAL_TIMEZONE,
        description=(
            'An IANA timezone such as "America/New_York", or "local" for the'
            " player's own."
        ),
    )

    @property
    def minutes(self) -> int:
        """Minutes past midnight."""
        hours, minutes = self.time.split(":")
        return int(hours) * 60 + int(minutes)

    @property
    def zone_name(self) -> str | None:
        """The IANA timezone, or None for the player's own."""
        return None if self.timezone == LOCAL_TIMEZONE else self.timezone

    def js_config(self) -> dict[str, int | str | None]:
        """The argument gameDay() in src/games/game_day.js takes."""
        return {"minutes": self.minutes, "timezone": self.zone_name}

    def day_at(self, time: datetime) -> date:
        """The game day `time` falls in: the date, in the reset timezone (the
        server's own for "local"), of `minutes` before it. The Python twin of
        gameDay() in src/games/game_day.js."""
        zone = ZoneInfo(self.zone_name) if self.zone_name else None
        return (time.astimezone(zone) - timedelta(minutes=self.minutes)).date()


class _TriggerBase(_StrictModel):
    name: NonEmptyStr = Field(
        description="Unique within the game; stored with each result."
    )
    when: JsExpr = Field(
        default="true",
        description=(
            'Truthy means "the player has finished, report it". The game\'s'
            " vars.js is in scope."
        ),
    )


class PageTrigger(_TriggerBase):
    """Checked on page load, DOM mutations, storage writes, after any
    fetch/XHR, and every second."""

    type: Literal["page"]


class NetworkTrigger(_TriggerBase):
    """Checked after each fetch/XHR response whose URL matches `url`."""

    type: Literal["network"]
    url: Annotated[NonEmptyStr, AfterValidator(_valid_regex)] = Field(
        description="Regex, searched against the request URL.",
        json_schema_extra={"format": "regex"},
    )
    method: (
        Annotated[
            str,
            StringConstraints(pattern=r"^[A-Za-z]+$"),
            AfterValidator(str.upper),
        ]
        | None
    ) = Field(default=None, description="Only match this HTTP method.")


class EventTrigger(_TriggerBase):
    """Checked when `event` fires on `target`."""

    type: Literal["event"]
    event: NonEmptyStr = Field(description="DOM event name.")
    target: Literal["window", "document"] = "window"


Trigger = Annotated[
    PageTrigger | NetworkTrigger | EventTrigger, Field(discriminator="type")
]


def _unique_trigger_names(triggers: list[Trigger]) -> list[Trigger]:
    names = [t.name for t in triggers]
    if len(set(names)) != len(names):
        raise ValueError("trigger names must be unique")
    return triggers


class GameConfig(_StrictModel):
    model_config = ConfigDict(title="Game config")

    name: str = Field(
        pattern=r"^[a-z][a-z0-9_]*$",
        description="Must match the game's directory name.",
    )
    title: NonEmptyStr = Field(
        default_factory=lambda data: str(data["name"]).title(),
        description="Shown on the launcher. Defaults to the name.",
    )
    description: NonEmptyStr | None = Field(
        default=None,
        description="A line or two about the game, shown on the launcher.",
    )
    icon: str | None = Field(
        default=None,
        pattern=rf"^[\w.-]+({'|'.join(re.escape(e) for e in ICON_MIME_TYPES)})$",
        description=(
            "Image file in the game's directory, shown on the launcher;"
            " square, at least 128px. Defaults to the title's first letter."
        ),
    )
    origin: Annotated[
        str,
        StringConstraints(pattern=r"^https?://"),
        AfterValidator(lambda s: s.rstrip("/")),
    ] = Field(description="The real site, proxied 1:1.")
    port: int = Field(
        ge=1024,
        le=65535,
        description=f"Unique local port ({LAUNCHER_PORT} is the launcher's).",
    )
    landing_path: str = Field(default="/", pattern=r"^/")
    higher_score_wins: bool = Field(
        default=False,
        description=(
            "Rank the scoreboard by highest `score` first. By default the"
            " lowest score (fewest guesses, mistakes) ranks first."
        ),
    )
    reset: Reset = Field(
        default_factory=Reset,
        description="When the daily puzzle changes. Default: the player's midnight.",
    )
    triggers: Annotated[list[Trigger], AfterValidator(_unique_trigger_names)] = Field(
        default_factory=list[Trigger],
        description=(
            "Each says when the player has finished and what to report."
            " They share the game's vars.js and fields.js. A game with no"
            " triggers is still proxied, just not captured."
        ),
    )


class Game(GameConfig):
    """A game's config.toml plus the files beside it."""

    vars_js: str = ""
    fields_js: str = ""
    icon_path: Path | None = None
    announcement_template: str | None = None  # None: announce.DEFAULT_TEMPLATE

    @property
    def local_origin(self) -> str:
        return f"http://localhost:{self.port}"
