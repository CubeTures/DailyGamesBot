# Daily Games Bot

A mitmproxy reverse proxy that serves daily web games from `localhost` and
captures each player's result, plus a Discord bot that hands out play links and
announces results. See `README.md` for the full picture.

## Commands

```sh
uv sync                          # install deps (incl. dev tools)
uv run python3 -m src            # proxy + launcher + Discord bot
uv run python3 -m src.proxy      # proxy + launcher only (no token needed)
uv run python3 -m src.proxy.config  # validate games/ and regenerate games/schema.json
```

## Before finishing any change

Run all of these and fix anything they report:

```sh
uv run ruff format --check --diff
uv run ruff check
uv run pyright --level error
```

If `games/` or `src/proxy/config.py` changed, also run
`uv run python3 -m src.proxy.config`. It regenerates `games/schema.json`;
commit the result.

Pyright runs in strict mode against `src/`, so every function needs full type
annotations.

## Layout

- `src/proxy/`: reverse proxy (`addon.py`), result capture (`capture.py`,
  `capture.js`), game config models (`config.py`), launcher generation
  (`gen_launcher.py`, `launcher.html.j2`)
- `src/proxy/hooks/<game>.py`: optional per-game `request(flow)` /
  `response(flow)` hooks
- `src/discord_bot/bot.py`: `/play` command and result announcements
- `src/results.py`: SQLite results store (`data/results.db`, override with
  `DGB_DB_PATH`)
- `games/<name>/`: one directory per game (`config.toml`, `fields.js`,
  `announcement.j2`, icon); format in `games/README.md`

## Gotchas

- `launcher/index.html` is generated from `src/proxy/launcher.html.j2` on
  every proxy start. Edit the template, not the output.
- A new game's port must be added to `docker-compose.yml` `ports:` and the
  `Dockerfile` `EXPOSE`.
- To add a game or fix its result capture, use the `/add-game` skill.
