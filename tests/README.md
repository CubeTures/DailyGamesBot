# Tests

```sh
uv run pytest                              # offline: unit tests, every captured game has a driver
uv run pytest -m live                      # every game once, live
uv run pytest -m live -k wordle --headed   # one game, watching the browser
uv run pytest -m live --keep-artifacts     # keep traces for passing tests too
```

The offline unit tests (`tests/unit/`) cover the pieces with no browser:
the store, the proxy's rewrites, the capture endpoints and script (each
game's built script is checked with `node --check`), announcements, and the
launcher's API. Each test gets its own scratch database.

The live tests (`tests/e2e/`) play each game on its real site, through the
proxy, and check the result the capture script saved. They're how a
regression in recording results shows up: a site changing its storage, a
trigger that no longer fires, a field that comes out wrong.

They need ports 8080 and 8090 free (stop a running `src.proxy` first) and use
the system Chrome. The session starts its own proxy on a temporary database,
so the real `data/results.db` is never touched.

## What a test does

There's one live test per game, and all it asks is whether the capture still
fires at the end of a game and saves the right result. `test_capture.py`
runs each driver in `tests/e2e/games/`:

1. Learns the day's solution if the driver needs one from an API (see below).
2. Opens a fresh browser context (so today's puzzle is unplayed), visits the
   launcher with a /play token for its own numeric Discord ID, then the game.
3. Plays to the end with the driver's `play`.
4. Waits for the row in the database and checks its fields against what the
   driver did, plus checks every game shares: `puzzle_id`, `game_day` by the
   game's `[reset]`, a `time_secs`, exactly one row, and an announcement that
   rendered from the game's template (served by the launcher's
   `/api/results`).

### How a driver plays

A driver takes the surest way to a finished game: losing, giving up,
revealing, skipping or letting a clock run out all count. The one limit is
that **every field the capture reports gets real data**. Every kind of event
the game's `fields.js` counts (a wrong guess, a hint, an orb, a lost heart, a
Bolt, a give-up) happens at least once, so a broken source can't pass as a
zero. That usually means a mistake or a hint first, then the cheapest way to
the end: Wordle guesses one wrong word and then the answer, Bracket City makes
a wrong guess and then reveals every clue, PokeDoku makes one right guess and
one wrong one and then gives up.

What it expects comes only from what it did or saw. Where a value can't be
known in advance, the check is that the result adds up instead (`expect.ALL`
checks fields together: Costcodle Checkout's total is the sum of what each
product was off by).

## When one fails

A capture problem raises `CaptureFailed` (wrong fields, a result from an
unfinished game, or nothing saved though a trigger fires); anything else,
including `NoResult` (nothing saved and no trigger fires), is most likely the
driver's. The daily report marks the first 🔴 and the rest 🟡.

So a driver's own sanity checks raise plain assertions, and they should
avoid the storage the capture reads (unless the driver needs it to steer,
as Daily Orbs does): a change there should come out as a `CaptureFailed`.

The assertion lists each field that didn't match (`won: expected true, got
false`), then all saved fields and the announcement. If nothing was saved,
it shows `__dgb.status()` and `__dgb.dryRun()` from every frame instead.

`tests/e2e/.artifacts/<test>/<player>/` then holds, for the player that
played (`play`) and the one that learned the solution (`learn`):

- `trace.zip`: `uv run playwright show-trace <path>` steps through every
  action with DOM snapshots and network
- `screenshot.png`: the final screen
- `status.json`: the saved rows and each frame's `__dgb` state
- `console.log`: the page's console

`proxy.log` in the same directory is the proxy's output for the session.

## Solutions

Puzzles change daily. Where a driver needs the day's answers, it reads them
in the game's own page if it can (Blossom's puzzle cache, Costcodle's price,
the board Circuits is sent, TimeGuessr's years, the cards in Clues by Sam).
Drivers that need the game's API instead (Wordle, Connections, Chess.com,
Daily Orbs, Tightrope) have a `learn`, which runs once per game day and is
cached in `tests/e2e/.solutions/<game>/<game day>.json`. Delete the directory
to force a re-learn.

A game's test is skipped if its puzzle resets within 10 minutes.

## Known failures

A driver's `known_failure` names a capture bug its test exposes. The test
then runs as a strict xfail: it's reported as `xfail` while the bug is there,
and fails as `XPASS` once it's fixed, so the entry can be removed. There are
none currently.

## Adding a game

`test_coverage.py` fails until a game with triggers has a driver. Add
`tests/e2e/games/<name>.py` exporting `DRIVER = Driver(name=..., play=...)`
(and `learn=...` if it needs an API's answers); `wordle.py` is the simplest.
`play` takes the player (already on the game's landing page) and the learned
solution (empty without `learn`), plays to the end as in "How a driver plays"
above, and returns the expected fields: plain values, or checks from
`expect.py` (`where`, `approx`, `between`, `ALL`...) where a value can't be
known exactly.

Things the existing drivers ran into:

- Welcome, promo and ad overlays: `player.dismiss(locator)` clicks one away
  before any later click. Typing and raw mouse clicks don't trigger that, so
  close an overlay explicitly before typing into the game or clicking board
  coordinates (Bracket City, Chess.com).
- Prefer on-screen keys and buttons to keyboard input where the game has them.
- Bound every loop over game state, so a stuck step fails instead of hanging.
