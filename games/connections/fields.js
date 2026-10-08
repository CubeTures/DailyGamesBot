export default {
  puzzle_id: st.printDate,
  // the "No." the game shows; #1 was 2023-06-12
  puzzle_number: Math.round((Date.parse(st.printDate) - Date.parse("2023-06-11")) / 864e5),
  won: !!st.data.puzzleWon,
  // wrong guesses, out of 4
  mistakes: st.data.mistakes,
  // the scoreboard's score: groups solved minus mistakes, higher is better
  // (a perfect solve is 4, a loss with 3 groups -1, a loss with none -4)
  score: (st.data.solvedCategories?.length ?? 0) - st.data.mistakes,
  max_score: 4,
  attempts: st.data.guesses.length,
  groups_found: st.data.solvedCategories?.length ?? 0,
  rows: rows,
};
