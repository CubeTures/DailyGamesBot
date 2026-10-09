"""Reads and validates the game directories in games/ (format in games/README.md)."""

import re
import tomllib
from pathlib import Path

from pydantic import ValidationError

from src import announce
from src.games.models import FIELDS_EXPORT_RE, Game, GameConfig
from src.settings import GAMES_DIR

CONFIG_FILE = "config.toml"
VARS_FILE = "vars.js"
FIELDS_FILE = "fields.js"
ANNOUNCEMENT_FILE = "announcement.j2"
GAME_FILES = (CONFIG_FILE, VARS_FILE, FIELDS_FILE, ANNOUNCEMENT_FILE)


class ConfigError(Exception):
    pass


def _format_validation_error(where: str, error: ValidationError) -> str:
    lines = [f"{where}:"]
    for detail in error.errors(include_url=False):
        location = ".".join(str(part) for part in detail["loc"]) or "(top level)"
        lines.append(f"  {location}: {detail['msg']}")
    return "\n".join(lines)


def _read_optional(path: Path) -> str | None:
    return path.read_text() if path.exists() else None


def _read_config(game_dir: Path) -> GameConfig:
    where = f"{game_dir.name}/{CONFIG_FILE}"
    toml = _read_optional(game_dir / CONFIG_FILE)
    if toml is None:
        raise ConfigError(f"{game_dir.name}/: missing {CONFIG_FILE}")
    try:
        config = GameConfig.model_validate(tomllib.loads(toml))
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"{where}: {e}") from e
    except ValidationError as e:
        raise ConfigError(_format_validation_error(where, e)) from None
    if config.name != game_dir.name:
        raise ConfigError(f"{game_dir.name}/: 'name' must match the directory name")
    return config


def _check_directory_contents(game_dir: Path, config: GameConfig) -> None:
    """Reject unknown files, so a misnamed one isn't silently ignored."""
    allowed = {*GAME_FILES, *([config.icon] if config.icon else [])}
    unexpected = sorted(p.name for p in game_dir.iterdir() if p.name not in allowed)
    if unexpected:
        raise ConfigError(
            f"{game_dir.name}/: unexpected {', '.join(unexpected)}"
            f" (a game holds only {', '.join(GAME_FILES)} and its icon)"
        )
    if config.icon and not (game_dir / config.icon).is_file():
        raise ConfigError(
            f"{game_dir.name}/{CONFIG_FILE}: icon {config.icon} doesn't exist"
        )


def _check_capture_scripts(
    game_dir: Path, config: GameConfig, vars_js: str | None, fields_js: str | None
) -> None:
    if config.triggers and fields_js is None:
        raise ConfigError(f"{game_dir.name}/: has triggers but no {FIELDS_FILE}")
    if not config.triggers and (vars_js is not None or fields_js is not None):
        raise ConfigError(
            f"{game_dir.name}/: has {VARS_FILE}/{FIELDS_FILE} but no triggers"
        )
    if fields_js is None:
        return
    where = f"{game_dir.name}/{FIELDS_FILE}"
    if len(FIELDS_EXPORT_RE.findall(fields_js)) != 1:
        raise ConfigError(
            f"{where}: needs one `export default {{ ... }}` at the start of a line"
        )
    if not re.search(r"\bpuzzle_id\b", fields_js):
        raise ConfigError(f"{where}: must include puzzle_id")


def _check_announcement(game_dir: Path, template: str | None) -> None:
    if template is None:
        return
    try:
        announce.check_template(template)
    except ValueError as e:
        raise ConfigError(f"{game_dir.name}/{ANNOUNCEMENT_FILE}: {e}") from None


def load_game(game_dir: Path) -> Game:
    config = _read_config(game_dir)
    _check_directory_contents(game_dir, config)

    vars_js = _read_optional(game_dir / VARS_FILE)
    fields_js = _read_optional(game_dir / FIELDS_FILE)
    _check_capture_scripts(game_dir, config, vars_js, fields_js)

    announcement_template = _read_optional(game_dir / ANNOUNCEMENT_FILE)
    _check_announcement(game_dir, announcement_template)

    return Game(
        **dict(config),
        vars_js=vars_js or "",
        fields_js=fields_js or "",
        icon_path=game_dir / config.icon if config.icon else None,
        announcement_template=announcement_template,
    )


def load_games(games_dir: Path = GAMES_DIR) -> dict[str, Game]:
    """Every game in `games_dir`, keyed by name."""
    games = (load_game(p) for p in sorted(games_dir.iterdir()) if p.is_dir())
    return {game.name: game for game in games}
