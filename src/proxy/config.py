"""Single source of truth for which local port maps to which game.

Every game is one TOML file in `games/` (see games/README.md for the format).
Run `uv run python3 -m src.proxy.config` to validate them all.
"""

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
GAMES_DIR = REPO_ROOT / "games"

LAUNCHER_PORT = 8090

TRIGGER_TYPES = ("page", "network", "event")


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class Trigger:
    name: str
    type: str
    # JS expression; truthy means "the player has finished, report it".
    when: str
    # Result field name -> JS expression. Must include "puzzle_id".
    fields: dict[str, str]
    # network triggers: regex searched against the request URL, and
    # optional HTTP method.
    url: str | None = None
    method: str | None = None
    # event triggers: event name, and "window" or "document".
    event: str | None = None
    target: str = "window"
    # Name -> JS expression, evaluated in order before `when` and each field
    # and in scope for them, so shared lookups are written once.
    vars: dict[str, str] = field(default_factory=dict[str, str])


@dataclass(frozen=True)
class GameConfig:
    name: str
    title: str
    origin: str
    port: int
    landing_path: str
    triggers: list[Trigger] = field(default_factory=list[Trigger])


def _str(data: dict[str, Any], key: str, where: str, default: str | None = None) -> str:
    value = data.get(key, default)
    if not isinstance(value, str) or not value:
        raise ConfigError(f"{where}: '{key}' must be a non-empty string")
    return value


def _opt_str(data: dict[str, Any], key: str, where: str) -> str | None:
    if key not in data:
        return None
    return _str(data, key, where)


def _exprs(data: dict[str, Any], key: str, where: str) -> dict[str, str]:
    raw = data.get(key, {})
    if not isinstance(raw, dict):
        raise ConfigError(f"{where}: '{key}' must be a table")
    exprs = cast(dict[str, Any], raw)
    for name, expr in exprs.items():
        if not isinstance(expr, str) or not expr.strip():
            raise ConfigError(f"{where}: {key}.{name} must be a JS expression")
    return cast(dict[str, str], exprs)


def _parse_trigger(raw: Any, where: str) -> Trigger:
    if not isinstance(raw, dict):
        raise ConfigError(f"{where}: must be a table")
    data = cast(dict[str, Any], raw)
    name = _str(data, "name", where)
    where = f"{where} ({name})"
    type_ = _str(data, "type", where)
    if type_ not in TRIGGER_TYPES:
        raise ConfigError(f"{where}: 'type' must be one of {TRIGGER_TYPES}")

    fields = _exprs(data, "fields", where)
    if "puzzle_id" not in fields:
        raise ConfigError(f"{where}: [fields] must include 'puzzle_id'")
    vars_ = _exprs(data, "vars", where)
    reserved = {"req", "res", "event"}
    for var in vars_:
        if not re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$]*", var) or var in reserved:
            raise ConfigError(f"{where}: vars.{var} is not a usable JS name")

    url = _opt_str(data, "url", where)
    event = _opt_str(data, "event", where)
    if type_ == "network":
        if url is None:
            raise ConfigError(f"{where}: network triggers need 'url'")
        try:
            re.compile(url)
        except re.error as e:
            raise ConfigError(f"{where}: bad 'url' regex: {e}") from e
    if type_ == "event" and event is None:
        raise ConfigError(f"{where}: event triggers need 'event'")
    target = _str(data, "target", where, default="window")
    if target not in ("window", "document"):
        raise ConfigError(f"{where}: 'target' must be 'window' or 'document'")

    method = _opt_str(data, "method", where)
    return Trigger(
        name=name,
        type=type_,
        when=_str(data, "when", where, default="true"),
        fields=fields,
        url=url,
        method=method.upper() if method else None,
        event=event,
        target=target,
        vars=vars_,
    )


def parse_game(path: Path) -> GameConfig:
    where = path.name
    try:
        data = tomllib.loads(path.read_text())
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"{where}: {e}") from e

    name = _str(data, "name", where)
    if not re.fullmatch(r"[a-z][a-z0-9_]*", name):
        raise ConfigError(f"{where}: 'name' must be a lowercase python identifier")
    if name != path.stem:
        raise ConfigError(f"{where}: 'name' must match the file name")
    port = data.get("port")
    if not isinstance(port, int):
        raise ConfigError(f"{where}: 'port' must be an integer")

    raw_triggers = data.get("triggers", [])
    if not isinstance(raw_triggers, list):
        raise ConfigError(f"{where}: use [[triggers]] for triggers")
    triggers = [
        _parse_trigger(t, f"{where} triggers[{i}]")
        for i, t in enumerate(cast(list[Any], raw_triggers))
    ]
    names = [t.name for t in triggers]
    if len(set(names)) != len(names):
        raise ConfigError(f"{where}: trigger names must be unique")

    return GameConfig(
        name=name,
        title=_str(data, "title", where, default=name.title()),
        origin=_str(data, "origin", where).rstrip("/"),
        port=port,
        landing_path=_str(data, "landing_path", where, default="/"),
        triggers=triggers,
    )


def load_games(games_dir: Path = GAMES_DIR) -> dict[int, GameConfig]:
    games: dict[int, GameConfig] = {}
    for path in sorted(games_dir.glob("*.toml")):
        game = parse_game(path)
        if game.port == LAUNCHER_PORT:
            raise ConfigError(f"{path.name}: port {LAUNCHER_PORT} is the launcher's")
        if game.port in games:
            other = games[game.port].name
            raise ConfigError(f"{path.name}: port {game.port} already used by {other}")
        games[game.port] = game
    return games


GAME_CONFIGS = load_games()

# port -> (name, origin)
GAMES = {port: (g.name, g.origin) for port, g in GAME_CONFIGS.items()}


if __name__ == "__main__":
    for port, game in sorted(GAME_CONFIGS.items()):
        triggers = ", ".join(f"{t.name} ({t.type})" for t in game.triggers) or "none"
        print(f"{port}  {game.name:<16} {game.origin}  triggers: {triggers}")
    print(f"next free port: {max(GAME_CONFIGS, default=8080) + 1}")
