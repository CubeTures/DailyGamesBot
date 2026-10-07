"""Single source of truth for which local port maps to which game.

Every game is a directory in `games/` (see games/README.md for the format):
config.toml, plus vars.js, fields.js and announcement.j2. The models below
define config.toml; games/schema.json is generated from them so editors can
check it as it's written. Run
`uv run python3 -m src.proxy.config` to validate every game and regenerate
the schema.
"""

import json
import re
import tomllib
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    TypeAdapter,
    ValidationError,
)

from src import announce

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
GAMES_DIR = REPO_ROOT / "games"
SCHEMA_PATH = GAMES_DIR / "schema.json"

LAUNCHER_PORT = 8090

CONFIG_FILE = "config.toml"
VARS_FILE = "vars.js"
FIELDS_FILE = "fields.js"
ANNOUNCEMENT_FILE = "announcement.j2"
GAME_FILES = (CONFIG_FILE, VARS_FILE, FIELDS_FILE, ANNOUNCEMENT_FILE)

ICON_TYPES = {
    ".png": "image/png",
    ".svg": "image/svg+xml",
    ".webp": "image/webp",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}

# fields.js is a module whose default export is the fields object; capture.py
# swaps this for `return` to run it as a function body.
FIELDS_EXPORT_RE = re.compile(r"^export\s+default\s*", re.MULTILINE)


class ConfigError(Exception):
    pass


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


class _Model(BaseModel):
    # strict: TOML is typed, so "8081" for a port is a mistake, not a coercion.
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


class _TriggerBase(_Model):
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


class GameConfig(_Model):
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
        pattern=rf"^[\w.-]+({'|'.join(re.escape(e) for e in ICON_TYPES)})$",
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
    # The icon's file, if it has one, to read at serve time.
    icon_path: Path | None = None
    # Jinja template for the result announcement; None uses the default.
    announcement: Annotated[str, AfterValidator(announce.check)] | None = None


def _format_errors(where: str, e: ValidationError) -> str:
    lines = [f"{where}:"]
    for err in e.errors(include_url=False):
        loc = ".".join(str(p) for p in err["loc"]) or "(top level)"
        lines.append(f"  {loc}: {err['msg']}")
    return "\n".join(lines)


def _read(game_dir: Path, name: str) -> str | None:
    path = game_dir / name
    return path.read_text() if path.exists() else None


def parse_game(game_dir: Path) -> Game:
    where = f"{game_dir.name}/"
    toml = _read(game_dir, CONFIG_FILE)
    if toml is None:
        raise ConfigError(f"{where}: missing {CONFIG_FILE}")
    try:
        config = GameConfig.model_validate(tomllib.loads(toml))
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"{where}{CONFIG_FILE}: {e}") from e
    except ValidationError as e:
        raise ConfigError(_format_errors(where + CONFIG_FILE, e)) from None
    if config.name != game_dir.name:
        raise ConfigError(f"{where}: 'name' must match the directory name")
    allowed = (*GAME_FILES, *([config.icon] if config.icon else []))
    stray = sorted(p.name for p in game_dir.iterdir() if p.name not in allowed)
    if stray:
        raise ConfigError(
            f"{where}: unexpected {', '.join(stray)}"
            f" (a game holds only {', '.join(GAME_FILES)} and its icon)"
        )
    if config.icon and not (game_dir / config.icon).is_file():
        raise ConfigError(f"{where}{CONFIG_FILE}: icon {config.icon} doesn't exist")

    vars_js = _read(game_dir, VARS_FILE)
    fields_js = _read(game_dir, FIELDS_FILE)
    if config.triggers and fields_js is None:
        raise ConfigError(f"{where}: has triggers but no {FIELDS_FILE}")
    if not config.triggers and (vars_js is not None or fields_js is not None):
        raise ConfigError(f"{where}: has {VARS_FILE}/{FIELDS_FILE} but no triggers")
    if fields_js is not None:
        if len(FIELDS_EXPORT_RE.findall(fields_js)) != 1:
            raise ConfigError(
                f"{where}{FIELDS_FILE}: needs one `export default {{ ... }}`"
                " at the start of a line"
            )
        if not re.search(r"\bpuzzle_id\b", fields_js):
            raise ConfigError(f"{where}{FIELDS_FILE}: must include puzzle_id")
    try:
        return Game(
            **dict(config),
            vars_js=vars_js or "",
            fields_js=fields_js or "",
            announcement=_read(game_dir, ANNOUNCEMENT_FILE),
            icon_path=game_dir / config.icon if config.icon else None,
        )
    except ValidationError as e:
        raise ConfigError(_format_errors(where + ANNOUNCEMENT_FILE, e)) from None


def load_games(games_dir: Path = GAMES_DIR) -> dict[int, Game]:
    loose = sorted(p.name for p in games_dir.glob("*.toml"))
    if loose:
        raise ConfigError(
            f"{', '.join(loose)}: each game is now a directory,"
            f" games/<name>/{CONFIG_FILE} (see games/README.md)"
        )
    games: dict[int, Game] = {}
    for path in sorted(p for p in games_dir.iterdir() if p.is_dir()):
        game = parse_game(path)
        if game.port == LAUNCHER_PORT:
            raise ConfigError(f"{path.name}/: port {LAUNCHER_PORT} is the launcher's")
        if game.port in games:
            other = games[game.port].name
            raise ConfigError(f"{path.name}/: port {game.port} already used by {other}")
        games[game.port] = game
    return games


def json_schema() -> dict[str, Any]:
    schema = TypeAdapter(GameConfig).json_schema()
    # Editors (taplo, tombi) ignore the OpenAPI-style discriminator, so an
    # invalid trigger only gets "not valid under any of the schemas listed in
    # the 'oneOf'". Picking the model by `type` with if/then gives errors that
    # name the actual problem.
    mapping: dict[str, str] = schema["properties"]["triggers"]["items"][
        "discriminator"
    ]["mapping"]
    schema["properties"]["triggers"]["items"] = {
        "type": "object",
        "required": ["type"],
        "properties": {"type": {"enum": list(mapping)}},
        "allOf": [
            {
                "if": {"properties": {"type": {"const": type_}}},
                "then": {"$ref": ref},
            }
            for type_, ref in mapping.items()
        ],
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$comment": "Generated by `python3 -m src.proxy.config`; do not edit.",
        **schema,
    }


def write_schema() -> bool:
    """Regenerate games/schema.json; return True if it changed."""
    text = json.dumps(json_schema(), indent=2) + "\n"
    if SCHEMA_PATH.exists() and SCHEMA_PATH.read_text() == text:
        return False
    SCHEMA_PATH.write_text(text)
    return True


if __name__ == "__main__":
    import sys

    # Before loading the games, so the schema stays current even when one of
    # them is broken.
    if write_schema():
        print(f"updated {SCHEMA_PATH.relative_to(REPO_ROOT)}")
    try:
        configs = load_games()
    except ConfigError as e:
        sys.exit(str(e))
    for port, game in sorted(configs.items()):
        triggers = ", ".join(f"{t.name} ({t.type})" for t in game.triggers) or "none"
        print(f"{port}  {game.name:<16} {game.origin}  triggers: {triggers}")
    print(f"next free port: {max(configs, default=8080) + 1}")
    sys.exit(0)

GAME_CONFIGS = load_games()

# port -> (name, origin)
GAMES = {port: (g.name, g.origin) for port, g in GAME_CONFIGS.items()}
