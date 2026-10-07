# Game configs

Each game is one TOML file here, `games/<name>.toml`. Adding a game is just
adding a file (the `add-game` Claude skill writes it for you). Validate them
all with:

```sh
uv run python3 -m src.proxy.config
```

## Format

```toml
name = "wordle"                      # must match the file name; [a-z0-9_]
title = "Wordle"                     # shown on the launcher (default: name)
origin = "https://www.nytimes.com"   # real site; proxied 1:1
port = 8081                          # unique local port (8090 is the launcher)
landing_path = "/games/wordle/index.html"   # default "/"

# Zero or more triggers. Each one says "when X is true, the player has
# finished; report these fields". A game with no triggers is still proxied,
# just not captured.
[[triggers]]
name = "local-state"                 # unique per game; stored with the result
type = "page"                        # page | network | event
when = '''st && st.data.status === "WIN"'''

[triggers.vars]                      # optional shared lookups, in order
st = '''ls("games-state-wordleV2/ANON")?.states?.[0]'''

[triggers.fields]
puzzle_id = '''st.printDate'''          # REQUIRED
won       = '''st.data.status === "WIN"'''
attempts  = '''st.data.currentRowIndex'''
```

This is a trimmed version of `wordle.toml`, which is a complete, verified
example.

Use TOML literal strings (`'''...'''`) for JS so quotes and backslashes need
no escaping.

### Trigger types

| type      | evaluated when                                                     | extra keys |
|-----------|--------------------------------------------------------------------|------------|
| `page`    | on page load, DOM mutations, storage writes, after any fetch/XHR, and every 1s | – |
| `network` | after each fetch/XHR response whose URL matches `url` (a regex, searched) | `url`, optional `method` |
| `event`   | when `event` fires on `target` (`window` default, or `document`)   | `event`, `target` |

### Expressions

`when`, every field and every `vars` entry are JavaScript **expressions** (use an IIFE,
`(() => { ... })()`, if you need statements). A thrown error counts as
false/null. They run in the page, with these in scope:

- the trigger's `vars`, by name (each is re-evaluated before `when` and each
  field, so one var can use the vars before it)
- `req` – network triggers: `{url, method, body, json}` (`json` is the parsed
  body or null)
- `res` – network triggers: `{status, body, json}`
- `event` – event triggers: the DOM event
- `ls(key)` / `ss(key)` – local/sessionStorage value, JSON-parsed if possible
- `text(sel)`, `texts(sel)`, `exists(sel)` – DOM helpers
- `cookie(name)`, `today()` (local `YYYY-MM-DD`)
- anything on `window`

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

## How capture works

The proxy injects `/__dgb/capture.js` (built from `src/proxy/capture.js` and
the game's triggers) at the top of every HTML page of a game that has
triggers. When a trigger fires it POSTs to `/__dgb/result` on the same local
origin; the proxy answers that itself and saves a row in SQLite
(`data/results.db`, see `src/results.py`), keyed on the `dgb_discord_id`
cookie the launcher sets from the `/play` link.

Debug in devtools on a game page: `__dgb.status()`, `__dgb.dryRun()`,
`__dgb.testNetwork(method, url, reqBody, resBody)`.
