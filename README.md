# Daily Games Bot

A local mitmproxy reverse proxy that serves daily web games from `localhost`,
captures each player's result, and a Discord bot that hands out play links and
announces results. All of it lives under `src/` and runs together from a
single command.

## Setup

```sh
uv sync
```

Copy `.env.example` to `.env` and fill in `DISCORD_BOT_TOKEN`. To have the
bot announce finished games, also set `DISCORD_RESULTS_CHANNEL_ID` to the ID
of the channel to post in (Developer Mode on, then right-click the channel and
pick Copy Channel ID). The bot needs permission to send messages there.

## Run

```sh
uv run python3 -m src
```

This regenerates the launcher page, starts the reverse proxy, serves the
launcher, and logs in the Discord bot, all in one process. Then open
http://localhost:8090 for the launcher, which links to each game:

| Port | Game           | Origin                |
| ---- | -------------- | --------------------- |
| 8081 | Wordle         | www.nytimes.com       |
| 8082 | Fermi          | fermi.gg              |
| 8083 | Minute Cryptic | www.minutecryptic.com |
| 8084 | Krillion       | krillion.io           |

Each game gets its own local port, reverse-proxied 1:1 to its real origin.
Games are configured one directory per game in `games/` (format in
`games/README.md`; validate with `uv run python3 -m src.proxy.config`). The
addon (`src/proxy/addon.py`) strips `X-Frame-Options`/CSP/HSTS and rewrites
cookies so the game works from a `localhost` origin over plain HTTP.

To run just the proxy and launcher, without the Discord bot (no token
needed):

```sh
uv run python3 -m src.proxy
```

Results are stored in SQLite at `data/results.db`. Set `DGB_DB_PATH` to use a
different file, e.g. a scratch database while testing a game.

### Docker

```sh
docker compose up --build
```

`docker-compose.yml` reads `.env`, publishes the launcher and every game port,
and mounts `./data` so results survive rebuilds. A new game's port has to be
added to both its `ports:` list and the `Dockerfile`'s `EXPOSE`.

## The launcher

`launcher/index.html` is generated from `src/proxy/launcher.html.j2` and the
game configs (`src/proxy/gen_launcher.py`) every time the proxy starts, so
don't edit it by hand; commit it after adding or changing a game. It shows a
card per game (title, description, icon, and whether you've played it today)
and a scoreboard, read from `GET /api/results?since=<ISO time>[&until=<ISO
time>]` on the launcher's own server. The scoreboard shows today by default;
its arrows and date picker step back to earlier days (results are never
cleared), and the chosen day is kept in the URL as `#day=YYYY-MM-DD` so it can
be linked. Days run from the viewer's local midnight. Clicking a result opens
the same announcement the bot posts to Discord, rendered from the game's
`announcement.j2` with Discord shortcodes and markdown turned into HTML.

## Adding a game and capturing results

Each game's `config.toml` can declare `[[triggers]]` saying when the player
has finished, and its `fields.js` says which result fields to pull out
(puzzle id, score, win/loss...). The proxy injects a small script into the
game's pages that evaluates them and reports results back to the proxy, which
saves them to the results database (`src/results.py`), keyed on the player's
Discord ID from their `/play` link.

To add a game, or work out the triggers for one, run the Claude Code skill:

```
/add-game https://example.com/daily-puzzle
```

It sets up `games/<name>/` (config, description, icon, port), opens the game
through the proxy in a Playwright browser with an event recorder, and asks you
to play it, once to win and once to lose where the game allows it. It then
inspects what the page did (storage, network calls, analytics events, the
final screen), writes the triggers, fields and Discord announcement, and
verifies them end to end against a scratch database. The skill's steps are in
`.claude/skills/add-game/SKILL.md`.

## Development

Install the pre-commit hooks once per checkout:

```sh
uv run pre-commit install
```

Every commit then runs `ruff check`, `ruff format` (Black-compatible),
`pyright` in strict mode against `src/`, and, when `games/` or
`src/proxy/config.py` changed, the game config validator, which also
regenerates `games/schema.json` (a stale schema fails the commit as a modified
file). Run them manually with:

```sh
uv run pre-commit run --all-files
```

`pyright`'s config lives in `pyproject.toml` under `[tool.pyright]` and points
at the project's `.venv`, so VS Code/Pylance (which reads the same section)
reports the same diagnostics as the pre-commit hook and the CLI.

## Adding bot/solver logic

A game can have a module under `src/proxy/hooks/` named after it (e.g.
`src/proxy/hooks/wordle.py`) with optional `request(flow)` / `response(flow)`
functions; games without one are simply proxied. `flow` is a standard
`mitmproxy.http.HTTPFlow`: inspect or modify `flow.request` /
`flow.response` there to build solvers without touching the core proxy.

## Discord bot

A minimal discord.py bot lives in `src/discord_bot/bot.py` with a
`/play` slash command. `/play` replies ephemerally with a link to the
launcher page tagged with the user's Discord ID
(`?discord_id=...`); the launcher stores that ID in `localStorage` and
a `dgb_discord_id` cookie, and strips it from the URL on load. The bot also
records each player's Discord username, so the launcher's scoreboard can show
names; it looks a name up on a player's first `/play` and again after each
result. It starts automatically as part of `uv run python3 -m src`.

When `DISCORD_RESULTS_CHANNEL_ID` is set, the bot also posts each newly
captured result to that channel. The proxy saves results and the bot polls
for unannounced ones every 15s, so a post shows up within about 15 seconds of
finishing. Each message is formatted by the game's `announcement.j2` template
(see `games/README.md`); mentions render as names but don't ping anyone.
Results more than 6 hours old when the bot first sees them, for example ones
saved while the bot was down, are skipped.

To run just the bot on its own:

```sh
uv run python3 -m src.discord_bot.bot
```

## Known limitation

Each listener maps to one origin. Relative URLs pass through untouched, and
absolute URLs back to the game's own origin are rewritten to the local port in
text responses. If a game's JS fetches an _absolute_ URL on a different host
(e.g. a separate API or CDN subdomain), that request bypasses the proxy
entirely and may fail from the `localhost` origin (CORS). If you hit this for
a particular game, check the browser devtools network tab for blocked
requests and add a host-specific rewrite rule to `src/proxy/addon.py`.
