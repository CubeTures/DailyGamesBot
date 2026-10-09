export default {
  puzzle_id: daily.dateKey,
  // Puzzmo's daily number, the same for every game that day: days since
  // 2023-10-16 (their day 0), plus one. dateKey is the Chicago date (see
  // [reset]), so this follows Puzzmo's day, not the player's.
  puzzle_number:
    daily.seriesNumber ??
    Math.round((Date.parse(daily.dateKey) - Date.parse("2023-10-16")) / 864e5) + 1,
  date: gp.puzzle.dailyTitle, // "Oct 8, 2026"
  score: gp.pointsAwarded,
  time_secs: gp.elapsedTimeSecs,
  boxes: submits.length,
  submits: submits.reduce((n, w) => n + w.length, 0),
  // Every submit but the right one in each box.
  wrong: submits.reduce((n, w) => n + Math.max(w.length - 1, 0), 0),
  bolts: bolts.reduce((n, b) => n + b.length, 0),
  // Per box, in board order: wrong submits and Bolts before it was solved.
  box_wrong: submits.map(w => Math.max(w.length - 1, 0)),
  box_bolts: bolts.map(b => b.length),
};
