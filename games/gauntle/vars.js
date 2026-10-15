// A Gauntle run is eleven mini-games against one clock. Each game's result is
// a raw time plus a bonus (negative) or penalty (positive) delta; failing or
// skipping a game only adds a penalty, so every run ends in a total time and
// there is no losing state.
//
// The day's puzzles are dated in UTC+3: the date rolls over at 21:00 UTC
// (the game's own `new Date(Date.now() + 3h).toISOString().slice(0, 10)`).
const gauntleDay = new Date(Date.now() + 3 * 36e5).toISOString().slice(0, 10);

// Anonymous daily runs: when the last game is done the game writes
//   gauntle:anon:lastPlayedDate    "2026-10-14"
//   gauntle:anon:lastPlayedTime    "1139741.86"  total ms: every game's time and
//                                  delta plus loading/between-game time
//   gauntle:anon:lastPlayedDetails {flawless: false, breakdown: {
//     gameOrder: ["ratiole", "clambers", ...],
//     games: {ratiole: {rawTimeMs: 11584, delta: -12760.1, flawless: true,
//                       failed: false, skipped: false, meta: {...}}, ...}}}
// Nothing writes them mid-run. Archive runs return before writing them and
// Hard Mode skips them, so they only ever hold a daily run.
//
// Logged-in runs don't write those; the network trigger covers them (and
// anonymous runs too, first). The last POST /api/run/complete-game answers
//   {done: true, results: {totalTimeMs, rawTimeMs, totalDeltaMs, flawless, breakdown}}
// and earlier ones {done: false, nextPuzzle, ...}. Its request's runId is
// "<date>-<uuid>". Archive runs post /api/archive/run/complete-game instead.
const run = (() => {
  if (res) {
    const r = res.json?.done ? res.json.results : null;
    const date = /^(\d{4}-\d{2}-\d{2})-[0-9a-f-]{36}$/.exec(req?.json?.runId ?? "")?.[1];
    return r?.breakdown && date ? { date, totalMs: r.totalTimeMs, details: r } : null;
  }
  const date = ls("gauntle:anon:lastPlayedDate");
  const details = ls("gauntle:anon:lastPlayedDetails");
  const totalMs = Number(ls("gauntle:anon:lastPlayedTime"));
  // Only today's run: the keys outlive the day.
  return date === gauntleDay && details?.breakdown && totalMs > 0
    ? { date, totalMs, details }
    : null;
})();

// Names as the game's share text writes them.
const NAMES = { minesweeper: "Mines" };
const gameName = id => NAMES[id] ?? id.charAt(0).toUpperCase() + id.slice(1);

// Times as the game shows them, cut (not rounded) to the hundredth: "1:11.07".
const clock = ms => {
  const cs = Math.floor(ms / 10), s = Math.floor(cs / 100);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}.${String(cs % 100).padStart(2, "0")}`;
};

// One entry per game, in play order.
const games = (run?.details.breakdown.gameOrder ?? []).map(id => {
  const g = run.details.breakdown.games?.[id] ?? {};
  return {
    id,
    name: gameName(id),
    time: clock(g.rawTimeMs ?? 0),
    raw_ms: g.rawTimeMs ?? 0,
    delta_ms: g.delta ?? 0,
    // Seconds added to the run: negative is a bonus.
    delta_secs: Math.round((g.delta ?? 0) / 1000),
    flawless: !!g.flawless,
    failed: !!g.failed,
    skipped: !!g.skipped,
  };
});
