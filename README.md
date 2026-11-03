# Daily Games Bot

Play daily web games (Wordle, Fermi, Minute Cryptic, Krillion...) through a
local proxy that captures your result, and have a Discord bot post everyone's
scores.

![Logo](src/launcher/templates/favicon.png)

## Commands

- `/play`
    - Get a personal link to register with a server
- `/primary`
    - Set the current server as your primary

## Adding games

Games live in `games/<name>/`, one directory each. The easiest way to add one
is the [Claude Code](https://claude.com/claude-code) `/add-game` skill:

```
/add-game https://example.com/daily-puzzle
```

It sets up the game's config, opens it in a browser through the proxy, and
asks you to play a round or two. From what the page does, it works out how to
detect a finished game, which result fields to capture, and what the Discord
announcement should say, then checks it all end to end. Once it works, open a
pull request.

## Setup

```sh
uv sync
cp .env.example .env   # and fill it in
uv run python3 -m src
```

Or with Docker: `docker compose up --build`. To deploy it behind a
Cloudflare Tunnel, see [SETUP.md](SETUP.md).

## Admins

- Run `uv run python3 -m src.store reset-token <discord id>` to reset someone's token
- Use `DISCORD_ADMIN_CHANNEL_ID` and the `ghcr.io/<repo>-with-tests` image to test and get a report for degradation of any games
