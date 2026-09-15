# Daily Games Bot

A local mitmproxy reverse proxy that serves the games in `games.txt` from
`localhost`, a Discord bot, and an extension point for bot/solver logic. All
of it lives under `src/` and runs together from a single command.

## Setup

```sh
uv sync
```

Copy `.env.example` to `.env` and fill in `DISCORD_BOT_TOKEN`.

## Run

```sh
./run.sh
```

which is just:

```sh
uv run python3 -m src
```

This regenerates the launcher page, starts the reverse proxy, serves the
launcher, and logs in the Discord bot, all in one process. Then open
http://localhost:8090 for the launcher, which links to each game:

| Port | Game          | Origin                          |
|------|---------------|----------------------------------|
| 8081 | Wordle        | www.nytimes.com                 |
| 8082 | Fermi         | fermi.gg                        |
| 8083 | Minute Cryptic| www.minutecryptic.com           |
| 8084 | Krillion      | krillion.io                     |

Each game gets its own local port, reverse-proxied 1:1 to its real origin
(`src/proxy/config.py`). The addon (`src/proxy/addon.py`) strips
`X-Frame-Options`/CSP/HSTS and rewrites cookies so the game works from a
`localhost` origin over plain HTTP.

## Development

Install the pre-commit hooks once per checkout:

```sh
uv run pre-commit install
```

Every commit then runs `ruff check`, `ruff format` (Black-compatible), and
`pyright` in strict mode against `src/`. Run them manually with:

```sh
uv run pre-commit run --all-files
```

`pyright`'s config lives in `pyproject.toml` under `[tool.pyright]` and points
at the project's `.venv`, so VS Code/Pylance (which reads the same section)
reports the same diagnostics as the pre-commit hook and the CLI.

## Adding bot/solver logic

Each game has a stub module under `src/proxy/hooks/` (e.g.
`src/proxy/hooks/wordle.py`) with optional `request(flow)` / `response(flow)`
functions. `flow` is a standard `mitmproxy.http.HTTPFlow` — inspect or modify
`flow.request` / `flow.response` there to build solvers without touching the
core proxy.

## Discord bot

A minimal discord.py bot lives in `src/discord_bot/bot.py` with `/hello` and
`/link` slash commands. `/link` replies ephemerally with a link to the
launcher page tagged with the user's Discord ID
(`?discord_id=...`); the launcher stores that ID in `localStorage` and
strips it from the URL on load. It starts automatically as part of
`uv run python3 -m src`. To run just the bot on its own:

```sh
uv run python3 -m src.discord_bot.bot
```

## Known limitation

Each listener maps to one origin, so relative URLs (the vast majority of
assets/API calls) pass through untouched. If a game's JS fetches an
*absolute* URL on a different host (e.g. a separate CDN subdomain not
covered by `src/proxy/config.py`), that request bypasses the proxy entirely
and may fail from the `localhost` origin (CORS). If you hit this for a
particular game, check the browser devtools network tab for blocked
requests and add a host-specific rewrite rule to `src/proxy/addon.py`.
