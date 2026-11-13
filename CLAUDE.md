# Daily Games Bot

A mitmproxy reverse proxy that serves daily web games from `localhost` and
captures each player's result, plus a Discord bot that hands out play links and
announces results. `README.md` is the user-facing overview, `SETUP.md` covers
deploying behind Cloudflare Tunnel; the technical details live here.

## Commands

```sh
uv sync                          # install deps (incl. dev tools)
uv run python3 -m src            # proxy + launcher + Discord bot
uv run python3 -m src.proxy      # proxy + launcher only (no token needed)
uv run python3 -m src.discord_bot      # Discord bot only
uv run python3 -m src.games            # validate games/ and regenerate games/schema.json
uv run python3 -m src.store reset-token ID  # invalidate a leaked /play link
docker compose up --build        # everything, in Docker
uv run pytest                    # offline unit tests + every game has a driver
uv run pytest -m live            # play every game live and check its capture
uv run pytest -m live -k wordle --headed   # one game, watching the browser
```

`.env` (from `.env.example`) holds `DISCORD_BOT_TOKEN` and, optionally,
`DISCORD_RESULTS_CHANNEL_IDS` (comma-separated channels results are announced
in, at most one per server; the old `DISCORD_RESULTS_CHANNEL_ID` is its
fallback), `DISCORD_ADMIN_CHANNEL_ID` (daily test reports; see below) and
`DGB_PUBLIC_URL` / `DGB_PROXY_PORT` / `DGB_GAME_HOST` (where it's served; see
below).

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

- `src/settings.py`: repo paths, public URL and ports, database path,
  `.env` settings, logging setup
- `src/games/`: game config models (`models.py`), loading and validation
  (`loader.py`), the loaded games (`registry.py`), schema generation
  (`schema.py`), and `game_day.js`, the JS `gameDay()` shared by the
  capture script and the launcher (its Python twin is `Reset.day_at`)
- `src/store/`: the SQLite store (`data/results.db`, override with
  `DGB_DB_PATH`), one module per table: `results.py`, `players.py`,
  `subscriptions.py`, `hidden_games.py`, `starts.py` (co-op games
  started), `guilds.py` (servers players
  registered with, their primary one, server names); `db.py` connects, creates the
  tables and migrates old databases; `__main__.py` is the admin CLI
- `src/proxy/`: mitmdump launcher (`mitmdump.py`), the addon it loads and
  that routes each subdomain to its game (`addon.py`), localhost rewrites
  (`rewrite.py`)
- `src/proxy/capture/`: the `/__dgb/` paths (`__init__.py`), capture script
  building and injection (`script.py`, `runtime.js`), the endpoints that
  save results (`endpoints.py`)
- `src/proxy/hooks/<game>.py`: optional per-game `request(flow)` /
  `response(flow)` hooks (see `hooks/__init__.py`); `route_foreign_hosts()`
  builds them for games that fetch from other hosts
- `src/launcher/`: page generation (`build.py`, `templates/`) and its HTTP
  server with the JSON API (`server.py`, one function per route)
- `src/discord_bot/`: client, polling loops, `/play` and `/primary` (`bot.py`), result
  posts (`announcer.py`), username lookups (`player_names.py`), game roles
  (`roles.py`), results channel lookups (`channels.py`), the daily test run
  (`daily_tests.py`)
- `src/announce.py`: renders a result's `announcement.j2`
- `tests/unit/`: offline tests of the store, rewrites, capture endpoints,
  announcements and launcher API, each on a scratch database
- `tests/e2e/`: live end-to-end tests of every game's capture; one driver per
  game in `tests/e2e/games/` (see `tests/README.md`)
- `games/<name>/`: one directory per game (`config.toml`, `fields.js`,
  `announcement.j2`, icon); format in `games/README.md`

## How it works

- **Proxy.** Everything is served through one mitmproxy listener on 8080
  (`DGB_PUBLIC_URL`, default `http://localhost:8080`). Each game has its own
  subdomain of it (`http://wordle.localhost:8080`), so its own origin and
  storage (`DGB_GAME_HOST`, e.g. `{game}-daily.example.com`, overrides the
  host when nested subdomains can't get a certificate); the addon picks the game by the Host header and reverse-proxies it
  1:1 to its real origin. The launcher's host (`DGB_PUBLIC_URL`) goes to the
  launcher's server, on 127.0.0.1:8090; any other host gets a 404. Chrome and Firefox resolve `*.localhost` themselves; in
  production, put a TLS-terminating reverse proxy with wildcard DNS in front
  and forward every host, keeping the Host header. `rewrite.py` strips
  `X-Frame-Options`/CSP/HSTS and rewrites cookies so games work from a
  `localhost` origin over plain HTTP. Absolute URLs back to the game's own
  origin are rewritten to its subdomain in text responses.
- **Capture.** A game's `config.toml` `[[triggers]]` say when the player has
  finished; `fields.js` says which result fields to extract. The proxy
  injects `capture/runtime.js` into the game's pages, which evaluates them
  and reports back; `capture/endpoints.py` saves results via
  `src/store/results.py`, keyed on the player's Discord ID (looked up
  from the `dgb_token` cookie; see the Discord bot below). When `fields.js` gives
  no `time_secs`, `runtime.js` fills it in as the time since the game's
  first page load that game day (a day starts at the config's `[reset]`; see
  `src/games/game_day.js`), kept in the game's localStorage under `__dgb_timer`.
- **Launcher.** `launcher/index.html` is rendered from
  `src/launcher/templates/` and the game configs on every proxy start. It shows a card per game and a
  scoreboard (score, ties broken by `time_secs`) read from `GET /api/results?day=YYYY-MM-DD&token=...&guild=ID` on the
  launcher's server. It shows the viewer's own results plus those of the
  players registered with the server picked in its dropdown (from
  `/api/me`, shown with two or more servers), if the viewer is registered
  with it too. With two or more there's also "All servers" first
  (`guild=all`), for everyone sharing any server with the viewer; its rows
  carry `in_primary`, and the page highlights the primary server's players
  (`--primary`, red) and tints "See all" when some are below the cut. It opens
  on the pick last made in that browser (`localStorage` `guild`), else the
  primary server. The chosen day is kept in the URL as `#day=YYYY-MM-DD`.
  The board can go forward to tomorrow while some game is already on it.
  It opens on the home day: tomorrow once the viewer has a result on it,
  otherwise today. The button back to it is labelled with that day. A view following the home day
  moves to tomorrow on its own when that first result lands.
  Results are filed by game day, not capture time: `runtime.js` reports the
  day the page loaded in, by the game's `[reset]`, as `game_day`. So a game
  resetting at Eastern midnight, played at 10pm Pacific, shows on the
  viewer's tomorrow. A card's "Done" state is for its game's current game
  day (`currentGameDay()` in `app.js`, using the shared `gameDay()`). Cards of
  games whose reset isn't `local` show, in a pill in their footer, when
  it next comes round on the viewer's clock (e.g. "5 PM"), unless that's
  the same wall-clock time as the reset itself. Each card is tinted with
  its icon's dominant color (`icon-color.js`). A flame pill in each card's
  footer shows the viewer's streak in that game (two or more game days in a
  row with a result, from `GET /api/streaks`; `results.streaks()`): fire-colored once
  today's is played, styled like the reset pill while it ended yesterday and
  can still be kept going, gone after that. From the second day, every
  announcement's header ends in `:fire: N`, the streak as of that result's
  game day (`StoredResult.streak`). Clicking a result shows the
  game's `announcement.j2` rendered as HTML. With
  `DISCORD_RESULTS_CHANNEL_IDS` set, a bell on each card toggles the
  player's game role via `GET`/`POST /api/subscriptions`. Cards are divs
  whose title link stretches over the whole card, so the bell can be a
  button inside it.
- **Discord bot.** `/play` replies ephemerally with a launcher link tagged
  `?token=...`, a UUID saved in `players.token` that stands in for the
  player's Discord ID. It's made on their first `/play` and kept after
  that; if a link leaks, an admin runs
  `uv run python3 -m src.store reset-token DISCORD_ID` and the player's
  next `/play` gets a new one. The launcher's server only sends the page
  for a working token, from `?token=` or the HttpOnly `dgb_token` cookie it
  sets on the launcher's host then; anyone else gets `locked.html.j2`
  ("run /play", or "link expired" for a reset token) with a 401. It fills
  the token into the page's `dgb-token` meta tag, and the page strips it
  from the URL. Every launcher API, `/api/results` included, takes the
  token, never a Discord ID; a 401 from `/api/me` reloads the page. Game
  subdomains can't see the launcher's storage or cookies, so its card links
  go through the game's `/__dgb/enter?token=...&to=`, which sets an
  HttpOnly `dgb_token` cookie on that subdomain and redirects to the
  game. Any other request to a game's subdomain without a working token
  cookie gets a 404 (`has_working_token()` in `capture/endpoints.py`, which
  caches a working token for 60s, so a reset takes up to a minute to lock
  games). The bot records usernames for the
  scoreboard on first `/play` and after each result.
- **Servers.** `/play` run in a server registers the player with it
  (`player_guilds`); the first becomes their primary server (the one the
  scoreboard opens on in a browser that hasn't picked one yet) until `/primary`, run in another, changes it. Players
  are never unregistered. The bot keeps server names in `guilds` for the
  launcher. On startup it registers players from before servers were tracked
  with each results channel's server they're a member of. With
  `DISCORD_RESULTS_CHANNEL_IDS` set, it polls every 15s for unannounced
  results and posts each in the results channel of every server its player
  is registered with, using the game's `announcement.j2` (`announcements`
  records where it went, so a failed post is retried without repeating the
  rest); player mentions don't ping, and results over 6 hours old when first
  seen are skipped. A channel ID names its server; if two are in the same
  server, the bot logs an error and uses the first.
- **Co-op games.** A game with `coop = true` (Cross with Friends) is played
  together, any number of times a day; `puzzle_id` is the shared game. A
  trigger with `report = "start"` posts to `/__dgb/start` whenever a player
  plays in one, recording the game's ID for them (`coop_players`); the
  first is also a start (`starts` table). The first solve reported, from
  anyone, is saved as a result for every recorded player with their own
  score from the `players` roster (`_save_shared_game()` in
  `capture/endpoints.py`); later reports are duplicates. The announcer
  posts one message per shared game; the launcher's `/api/results` sums
  each player's day into one row, and its card has a "Co-op" pill in its
  footer. The bot
  posts it with `/join/<game>?to=PATH` on the launcher, which redirects the
  clicker through the game's `/__dgb/enter` with their own token. Format in
  `games/README.md`.
- **Game roles.** On startup the bot creates a mentionable role named after
  each game's `title` in each results channel's server (reusing one that
  already has that name; needs Manage Roles). Announcements ping it. Role
  picks from the launcher are saved in the `subscriptions` table and the bot
  polls every 15s to give or take the role in each of those servers the
  player is registered with. The table is the source of
  truth: roles changed by hand in Discord aren't reflected on the launcher.
- **Daily tests.** With `DISCORD_ADMIN_CHANNEL_ID` set, the bot runs
  `pytest -m 'not live'` and then `pytest -m live` in subprocesses every day
  at `daily_tests.RUN_AT` (12:00 UTC). Only if a test failed or errored, or a
  run broke (timeout, other exit code), it posts them in that channel with
  each run's output and a zip of `tests/e2e/.artifacts/` (minus traces)
  attached. The post opens with 🔴 if capturing is degraded (a live test
  raised the harness's `CaptureFailed`, or a unit test failed), otherwise
  🟡 (drivers only: a game couldn't be played through, or a run broke). The live run gets its own ports (18080/18090, via
  `DGB_PUBLIC_URL` and `DGB_LAUNCHER_PORT`) so it doesn't collide with the
  running proxy; both runs blank the other `DGB_*` URL settings so `.env`
  doesn't leak into them, and use a scratch `DGB_DB_PATH`. Needs the dev
  dependencies and Chrome: in Docker, the image from `Dockerfile.with-tests`
  (published as `ghcr.io/<repo>-with-tests` by `.github/workflows/build.yml`
  beside the plain one), which also installs `libnss-myhostname` so
  `*.localhost` resolves outside Chrome.
- **Modes.** A game with several modes scored differently has one game
  per mode (see `games/README.md`): the extra ones name the main one with
  `mode_of`, and each has a `mode` name (`check_modes()` in `loader.py`).
  The launcher stacks a game's modes into one card (`.stack` in the
  template, `mode-stack.js`), the mode on top in front and the next one
  peeking out behind; only two ever show, and switching makes the card
  behind the mode picked before shuffling the front one behind it. The
  pill under the title names the mode showing (even when it's the only
  one, so a lone mode isn't mistaken for the game) and shows each other
  as a badge, green once played; a click on it, on the card behind, a
  drag of the front card or the arrow keys switch. The scoreboard stacks the
  modes played that day the same way, its pill replacing the player count,
  and both stacks of a game switch together; the mode on top is kept per
  browser (`localStorage` `stack_tops`). Hiding works per mode; edit mode
  puts every mode back in its stack.
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
- Each game's subdomain maps to one origin. If a game's JS fetches an absolute URL on
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
