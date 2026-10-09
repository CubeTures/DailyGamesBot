---
name: add-game
description: Add a new web game to the Daily Games Bot, or build/fix the result-capture config for an existing one. Opens the game through the local proxy in a Playwright browser with an event recorder, has the user play it, then inspects what the page did (storage, network, analytics, DOM events, final screen) to write the games/<name>/ triggers, fields and Discord announcement that report the player's result, and verifies them end to end, including in the launcher. Use when the user wants to add/support a game, or create, debug or fix capture config for a game.
argument-hint: <game url | existing game name>
---

# Add a game / build its capture config

Goal: a `games/<name>/` directory whose `config.toml` `[[triggers]]` fire
exactly once the player has **finished** today's puzzle (won *or* lost), with
every reported field already final, and that extracts a stable `puzzle_id`
plus the result fields (`fields.js`) and turns them into an announcement
(`announcement.j2`) in the house style.

Read `games/README.md` first. It is the format reference: the files in a
game's directory, trigger types, the expression helpers, the standard field
names, and the announcement house style. The runtime that executes the config
is `src/proxy/capture/runtime.js`. Use `games/wordle/` and `games/minutecryptic/` as
the models for a finished game: commented `vars.js`, a short `when`, and an
announcement that reads like the game's share screen.

A finished game touches:

| file | what |
|------|------|
| `games/<name>/config.toml` | metadata (`title`, `description`, `icon`, `origin`, `landing_path`) and `[[triggers]]` |
| `games/<name>/icon.png` | launcher icon, square, at most 128px |
| `games/<name>/vars.js` | commented lookups shared by `when` and the fields |
| `games/<name>/fields.js` | the result: `puzzle_id` plus standard and game-specific fields |
| `games/<name>/announcement.j2` | the Discord / launcher message |

Paths below are relative to the repo root. `$SCRATCH` is your scratchpad dir.
Playwright tools are the `mcp__plugin_playwright_playwright__*` MCP tools.

## 1. Set up the game entry

- **Existing game** (argument is a name in `games/`): read the files in `games/<name>/` and skip to step 2.
- **New game** (argument is a URL):
  - Run `uv run python3 -m src.games` to see the existing games.
  - Split the URL into `origin` (scheme + host) and `landing_path` (path + query).
  - Derive `name` from the host, e.g. `www.minutecryptic.com` becomes `minutecryptic`. It must be lowercase `[a-z0-9]`; it's also the game's subdomain, `http://<name>.localhost:8080`.
  - Write `games/<name>/config.toml` starting with a `#:schema ../schema.json` line, then `name`, `title`, `description`, `icon`, `origin` and `landing_path`, and no triggers yet. Use the game's own spelling for `title` (`Minute Cryptic`, not `Minutecryptic`).
  - For `description`, write one short sentence on how the game plays, based on the site's `<meta name="description">` or `og:description`.
  - For `icon`, save the site's largest square icon as `games/<name>/icon.png` and set `icon = "icon.png"`. Look for `apple-touch-icon` or a `<link rel="icon">` of 128px or more, and fall back to `/favicon.ico`. Convert an `.ico` to PNG by extracting its largest frame, and downscale anything over 128px to 128px, e.g. `uv run --no-project --with pillow python -I -c ...`. View the result to make sure it's the logo and not a blank or placeholder image.
  - Run the config command again to validate.

## 2. Start the proxy (no Discord bot needed)

Use a scratch DB so test results never reach the real one. Run it with
`run_in_background`:

```sh
DGB_DB_PATH=$SCRATCH/add-game.db uv run python3 -m src.proxy
```

Wait until `curl -s -o /dev/null -w '%{http_code}' http://<name>.localhost:8080/`
answers, retrying if the connection is refused. If the ports are already taken,
an earlier proxy is still running: stop it as in step 8.

## 3. Open the game with the recorder

1. If you already used the browser in this session, call `browser_close` first. Init scripts stack up per context.
2. Install the recorder: call `browser_run_code_unsafe` with `filename` set to the **absolute** path of `.claude/skills/add-game/install-recorder.js`. It records fetch, XHR and sendBeacon calls with bodies, plus storage writes, cookie writes, dispatched DOM events, postMessage, history changes and dataLayer pushes. The log persists across reloads.
3. Call `browser_navigate` to `http://localhost:8080/?discord_id=dgb-test`. For a new game, take a `browser_snapshot` and check its card shows the right title, description and icon.
4. Call `browser_navigate` to `http://<name>.localhost:8080/__dgb/enter?discord_id=dgb-test&to=<landing_path>` (what the card's link does). It sets the `dgb_discord_id` cookie that results are keyed on, on the game's subdomain, and redirects to the game. Take a `browser_snapshot` to confirm the game actually renders and is playable.
   - If it's broken, check `browser_console_messages` and `browser_network_requests`. Typical causes are absolute URLs to another host (see "Known limitation" in `README.md`) or the game living in a cross-origin iframe. In the iframe case, the config's `origin` should probably be the iframe's origin.
   - Fix the problem or report it before involving the user.
5. Check whether today's puzzle already shows as finished in this browser profile. If it does, tell the user. Ideally they play from a fresh state.

## 4. Hand over to the user and STOP (run 1)

Tell the user:

- Play the game to the end in the Playwright browser window, until the results or score screen is showing. Try to win: a losing run comes later if the game has one.
- Say "done" here, along with the result they got (score, win/loss, time). That is the ground truth for checking the extracted fields.

**End your turn and wait.** Don't poll or touch the browser while they play.

## 5. Collect evidence (after the user says done)

Use `browser_evaluate` to collect:

- `() => __dgbRec.mark("user done")`
- `() => __dgbRec.summary()`: the whole timeline. If it's huge, narrow it with `summary({kind: "net"})`, `summary({kind: "storage"})`, `summary({grep: "score|result|complete|win|solve|finish|stat"})`, or `{from: N}`.
- `() => __dgbRec.storageKeys()`: which storage keys the game wrote while playing. Ignore ad and tracker noise.
- `() => __dgbRec.storage("<regex of the interesting keys>")`: their current values.
- `() => __dgbRec.get(i)`: full bodies of interesting network, event and dataLayer entries.

Then cross-check:

- `browser_snapshot` of the final screen.
- `browser_network_requests` (`static: false`), which also catches requests the in-page recorder can't see.

Work out what changed **at the moment of finishing**, for example:

- a storage key's status flipping
- a POST of stats
- an analytics event like `level_complete`
- a results modal appearing

Also find where the puzzle's identity lives: puzzle number, date or id.

**Save the run before moving on.** Step 6 wipes the browser's copy of it.
Call `browser_evaluate` with `filename` set to the absolute path of
`.playwright-mcp/add-game/run-<n>-<outcome>.json` (e.g. `run-1-win.json`).
Playwright can only write inside the repo, not to `$SCRATCH`, and
`.playwright-mcp/` is gitignored. Return everything the triggers might need:

```js
() => ({
  outcome: "win",                       // what the user reported, plus their score etc.
  storage: __dgbRec.storage("<regex of the interesting keys>"),
  entries: [/* indices of key net/event/dataLayer entries */].map(i => __dgbRec.get(i)),
  timeline: __dgbRec.summary({ grep: "<same regex>|<interesting urls>" }),
})
```

Also note the final screen in a sentence or two, since DOM state isn't in the file.

## 6. Losing run (run 2)

Wins and losses often look different, for example a different status value, a
different modal, or a missing score. A config built from a win alone will
silently miss losses, so get a real one where the game has it.

1. Ask the user with `AskUserQuestion` whether the game has a lose or fail state. Options:
   - **"Yes, I'll play again and lose"**
   - **"No, every game ends in a result"**, e.g. a score or a time with no failure
   - **"Not sure"**: check the game's help screen yourself, then treat it as yes or no

   If run 1 was a loss, ask about a winning run instead. Everything below applies the same way with the outcomes swapped.
2. If there's no lose state, skip to step 7 and say so in the report.
3. Otherwise start a fresh session for the game. Today's puzzle is already finished in this browser, and the Playwright profile persists, so `browser_close` alone isn't enough. Wipe the game origin's storage (cookies, local/sessionStorage, IndexedDB, cache, service workers) with `browser_run_code_unsafe`:
   ```js
   async (page) => {
     const origin = "http://<name>.localhost:8080";
     const cdp = await page.context().newCDPSession(page);
     await cdp.send("Storage.clearDataForOrigin", { origin, storageTypes: "all" });
     await cdp.detach();
     return "cleared";
   }
   ```
   This also removes the game's `dgb_discord_id` cookie and the recorder's log. The recorder itself stays installed.
4. Call `browser_navigate` to the `/__dgb/enter` URL from step 3 again.
5. Take a `browser_snapshot` to confirm today's puzzle is **unplayed** again. If it still shows finished, the game keeps state server-side (by account or IP), so a second run isn't possible this way. In that case:
   - Say so.
   - Skip the run and treat the losing path as unverified.
   - Cover it in step 9 with synthetic states built from what you know.
6. Hand over: ask the user to play today's puzzle again and **lose on purpose**, e.g. by entering wrong guesses until it ends or letting the timer run out. They should say "done" plus what the losing screen showed. **End your turn and wait.**
7. After "done", collect evidence and save it to `.playwright-mcp/add-game/run-2-lose.json`, exactly as in step 5.
8. Compare the two runs. Note the fields and keys that differ (status values, row or attempt counts, score present or absent) and the ones that don't. Both outcomes must satisfy `when`, and `won` must tell them apart.

## 7. Choose signals and write the config

### Triggers

Prefer structured, durable signals over presentation. Rough order:

1. **Storage state** with an explicit finished status (`page` trigger using `ls()`/`ss()`). It survives reloads, so it also re-reports on revisit, which dedupe absorbs. This is usually best.
2. **Network**: an API call that saves the result or stats, or a response containing them (`network` trigger on `req.json`/`res.json`). Only use a request that happens when the player finishes. Re-fetching state on page load is fine too.
3. **Analytics/dataLayer** completion events (`page` trigger such as `window.dataLayer?.some(e => e.event === "...")`), or **custom DOM events** (`event` trigger).
4. **DOM text** of the results screen (`text()`, `exists()`). Use it only as a last resort or a fallback, since it breaks on redesigns.

Rules:

- `when` must be false mid-game and true for both wins and losses. Base this on the real values from both runs (step 6), not on guessed status names.
- `when` must only become true once **every field is final**. A result is saved the first time a trigger fires and never updated, so a field read during an end-of-game animation stays wrong. If a field comes from the DOM, `when` waits for it too (Wordle's `finished` requires `rows.length === st.data.currentRowIndex`, i.e. every used row has flipped).
- `when` must exclude non-daily modes (archive, practice, unlimited) unless `puzzle_id` tells them apart.
- `puzzle_id` must be identical across reloads and across every trigger of the game, otherwise one play gets saved twice. Prefer the game's own puzzle number, then date, then `today()`.
- Multiple triggers are fine as primary and fallback. The first to fire is saved and later ones count as duplicates. Keep their fields consistent.
- Keep `when` in `config.toml` short. For anything longer, compute it in `vars.js` (e.g. `const finished = ...`) and set `when = "finished"`.

### vars.js and fields.js

- Put lookups that `when` and the fields share, like "find the state object", in `vars.js` instead of repeating them.
- Open `vars.js` with a comment showing what the game stores, with a trimmed real value from the runs and what each key means (see `games/wordle/vars.js` and `games/minutecryptic/vars.js`). Note how a loss shows up and how archive/practice plays are excluded.
- When storage lacks something the announcement needs (Wordle's tile colours), derive it from the DOM in `vars.js`, say in a comment where on the page it comes from, and gate `when` on it as above.
- Use the standard field names from `games/README.md` where they fit (`won`, `score`, `max_score`, `attempts`, `time_secs`, `share_text`). Report `won` whenever the game can be lost. Add game-specific extras freely, especially anything the announcement shows. Only report `time_secs` if the game times the solve itself; otherwise the capture script fills it in. Either way, show it in the announcement. Set `[reset]` to when the game's daily puzzle changes (default: the player's local midnight).
- Comment any field whose meaning isn't obvious: a score's sign or units, a derived number, a formula (see `games/minutecryptic/fields.js`).
- Write `vars.js` and `fields.js` defensively with `?.`. A throw anywhere skips the whole check (no result is sent), and a field that silently comes back null is a bug.
- Don't capture secrets or tokens. Keep `share_text`-like data small. Fields may hold the answer (Wordle's `guesses` end with it), but the announcement must not show it. When the player's answers are their own and can't be looked up later (Krillion's free-text answers), capture them as a field so the announcement can show them behind a spoiler.

### announcement.j2

Write the game's announcement following the house style in "Announcement" in
`games/README.md`:

- First line `:bee: {{ player }} played **<title>** <puzzle>`: the game's puzzle number (`#{{ puzzle_number }}`), or `{{ puzzle_id }}` if it has none.
- Then the result in the game's own terms (score vs. par, time, guesses), and an emoji grid or bar if the game's share screen has one. Mirror that share screen.
- Every outcome reads correctly: win, loss or give-up, and missing optional fields (`{% if x is not none %}`).
- Never spell out the answer. The player's own answers (see above) go in one `||spoiler||` block at the end, a line each, escaped with `| md` (see `games/krillion/announcement.j2`).
- Emoji as Discord shortcodes (`:green_square:`), only ones in the `SHORTCODES` map in `src/launcher/templates/discord-markdown.js`. If you need another, add it to that map (the shortcode and its emoji) so the launcher renders it too.
- Only the markdown the launcher renders: `**bold**`, `*italic*`, `__underline__`, `~~strike~~`, `` `code` ``, `||spoiler||`.

Preview it for every outcome with the field values from the runs:

```sh
uv run python3 -m src.announce <name> '<fields JSON from a run>'
```

### Validate

```sh
uv run python3 -m src.games
uv run python3 -m src.proxy.capture <name> > $SCRATCH/capture.js && node --check $SCRATCH/capture.js
```

The first checks the config, the files in the directory, `fields.js`'s
`export default` and `puzzle_id`, and the template's syntax, and regenerates
`games/schema.json`. The second is the only check of the JavaScript itself.

## 8. Restart the proxy

The script is built when the proxy starts, so restart it after every config
change:

```sh
pkill -TERM -f -- '-m [s]rc\.proxy$'   # bracket keeps pkill from matching its own shell
ss -ltn | grep -E ':(8080|8090)\b' || echo free
```

Then start it again as in step 2.

## 9. Verify end to end

All of these must pass. Iterate on the config (steps 7 and 8) until they do.

1. **Positive, live.** Reload the played page (it now holds the last run) and wait about 3s, then check `() => __dgb.status()`.
   - `log` should show `200 {"status": "saved"}`, or `duplicate` on later runs.
   - `errors` should be empty.
   - The fields should match the user's ground truth.
   - Confirm the row in the DB:
     ```sh
     uv run python3 -c "import sqlite3; [print(r) for r in sqlite3.connect('$SCRATCH/add-game.db').execute('select game, discord_id, puzzle_id, data, trigger from results')]"
     ```
2. **Positive, replayed.** The browser only holds the last run, so check the other saved run(s) by replaying them. Nothing gets sent.
   - **Storage triggers.** In a fresh context with no discord cookie (as in check 4), write the run's saved `storage` values into `localStorage`/`sessionStorage`, then call `__dgb.dryRun()`. The trigger must fire, with fields matching that run's ground truth.
   - **Network triggers.** Replay the saved entries:
     ```js
     () => { const e = /* entry from run-N.json, or __dgbRec.get(i) */; return __dgb.testNetwork(e.method, e.url, e.req, e.res, e.status); }
     ```
3. **Mid-game.** From the saved runs, derive an unfinished state, e.g. the storage value as it was after the first move (the timeline has each write). Replay it the same way and confirm nothing fires.
4. **Negative (fresh player).** In a brand-new context with **no** discord cookie, nothing can be saved even if a trigger misfires. Use `browser_run_code_unsafe`:
   ```js
   async (page) => {
     const ctx = await page.context().browser().newContext();
     try {
       const p = await ctx.newPage();
       await p.goto("http://<name>.localhost:8080<landing_path>");
       await p.waitForTimeout(4000);
       return await p.evaluate(() => ({ dry: __dgb.dryRun(), log: __dgb.state.log, errors: __dgb.state.errors }));
     } finally { await ctx.close(); }
   }
   ```
   Every `dry[].fired` must be `false` and `log` must be empty. A 400 entry in `log` means something fired.
5. If a mode the config must ignore (archive, practice) can't be derived from the runs, consider asking the user to start one. That checks `when` stays false there.
6. **Launcher.** The launcher reads the same scratch DB. Call `browser_navigate` to `http://localhost:8080/`, find the `dgb-test` row for the game on today's scoreboard (shown as `Player …test`), click it and `browser_snapshot` the dialog. The announcement must render as intended: no raw `:shortcode:` or `**` left over, no `None`, the outcome reads right. The mention shows as a literal `<@dgb-test>` because the test ID isn't numeric; that's expected.

## 10. Clean up and report

- Stop the proxy (step 8) and call `browser_close`.
- Add a live-test driver, `tests/e2e/games/<name>.py`, with a scenario per
  outcome the game has (see "Adding a game" in `tests/README.md`), and run it
  with `uv run pytest -m live -k <name>`. A new game fails `uv run pytest`
  until it has one.
- Delete `$SCRATCH/add-game.db` and `.playwright-mcp/add-game/`.
- Run `uv run ruff check src && uv run pyright` if you touched Python.
- Run `uv run python3 -m src.games` once more, then `git status`. The changes should be exactly the files in the table at the top plus the driver in `tests/e2e/games/` (and `src/launcher/templates/discord-markdown.js` if you added a shortcode).
- Report to the user:
  - which signal(s) you chose and why
  - the fields captured, with the values seen in verification for each outcome (win and lose)
  - the announcement as rendered for each outcome, and whether it looked right in the launcher dialog
  - whether the losing path was verified with a real run, with synthetic states only, or not at all (and why)
  - anything fragile, such as DOM-based triggers or timezone-based `puzzle_id`
  - any proxy fixes needed
- Don't commit unless asked.
