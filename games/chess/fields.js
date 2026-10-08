export default {
  puzzle_id: day,
  // 2007-05-08, the first Daily Puzzle, is #1
  puzzle_number: Math.round((Date.parse(day) - Date.parse("2007-05-08")) / 864e5) + 1,
  won: solved && heartsLeft > 0,
  // Mistakes made, one heart each: 0 is a perfect solve, max_score a loss.
  score: hearts - heartsLeft,
  max_score: hearts,
};
