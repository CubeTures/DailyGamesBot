export default {
  puzzle_id: run.date,
  // 2026-05-13, the first Gauntle, is #1
  puzzle_number: Math.round((Date.parse(run.date) - Date.parse("2026-05-13")) / 864e5) + 1,
  // The run's total in whole seconds, lowest wins, as on Gauntle's own
  // leaderboard; time_secs has it to the hundredth for ties.
  score: Math.round(run.totalMs / 1000),
  time_secs: Math.round(run.totalMs / 10) / 100,
  total_time: clock(run.totalMs),
  // Every game's own time, without deltas or time between games.
  raw_time_secs: games.reduce((t, g) => t + g.raw_ms, 0) / 1000,
  // Sum of the games' bonuses (negative) and penalties (positive).
  delta_secs: Math.round(games.reduce((t, g) => t + g.delta_ms, 0) / 1000),
  flawless: !!run.details.flawless,
  flawless_count: games.filter(g => g.flawless).length,
  game_count: games.length,
  games: games.map(({ raw_ms, delta_ms, ...g }) => g),
};
