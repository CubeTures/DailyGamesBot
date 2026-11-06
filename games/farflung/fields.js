const TIERS = {
  lost: { name: "Miss", emoji: ":black_large_square:" },
  tourist: { name: "Common", emoji: ":white_large_square:" },
  guidebook: { name: "Well known", emoji: ":yellow_square:" },
  traveller: { name: "Uncommon", emoji: ":green_square:" },
  wayfarer: { name: "Rare", emoji: ":blue_square:" },
  uncharted: { name: "Elusive", emoji: ":purple_square:" },
  farflung: { name: "Farflung", emoji: ":orange_square:" },
};
// The game's lands, by the km the expedition reached (since 2026-10-05).
const LANDS = [
  [500, "The edge"],
  [350, "The ice"],
  [250, "The mountains"],
  [100, "The plains"],
  [0, "The woods"],
];
const km = run.rounds.reduce((sum, r) => sum + (r.pts ?? 0), 0);

export default {
  puzzle_id: today(),
  // 2026-10-05, the first expedition, is #1 (the game's `mr()`).
  puzzle_number: Math.round((Date.parse(today()) - Date.parse("2026-10-05")) / 864e5) + 1,
  // The game's own score: km travelled, the sum of each pin's points.
  // Higher is better: 500 is five Farflung finds, five Common answers make
  // 200, and a miss adds 0.
  score: km,
  max_score: 500,
  km: km,
  // The game's own timing, from pressing Begin to the fifth pin.
  time_secs: Math.round((run.completedAt - run.admittedAt) / 1000),
  // Fraction of the day's expeditions this one went further than (0.85 is
  // further than 85%); only known when the finish trigger fired.
  further_than: saved?.histogram?.furtherThan ?? null,
  land: LANDS.find(([min]) => km >= min)[1],
  misses: run.rounds.filter(r => r.t === "lost").length,
  // Any round played against the clock (the game's timed setting).
  timed: run.rounds.some(r => r.k && r.k !== "none"),
  // One square per pin, by the rarity of the answer.
  row: run.rounds.map(r => TIERS[r.t]?.emoji ?? ":black_large_square:").join(""),
  // The player's own pins, for the spoiler: the country and its tier.
  pins: run.rounds.map(r => ({
    prompt: r.p,
    country: r.n ?? null,
    tier: TIERS[r.t]?.name ?? r.t,
    km: r.pts ?? 0,
  })),
};
