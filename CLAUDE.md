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
uv run pytest                    # offline unit tests + every game has a driver
uv run pytest -m live            # play every game live and check its capture
uv run pytest -m live -k wordle --headed   # one game, watching the browser
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
commit the result. If a game's capture (`vars.js`, `fields.js`, triggers)
or the capture runtime changed, run that game's live tests
(`uv run pytest -m live -k <game>`); see `tests/README.md`.

Pyright runs in strict mode against `src/` and `tests/`, so every function
needs full type annotations. Its config is `[tool.pyright]` in
`pyproject.toml`. The same checks run as pre-commit hooks
(`uv run pre-commit install`).

## Layout

- `src/settings.py`: repo paths, launcher port, database path, `.env`
  settings, logging setup
- `src/games/`: game config models (`models.py`), loading and validation
  (`loader.py`), the loaded games (`registry.py`), schema generation
  (`schema.py`), and `game_day.js`, the JS `gameDay()` shared by the
  capture script and the launcher (its Python twin is `Reset.day_at`)
- `src/store/`: the SQLite store (`data/results.db`, override with
  `DGB_DB_PATH`), one module per table: `results.py`, `players.py`,
  `subscriptions.py`, `hidden_games.py`; `db.py` connects, creates the
  tables and migrates old databases
- `src/proxy/`: mitmdump launcher (`mitmdump.py`), the addon it loads
  (`addon.py`), localhost rewrites (`rewrite.py`)
- `src/proxy/capture/`: the `/__dgb/` paths (`__init__.py`), capture script
  building and injection (`script.py`, `runtime.js`), the endpoints that
  save results (`endpoints.py`)
- `src/proxy/hooks/<game>.py`: optional per-game `request(flow)` /
  `response(flow)` hooks (see `hooks/__init__.py`); `route_foreign_hosts()`
  builds them for games that fetch from other hosts
- `src/launcher/`: page generation (`build.py`, `templates/`) and its HTTP
  server with the JSON API (`server.py`, one function per route)
- `src/discord_bot/`: client, polling loops and `/play` (`bot.py`), result
  posts (`announcer.py`), username lookups (`player_names.py`), game roles
  (`roles.py`), channel lookups (`channels.py`)
- `src/announce.py`: renders a result's `announcement.j2`
- `tests/unit/`: offline tests of the store, rewrites, capture endpoints,
  announcements and launcher API, each on a scratch database
- `tests/e2e/`: live end-to-end tests of every game's capture; one driver per
  game in `tests/e2e/games/` (see `tests/README.md`)
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
  `src/store/results.py`, keyed on the player's Discord ID. When `fields.js` gives
  no `time_secs`, `runtime.js` fills it in as the time since the game's
  first page load that game day (a day starts at the config's `[reset]`; see
  `src/games/game_day.js`), kept in the game's localStorage under `__dgb_timer`.
- **Launcher.** `launcher/index.html` is rendered from
  `src/launcher/templates/` and the game configs on every proxy start. It shows a card per game and a
  scoreboard (score, ties broken by `time_secs`) read from `GET /api/results?day=YYYY-MM-DD` on the
  launcher's server. The chosen day is kept in the URL as `#day=YYYY-MM-DD`.
  Results are filed by game day, not capture time: `runtime.js` reports the
  day the page loaded in, by the game's `[reset]`, as `game_day`. So a game
  resetting at Eastern midnight, played at 10pm Pacific, shows on the
  viewer's tomorrow. A card's "Done" state is for its game's current game
  day (`currentGameDay()` in `app.js`, using the shared `gameDay()`). Cards of
  games whose reset isn't `local` show its timezone (e.g. "EDT") in a
  pill, with a globe icon, beside their status. Each card is tinted with
  its icon's dominant color (`icon-color.js`). Clicking a result shows the
  game's `announcement.j2` rendered as HTML. With
  `DISCORD_RESULTS_CHANNEL_ID` set, a bell on each card toggles the
  player's game role via `GET`/`POST /api/subscriptions`. Cards are divs
  whose title link stretches over the whole card, so the bell can be a
  button inside it.
- **Discord bot.** `/play` replies ephemerally with a launcher link tagged
  `?discord_id=...`; the launcher stores it in `localStorage` and a
  `dgb_discord_id` cookie (shared across localhost ports so games can send
  it) and strips it from the URL. The bot records usernames for the
  scoreboard on first `/play` and after each result. With
  `DISCORD_RESULTS_CHANNEL_ID` set, it polls every 15s for unannounced
  results and posts them using the game's `announcement.j2`; player mentions
  don't ping, and results over 6 hours old when first seen are skipped.
- **Game roles.** On startup the bot creates a mentionable role named after
  each game's `title` in the results channel's server (reusing one that
  already has that name; needs Manage Roles). Announcements ping it. Role
  picks from the launcher are saved in the `subscriptions` table and the bot
  polls every 15s to give or take the role. The table is the source of
  truth: roles changed by hand in Discord aren't reflected on the launcher.
- **Hiding games.** Each player chooses which games they see. The pencil
  beside "Games" puts the launcher in edit mode, where every card shows
  with an eye; each click cycles the game through shown, card hidden
  (`card`) and card and scoreboard hidden (`all`). Choices are saved per
  `discord_id` in `hidden_games` via `GET`/`POST /api/hidden` (and cached
  in `localStorage` so hidden cards don't flash on load). It's only the
  player's view: the game is still proxied and its results are kept and
  announced.

## Gotchas

- `launcher/index.html` is generated from `src/launcher/templates/` on
  every proxy start, with the CSS and JS (including `src/games/game_day.js`)
  inlined. Edit the templates, not
  the output. It is gitignored, so don't commit it.
- A new game's port must be added to `docker-compose.yml` `ports:` and the
  `Dockerfile` `EXPOSE`.
- Each listener maps to one origin. If a game's JS fetches an absolute URL on
  a different host (separate API/CDN subdomain), that request bypasses the
  proxy and may fail on CORS; fix it with a hook calling
  `route_foreign_hosts()` (see `src/proxy/hooks/dailyorbs.py`).
- The store is shared across processes (the proxy runs inside mitmdump), so
  the bot learns of new results, names and role picks by polling it, never
  by being called. Call store functions from async code via
  `asyncio.to_thread`.
- Log with `logging.getLogger(__name__)`, not `print`; mitmproxy picks up
  the proxy's logs, and the entry points call `configure_logging()`.
- To add a game or fix its result capture, use the `/add-game` skill
  (`.claude/skills/add-game/SKILL.md`). Test against a scratch database by
  setting `DGB_DB_PATH`.
