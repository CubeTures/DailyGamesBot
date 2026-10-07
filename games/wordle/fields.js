export default {
  puzzle_id: st.printDate,
  // days since the 2021-06-19 launch
  puzzle_number: Math.round((Date.parse(st.printDate) - Date.parse("2021-06-19")) / 864e5),
  won: st.data.status === "WIN",
  attempts: st.data.currentRowIndex,
  score: st.data.status === "WIN" ? st.data.currentRowIndex : null, // null = X/6
  max_score: 6,
  guesses: st.data.boardState.filter(Boolean),
  rows: rows,
  hard_mode: !!st.data.hardMode,
};
