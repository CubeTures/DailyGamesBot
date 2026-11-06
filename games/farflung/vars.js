// localStorage "farflung:owner" names the active record slot (a guest's or a
// signed-in account's):
//   {owner: "guest", generation: "96a5…", storage: 1, slot: "659a9e7b-…"}
// and "farflung:record:v1:<slot>:run:<YYYY-MM-DD>" holds that day's
// expedition, rewritten after every pin. Trimmed, from a finished run:
//   {kind: "first-play", id: "5o3m2t0913", admittedAt: 1793931457066,
//    rounds: [{p: "bird-flag", a: "FJI", n: "Fiji", t: "farflung", pts: 100,
//              c: "FJI", k: "none", ...},
//             {p: "zuckerberg-superyacht-visits", a: null, n: "Brazil",
//              t: "lost", pts: 0, ...}, ...],
//    open: null, done: true, completedAt: 1793931579229}
// Per round: p the prompt id, n the country pinned (null if none or out of
// time), a its code when it was a right answer (null for a miss), t the tier
// the answer earned and pts the km it travelled (the game's own points),
// k the round's clock ("none", or "standard"/"relaxed" in timed play).
// Tiers, rarest last: lost (a miss, 0 km), tourist "Common" (40), guidebook
// "Well known" (retired), traveller "Uncommon" (55), wayfarer "Rare" (70),
// uncharted "Elusive" (85), farflung "Farflung" (100).
//
// `done` turns true with the fifth pin. Every expedition ends that way, so
// there's no loss, just fewer km. Archive and late plays are kept under their
// own day's date (late ones flagged `late`), and replays elsewhere, so only
// today's key is looked at.
const run = (() => {
  const slot = ls("farflung:owner")?.slot;
  const suffix = `:run:${today()}`;
  const key = slot
    ? `farflung:record:v1:${slot}${suffix}`
    : Object.keys(localStorage).find(k => k.startsWith("farflung:record:v1:") && k.endsWith(suffix));
  const r = key ? ls(key) : null;
  return r && Array.isArray(r.rounds) ? r : null;
})();

const finished = !!run && run.done === true && !run.late && run.rounds.length === 5;

// The finish trigger: the game POSTs the run to
// /api/v1/expeditions/<day>/finish once the fifth pin drops, and the answer
// (200) has the day's distances, of which it shows how many it beat:
//   {dropped: [...], late: false, streak: 1,
//    histogram: {buckets: [...], bucketKm: 20, expeditions: 230657,
//                furtherThan: 0.85, yourKm: 295}}
// It isn't stored, so a revisit (the page trigger) has no percentile.
const saved = res?.status === 200 && req?.url?.includes(`/expeditions/${today()}/finish`)
  && res.json?.histogram && !res.json.late ? res.json : null;
