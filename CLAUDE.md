# Daily Games Bot

A mitmproxy reverse proxy that serves daily web games from `localhost` and
captures each player's result, plus a Discord bot that hands out play links and
announces results. `README.md` is the user-facing overview; the technical
details live here.

## Commands

```sh
uv sync                          # install deps (incl. dev tools)
uv run python3 -m src            # proxy + launcher + Discord bot
uv run python3 -m src.proxy      # proxy + launcher only (no token needed)
uv run python3 -m src.discord_bot      # Discord bot only
uv run python3 -m src.games            # validate games/ and regenerate games/schema.json
docker compose up --build        # everything, in Docker
```

`.env` (from `.env.example`) holds `DISCORD_BOT_TOKEN` and, optionally,
`DISCORD_RESULTS_CHANNEL_ID` (the channel results are announced in).

## Before finishing any change

Run all of these and fix anything they report:

```sh
uv run ruff format --check --diff
uv run ruff check
uv run pyright --level error
```

If `games/` or `src/games/` changed, also run
`uv run python3 -m src.games`. It regenerates `games/schema.json`;
commit the result.

Pyright runs in strict mode against `src/`, so every function needs full type
annotations. Its config is `[tool.pyright]` in `pyproject.toml`. The same
checks run as pre-commit hooks (`uv run pre-commit install`).

## Layout

- `src/settings.py`: repo paths, launcher port, database path
- `src/games/`: game config models (`models.py`), loading and validation
  (`loader.py`), the loaded games (`registry.py`), schema generation
  (`schema.py`)
- `src/proxy/`: mitmdump launcher (`mitmdump.py`), the addon it loads
  (`addon.py`), localhost rewrites (`rewrite.py`)
- `src/proxy/capture/`: capture script building and injection (`script.py`,
  `runtime.js`), the `/__dgb/` endpoints that save results (`endpoints.py`)
- `src/proxy/hooks/<game>.py`: optional per-game `request(flow)` /
  `response(flow)` hooks (none exist yet; see `hooks/__init__.py`)
- `src/launcher/`: page generation (`build.py`, `templates/`) and its HTTP
  server with the results API (`server.py`)
- `src/discord_bot/`: client and `/play` (`bot.py`), result posts
  (`announcer.py`), username lookups (`player_names.py`)
- `src/announce.py`: renders a result's `announcement.j2`
- `src/results.py`: SQLite results store (`data/results.db`, override with
  `DGB_DB_PATH`)
- `games/<name>/`: one directory per game (`config.toml`, `fields.js`,
  `announcement.j2`, icon); format in `games/README.md`

## How it works

- **Proxy.** Each game gets its own local port (8081+), reverse-proxied 1:1
  to its real origin; the launcher is on 8090. `rewrite.py` strips
  `X-Frame-Options`/CSP/HSTS and rewrites cookies so games work from a
  `localhost` origin over plain HTTP. Absolute URLs back to the game's own
  origin are rewritten to the local port in text responses.
- **Capture.** A game's `config.toml` `[[triggers]]` say when the player has
  finished; `fields.js` says which result fields to extract. The proxy
  injects `capture/runtime.js` into the game's pages, which evaluates them
  and reports back; `capture/endpoints.py` saves results via
  `src/results.py`, keyed on the player's Discord ID.
- **Launcher.** `launcher/index.html` is rendered from
  `src/launcher/templates/` and the game configs on every proxy start. It shows a card per game and a
  scoreboard read from `GET /api/results?since=<ISO>[&until=<ISO>]` on the
  launcher's server. The chosen day is kept in the URL as `#day=YYYY-MM-DD`;
  days run from the viewer's local midnight. Clicking a result shows the
  game's `announcement.j2` rendered as HTML.
- **Discord bot.** `/play` replies ephemerally with a launcher link tagged
  `?discord_id=...`; the launcher stores it in `localStorage` and a
  `dgb_discord_id` cookie (shared across localhost ports so games can send
  it) and strips it from the URL. The bot records usernames for the
  scoreboard on first `/play` and after each result. With
  `DISCORD_RESULTS_CHANNEL_ID` set, it polls every 15s for unannounced
  results and posts them using the game's `announcement.j2`; mentions don't
  ping, and results over 6 hours old when first seen are skipped.

## Gotchas

- `launcher/index.html` is generated from `src/launcher/templates/` on
  every proxy start, with the CSS and JS inlined. Edit the templates, not
  the output; commit the output after adding or changing a game.
- A new game's port must be added to `docker-compose.yml` `ports:` and the
  `Dockerfile` `EXPOSE`.
- Each listener maps to one origin. If a game's JS fetches an absolute URL on
  a different host (separate API/CDN subdomain), that request bypasses the
  proxy and may fail on CORS; fix it with a host-specific rewrite in
  `src/proxy/rewrite.py`.
- To add a game or fix its result capture, use the `/add-game` skill
  (`.claude/skills/add-game/SKILL.md`). Test against a scratch database by
  setting `DGB_DB_PATH`.
