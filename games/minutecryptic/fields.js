export default {
  puzzle_id: d,
  // 2024-06-26, the first day in the site's archive, is #1
  puzzle_number: Math.round((Date.parse(d) - Date.parse("2024-06-26")) / 864e5) + 1,
  // Revealing every letter ends the game as "gave_up" (letterRevealOrder empties).
  won: p ? p.letterRevealOrder.length > 0 : null,
  // Help used minus par: negative is under par ("4 under par" is -4).
  score: par != null ? s.h.length - par : null,
  par: par,
  hints: s.h.filter(x => x === "HINT").length,
  letters_revealed: s.h.filter(x => x === "LETTER").length,
  // Every hint plus one reveal per letter: the dots in the game's help row.
  help_available: p ? p.hints.length + Object.keys(p.puzzlePieces).length : null,
  time_secs: s.st && s.ct ? Math.round((Date.parse(s.ct) - Date.parse(s.st)) / 1000) : null,
};
