# Daily Games Bot

A local mitmproxy reverse proxy that serves the games in `games.txt` from
`localhost`, plus an extension point for bot/solver logic.

## Setup

```sh
uv sync
```

## Run

```sh
./run.sh
```

Then open http://localhost:8090 for the launcher, which links to each game:

| Port | Game          | Origin                          |
|------|---------------|----------------------------------|
| 8081 | Wordle        | www.nytimes.com                 |
| 8082 | Fermi         | fermi.gg                        |
| 8083 | Minute Cryptic| www.minutecryptic.com           |
| 8084 | Krillion      | krillion.io                     |

Each game gets its own local port, reverse-proxied 1:1 to its real origin
(`proxy/config.py`). The addon (`proxy/addon.py`) strips
`X-Frame-Options`/CSP/HSTS and rewrites cookies so the game works from a
`localhost` origin over plain HTTP.

## Development

Install the pre-commit hooks once per checkout:

```sh
uv run pre-commit install
```

Every commit then runs `ruff check`, `ruff format` (Black-compatible), and
`pyright` in strict mode against `proxy/`. Run them manually with:

```sh
uv run pre-commit run --all-files
```

`pyright`'s config lives in `pyproject.toml` under `[tool.pyright]` and points
at the project's `.venv`, so VS Code/Pylance (which reads the same section)
reports the same diagnostics as the pre-commit hook and the CLI.

## Adding bot/solver logic

Each game has a stub module under `proxy/hooks/` (e.g. `proxy/hooks/wordle.py`)
with optional `request(flow)` / `response(flow)` functions. `flow` is a
standard `mitmproxy.http.HTTPFlow` — inspect or modify `flow.request` /
`flow.response` there to build solvers without touching the core proxy.

## Known limitation

Each listener maps to one origin, so relative URLs (the vast majority of
assets/API calls) pass through untouched. If a game's JS fetches an
*absolute* URL on a different host (e.g. a separate CDN subdomain not
covered by `proxy/config.py`), that request bypasses the proxy entirely and
may fail from the `localhost` origin (CORS). If you hit this for a
particular game, check the browser devtools network tab for blocked
requests and add a host-specific rewrite rule to `proxy/addon.py`.
