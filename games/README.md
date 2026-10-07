# Game configs

Each game is a directory here, `games/<name>/`. Adding a game is just adding
a directory (the `add-game` Claude skill writes it for you). Validate them
all, and regenerate `schema.json`, with:

```sh
uv run python3 -m src.proxy.config
```

| file              | holds                                                        |
|-------------------|--------------------------------------------------------------|
| `config.toml`     | the game's metadata and its triggers (required)              |
| `vars.js`         | shared lookups, run before `when` and `fields.js` (optional) |
| `fields.js`       | the result reported when a trigger fires (needed with triggers) |
| `announcement.j2` | the Discord message for a result (optional)                  |
| icon (e.g. `icon.png`) | the launcher icon named by `icon` (optional)            |

The icon should be square and at least 128px; it's inlined into the
launcher page, so keep it small. Without one, the launcher shows the title's
first letter. Anything else in the directory is an error, so a misnamed file
doesn't get silently ignored.

`config.toml`'s format is defined by the Pydantic models in
`src/proxy/config.py`, and `schema.json` (a JSON Schema) is generated from
them; don't edit it by hand. Start the file with `#:schema ../schema.json` and
a TOML language server (Even Better TOML / taplo, or tombi) will autocomplete
keys and flag mistakes as you type. The command above also checks what the
schema can't: the name matching the directory, unique trigger names, unique
ports, `fields.js` exporting a `puzzle_id`, and the announcement's Jinja
syntax. Neither checks the JavaScript itself; for that, see the add-game
skill's `node --check` step.

## Format

`wordle/` is a complete, verified example. Trimmed, its `config.toml`:

```toml
#:schema ../schema.json

name = "wordle"                      # must match the directory; [a-z0-9_]
title = "Wordle"                     # shown on the launcher (default: name)
description = "Guess the hidden five-letter word in six tries."  # on the launcher
icon = "icon.png"                    # image in this directory; png/svg/webp/jpg
origin = "https://www.nytimes.com"   # real site; proxied 1:1
port = 8081                          # unique local port (8090 is the launcher)
landing_path = "/games/wordle/index.html"   # default "/"

# Zero or more triggers. Each one says "when X is true, the player has
# finished; report fields.js". A game with no triggers is still proxied, just
# not captured.
[[triggers]]
name = "local-state"                 # unique per game; stored with the result
type = "page"                        # page | network | event
when = "finished"                    # a JS expression; vars.js is in scope
```

`vars.js`:

```js
const st = ls("games-state-wordleV2/ANON")?.states?.[0];
const finished = st?.data.status === "WIN";
```

`fields.js`:

```js
export default {
  puzzle_id: st.printDate,           // REQUIRED
  won: st.data.status === "WIN",
  attempts: st.data.currentRowIndex,
};
```

### vars.js vs fields.js

Both are plain JavaScript run in the game's page; the difference is what
happens to the result.

- **`vars.js`** is scratch work: statements (`const`, `function`, ...) that
  find and compute things. Nothing in it is saved. It runs first, every time
  a trigger is checked, so its names are in scope for `when` and `fields.js`.
  Put "find the state object" here once instead of repeating it.
- **`fields.js`** is the result. Its `export default` object is exactly what
  gets stored in the database and handed to the announcement template. It
  only runs once `when` is true, so it can assume whatever `when` checked
  (e.g. that `st` exists).

Every trigger in the game shares both files, so keep fields consistent
across triggers (a network fallback can read `res` where a page trigger
reads storage, e.g. `const st = res?.json ?? ls(...)`).

### Trigger types

| type      | evaluated when                                                     | extra keys |
|-----------|--------------------------------------------------------------------|------------|
| `page`    | on page load, DOM mutations, storage writes, after any fetch/XHR, and every 1s | – |
| `network` | after each fetch/XHR response whose URL matches `url` (a regex, searched) | `url`, optional `method` |
| `event`   | when `event` fires on `target` (`window` default, or `document`)   | `event`, `target` |

### Expressions

`when`, `vars.js` and `fields.js` run in the page. If any of them throws, the
check counts as not finished (the error shows in `__dgb.status().errors`), so
guard lookups with `?.` in `vars.js`. In scope:

- everything `vars.js` declares
- `req` – network triggers: `{url, method, body, json}` (`json` is the parsed
  body or null)
- `res` – network triggers: `{status, body, json}`
- `event` – event triggers: the DOM event
- `ls(key)` / `ss(key)` – local/sessionStorage value, JSON-parsed if possible
- `text(sel)`, `texts(sel)`, `exists(sel)` – DOM helpers
- `cookie(name)`, `today()` (local `YYYY-MM-DD`)
- anything on `window`

`vars.js` can't declare `req`, `res` or `event`.

### Fields

`puzzle_id` is required and identifies the daily puzzle; together with game
and player it is the dedupe key, so the game re-showing a finished state on
reload is harmless. Use the game's own puzzle number/date when it has one,
otherwise `today()`. Everything else is free-form and stored as JSON, but
prefer these names where they apply so results compare across games:

| field        | meaning                                                   |
|--------------|-----------------------------------------------------------|
| `won`        | bool: solved / passed                                     |
| `score`      | number: the game's headline score                         |
| `max_score`  | number: best possible / out-of                            |
| `attempts`   | number: guesses/tries used                                |
| `time_secs`  | number: solve time                                        |
| `share_text` | the game's own share string, if it has one                |

## Announcement

When a result is saved, the bot posts it to the channel in
`DISCORD_RESULTS_CHANNEL_ID`. `announcement.j2` is a
[Jinja](https://jinja.palletsprojects.com/en/stable/templates/) template for
that message, so each game can show its result its own way. The same text is
shown on the launcher when you click a result on today's scoreboard.

```jinja
{{ player }} — **Wordle {{ "{:,}".format(puzzle_number) }}** {{ score if won else "X" }}/6
{% if won %}
{% for guess in guesses %}
{{ guess | tiles(guesses[-1]) }}
{% endfor %}
{% endif %}
```

In scope:

- every field the trigger reported, by name. The standard fields above are
  always defined, as `none` if the trigger didn't report them, so
  `{% if score is not none %}` is safe.
- `player`: a mention of the player (rendered as their name, no ping)
- `game`: the game's `title`; `puzzle_id`; `fields`: all fields as a dict
- filters: `duration` (seconds as `1:05` / `1:02:03`) and
  `tiles(answer)` (a guess as a Wordle-style 🟩🟨⬛ row)

Blocks trim their own line, so put `{% ... %}` tags on lines of their own and
use `{%-` to join onto the previous line. Without `announcement.j2`, a generic
message is built from the standard fields. If a template fails at render time
the generic one is used and the error is logged. The command above checks the
template's syntax; to see what it renders, give it some fields:

```sh
uv run python3 -m src.announce wordle '{"puzzle_number": 1935, "won": true, "score": 3, "guesses": ["crane", "plate", "grape"]}'
```

## How capture works

The proxy injects `/__dgb/capture.js` (built from `src/proxy/capture.js` and
the game's directory) at the top of every HTML page of a game that has
triggers. When a trigger fires it POSTs to `/__dgb/result` on the same local
origin; the proxy answers that itself and saves a row in SQLite
(`data/results.db`, see `src/results.py`), keyed on the `dgb_discord_id`
cookie the launcher sets from the `/play` link.

Debug in devtools on a game page: `__dgb.status()`, `__dgb.dryRun()`,
`__dgb.testNetwork(method, url, reqBody, resBody)`.
