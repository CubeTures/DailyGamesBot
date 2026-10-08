# Game configs

Each game is a directory here, `games/<name>/`. Adding a game is just adding
a directory (the `add-game` Claude skill writes it for you). Validate them
all, and regenerate `schema.json`, with:

```sh
uv run python3 -m src.games
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
`src/games/models.py`, and `schema.json` (a JSON Schema) is generated from
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
# higher_score_wins = true           # scoreboard ranks highest score first (default: lowest)

# When the daily puzzle changes; the solve timer starts afresh each game day.
[reset]
time = "00:00"                       # 24-hour HH:MM (default "00:00")
timezone = "local"                   # IANA name, e.g. "America/New_York", or "local"
                                     # for the player's own (default "local")

# Zero or more triggers. Each one says "when X is true, the player has
# finished; report fields.js". A game with no triggers is still proxied, just
# not captured.
[[triggers]]
name = "local-state"                 # unique per game; stored with the result
type = "page"                        # page | network | event
when = "finished"                    # a JS expression; vars.js is in scope
```

`vars.js` (trimmed; the real one documents what NYT stores in comments):

```js
// The daily state object NYT rewrites after every guess.
const st = (() => {
  const key = Object.keys(localStorage).find(k => k.startsWith("games-state-wordleV2/"));
  return ls(key)?.states?.find(s => s.printDate && s.data && !s.data.isPlayingArchive);
})();

// Tile colours are only on the board: one emoji row per fully flipped row.
const rows = /* ... built from [role="group"] rows and each tile's data-state ... */;

// Won or out of rows, and every used row has flipped (so `rows` is complete).
const finished = !!st
  && (st.data.status === "WIN" || (st.data.status !== "IN_PROGRESS" && st.data.currentRowIndex >= 6))
  && rows.length === st.data.currentRowIndex;
```

`fields.js`:

```js
export default {
  puzzle_id: st.printDate,           // REQUIRED
  won: st.data.status === "WIN",
  attempts: st.data.currentRowIndex,
  score: st.data.status === "WIN" ? st.data.currentRowIndex : null, // null = X/6
  max_score: 6,
  rows: rows,
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

`when` should only turn true once every field is final. A result is saved
once, the first time a trigger fires, so a field read a moment too early
stays wrong. Wordle's `finished` waits for the board's last row to flip for
exactly this reason.

Comment `vars.js` with what the game stores and what each value means, and
comment any field in `fields.js` whose meaning isn't obvious (a score's sign,
a formula). That's what the next fix needs.

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
| `time_secs`  | number: solve time; filled in by the proxy if not given   |
| `share_text` | the game's own share string, if it has one                |

Report `time_secs` only when the game times the solve itself (Minute
Cryptic does). Otherwise the capture script fills it in: the first time a
page of the game loads in a game day (see `[reset]`) is when the player
started, and `time_secs` is how long before the result that was. Reloading
or leaving the tab doesn't pause or reset it. It's left out if the player
never clicked or typed since that load, i.e. the puzzle was finished outside
the proxy and its result fired on load. The scoreboard breaks score ties by
it and shows it beside each score.

## Announcement

When a result is saved, the bot posts it to the channel in
`DISCORD_RESULTS_CHANNEL_ID`. `announcement.j2` is a
[Jinja](https://jinja.palletsprojects.com/en/stable/templates/) template for
that message, so each game can show its result its own way. The same text is
shown on the launcher when you click a result on today's scoreboard.

Wordle's:

```jinja
:bee: {{ player }} played **{{ game }}** #{{ puzzle_number }}
{% for row in rows %}
{{ row }}
{% endfor %}
```

which renders as:

```
:bee: @player played **@Wordle** #1571
:white_large_square::yellow_square::white_large_square::white_large_square::white_large_square:
:green_square::green_square::green_square::green_square::green_square:
```

### House style

- Open with `:bee: {{ player }} played **{{ game }}** <puzzle>` (the
  puzzle number, e.g. `#{{ puzzle_number }}`, or the date if it has none), then the result in the
  game's own terms (par, guesses) followed by the time,
  `{{ " in %s" % (time_secs | duration) if time_secs }}`, then a grid or row of emoji if the
  game's share screen has one. See `minutecryptic/announcement.j2` for a
  game with a score and a hint bar.
- Cover every outcome: a loss or give-up should read as one, not as a
  missing score.
- Never spell out the answer; others in the channel may not have played yet.
  What the player put is fine behind a spoiler when nobody could look it up
  later, because it's their own (Krillion's answers).
  Put them in one spoiler block at the end, a line each, so one click
  reveals them all; see `krillion/announcement.j2`. A shared answer
  (Wordle's word) stays out entirely.
- Write emoji as Discord shortcodes (`:green_square:`), not as the characters
  themselves, so they look the same in Discord and on the launcher. The
  launcher only knows the shortcodes in the `SHORTCODES` map in
  `src/launcher/templates/discord-markdown.js`; any other shows as typed, so add it there
  when a template needs it.
- Stick to the markdown the launcher renders too: `**bold**`, `*italic*`,
  `__underline__`, `~~strike~~`, `` `code` ``, `||spoiler||` and `\`
  escapes.

### Template reference

In scope:

- every field the trigger reported, by name. The standard fields above are
  always defined, as `none` if the trigger didn't report them, so
  `{% if score is not none %}` is safe.
- `player`: a mention of the player (rendered as their name, no ping)
- `game`: a mention of the game's role in Discord (so it pings
  subscribers), its `title` on the launcher; `puzzle_id`; `fields`: all fields as a dict
- filters: `duration` (seconds as `1:05` / `1:02:03`) and
  `tiles(answer)` (a guess scored against the answer as a 🟩🟨⬛ row; this
  uses the answer, so only reach for it when the game reports one), `md`
  (a value on one line with its markdown escaped, so text the player typed
  shows as typed) and `spoiler` (the same, as a `||spoiler||`)

Blocks trim their own line, so put `{% ... %}` tags on lines of their own and
use `{%-` to join onto the previous line. Without `announcement.j2`, a generic
message is built from the standard fields. If a template fails at render time
the generic one is used and the error is logged. Messages are cut at
Discord's 2000-character limit. The command above checks the template's
syntax; to see what it renders, give it some fields:

```sh
uv run python3 -m src.announce wordle '{"won": true, "rows": [":green_square::green_square::green_square::green_square::green_square:"]}'
```

## How capture works

The proxy injects `/__dgb/capture.js` (built from `src/proxy/capture/runtime.js` and
the game's directory) at the top of every HTML page of a game that has
triggers. When a trigger fires it POSTs to `/__dgb/result` on the same local
origin; the proxy answers that itself and saves a row in SQLite
(`data/results.db`, see `src/results.py`), keyed on the `dgb_discord_id`
cookie the launcher sets from the `/play` link.

Debug in devtools on a game page: `__dgb.status()`, `__dgb.dryRun()`,
`__dgb.testNetwork(method, url, reqBody, resBody)`.
