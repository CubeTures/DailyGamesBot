# Daily Games Bot

Play daily web games (Wordle, Fermi, Minute Cryptic, Krillion...) through a
local proxy that captures your result, and have a Discord bot post everyone's
scores.

## Setup

```sh
uv sync
cp .env.example .env   # and fill it in
uv run python3 -m src
```

Or with Docker: `docker compose up --build`.

Open http://localhost:8090 for the launcher, or run `/play` in Discord to get
your personal link so your scores count. On the launcher you can also pick
which games' Discord roles you want, to get pinged when someone finishes them.
The pencil beside "Games" lets you hide games you don't play: click a game
once to hide its card, twice to hide its scoreboard too.

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
