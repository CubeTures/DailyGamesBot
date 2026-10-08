export default {
  puzzle_id: d,
  // 2025-04-08, the first Bracket City, is #1
  puzzle_number: Math.round((Date.parse(d) - Date.parse("2025-04-08")) / 864e5) + 1,
  // 0-100, higher is better; the game shows it to one decimal.
  score: Math.round(score * 10) / 10,
  max_score: 100,
  rank: rank,
  hard_mode: mode === "classic",
  wrong_guesses: st.wrongGuesses,
  // Clues whose first letter was shown, including ones later revealed.
  peeks: peeks,
  // Clues whose answer was revealed.
  reveals: reveals,
  keystrokes: st.totalKeystrokes,
  min_keystrokes: st.minimumKeystrokes,
};
