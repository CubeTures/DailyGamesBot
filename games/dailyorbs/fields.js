// Everything is counted up to the day's outcome (see vars.js), so it doesn't
// change if the player keeps going after winning.
const ev = outcome.events;
const orbs = ev.filter(e => e.type === "orb").length;
const heartsLost = ev.filter(e => e.type === "heart").length;
const SHORTCODES = {
  orb: { orange: ":orange_circle:", purple: ":purple_circle:", green: ":green_circle:", blue: ":blue_circle:" },
  heart: { orange: ":orange_heart:", purple: ":purple_heart:", green: ":green_heart:", blue: ":blue_heart:" },
};

export default {
  puzzle_id: st.dateKey,
  // 2026-04-17, the first Daily Orbs, is #1
  puzzle_number: Math.round((Date.parse(st.dateKey) - Date.parse("2026-04-17")) / 864e5) + 1,
  won: outcome.won,
  // Orbs collected by the time the day was decided: 6 for a win.
  orbs: orbs,
  // The scoreboard's score, higher is better: orbs minus hearts lost, so
  // every mistake costs (a perfect win is 6, a win with 2 mistakes 4).
  score: orbs - heartsLost,
  max_score: 6,
  hearts_lost: heartsLost,
  // The game's share row: an orb or a lost heart per event in its puzzle's
  // colour, then a trophy for a win.
  row: ev.map(e => SHORTCODES[e.type]?.[e.color] ?? "").join("") + (outcome.won ? ":trophy:" : ""),
  // Orbs per puzzle, in the game's order (orange, purple, green, blue).
  puzzles: st.puzzles.map(p => ({
    id: p.puzzleId,
    color: p.color,
    orbs: ev.filter(e => e.type === "orb" && e.color === p.color).length,
  })),
};
