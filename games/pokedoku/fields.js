export default {
  puzzle_id: pd.current.date,
  puzzle_number: sol.puzzleId,
  // The game's headline score, lower is better: each correct cell adds the
  // percentage of players who picked that Pokémon there, each empty one 100.
  // That ranks full and partial grids alike, so there's no `won`: a partial
  // grid would show as a loss on the launcher, with no score.
  score: Math.round(pd.stats.uniqueness),
  uniqueness_percentile: pd.stats.uniquenessPercentile,  // "better than N% of players"
  correct: sol.score,
  max_correct: sol.puzzleSize,
  attempts: sol.attempts,
  // The grid row by row: the Pokémon's name, or null for an empty cell.
  cells: sol.cells.map(id => id ? (pd.names?.[id] ?? String(id)) : null),
};
