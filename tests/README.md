# Tests

```sh
uv run pytest                              # offline: unit tests, every captured game has a driver
uv run pytest -m live                      # every game, every outcome, live (~15 min)
uv run pytest -m live -k wordle --headed   # one game, watching the browser
uv run pytest -m live -k "chess and lose"  # one scenario
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

`test_capture.py` runs each scenario of each driver in `tests/e2e/games/`:

1. Learns the day's solution if the scenario needs it (see below).
2. Opens a fresh browser context (so today's puzzle is unplayed), visits the
   launcher with its own numeric Discord ID, then the game.
3. Plays to one outcome: usually `win`, `lose` and `mixed` (a win with
   mistakes or hints). Games with no losing have their worst outcome instead
   (`reveal_all`, `hinted`, `far_off`, `misses`).
4. Waits for the row in the database and checks its fields against what the
   driver did, plus checks every game shares: `puzzle_id`, `game_day` by the
   game's `[reset]`, a `time_secs`, exactly one row, and an announcement that
   rendered from the game's template (served by the launcher's
   `/api/results`).

## When one fails

The assertion lists each field that didn't match (`won: expected true, got
false`), then all saved fields and the announcement. If nothing was saved,
it shows `__dgb.status()` and `__dgb.dryRun()` from every frame instead.

`tests/e2e/.artifacts/<test>/<player>/` then holds, for the scenario's player
and the one that learned the solution:

- `trace.zip`: `uv run playwright show-trace <path>` steps through every
  action with DOM snapshots and network
- `screenshot.png`: the final screen
- `status.json`: the saved rows and each frame's `__dgb` state
- `console.log`: the page's console

`proxy.log` in the same directory is the proxy's output for the session.

## Solutions

Puzzles change daily, so drivers learn each day's answers once and cache them
in `tests/e2e/.solutions/<game>/<game day>.json`: from the game's own API
(Wordle, Connections, Chess.com, PokeDoku's answer stats, the board Circuits
is sent), its page state
(Costcodle, Minute Cryptic, Clues by Sam's cards and hints), or by revealing
everything in a throwaway play (Bracket City, Fermi). Krillion's answers are
free text with no list, so its expectations come from the server's own
responses instead. Delete the directory to force a re-learn.

A scenario is skipped if its game's puzzle resets within 10 minutes.

## Known failures

A driver's `known_failures` maps a scenario to a capture bug it exposes. It
runs as a strict xfail: it's reported as `xfail` while the bug is there, and
fails as `XPASS` once it's fixed, so the entry can be removed. There are
none currently.

## Adding a game

`test_coverage.py` fails until a game with triggers has a driver. Add
`tests/e2e/games/<name>.py` exporting `DRIVER = Driver(name=..., learn=...,
scenarios={...})`; `wordle.py` is the simplest. A scenario takes the player
(already on the game's landing page) and the learned solution, plays to its
outcome, and returns the expected fields: plain values, or checks from
`expect.py` (`where`, `approx`, `between`, ...) where a value can't be known
exactly.

Things the existing drivers ran into:

- Welcome, promo and ad overlays: `player.dismiss(locator)` clicks one away
  before any later click. Typing and raw mouse clicks don't trigger that, so
  close an overlay explicitly before typing into the game or clicking board
  coordinates (Bracket City, Chess.com).
- Prefer on-screen keys and buttons to keyboard input where the game has them.
- Bound every loop over game state, so a stuck step fails instead of hanging.
