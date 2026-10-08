export default {
  puzzle_id: day,
  // 2025-04-28, the first Clues by Sam, is #1
  puzzle_number: Math.round((Date.parse(day) - Date.parse("2025-04-28")) / 864e5) + 1,
  // Every wrong guess and every hint taken; 0 is a perfect solve.
  score: st.imperfections.length,
  mistakes: countOf("error"),
  hints: countOf("hint"),
  // A second hint on the same clue, which also reveals the card to pick.
  double_hints: countOf("second-hint"),
  time_secs: Math.round(st.completeTime / 1000),
  difficulty: difficulty,
  rows: rows,
};
