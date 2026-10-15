const rounds = st.roundResults;

export default {
  puzzle_id: String(st.dailyNumber),
  puzzle_number: Number(st.dailyNumber),
  // The game's own total, higher is better: up to 5,000 for the place plus
  // 5,000 for the year in each of 5 rounds. A strong game is 40,000+, a
  // typical one 20,000-30,000.
  score: st.score,
  max_score: 50000,
  // The game times each round itself, in ms.
  time_secs: Math.round((st.roundDurations ?? []).reduce((a, b) => a + b, 0) / 1000) || null,
  rounds: rounds.map(r => ({
    score: r.totalScore,
    place_score: r.distanceScoreValue,
    year_score: r.yearScoreValue,
    km: Math.round(r.distanceMeters / 100) / 10,
    years_off: Math.abs(r.guessYear - r.actualYear),
  })),
  // Rounds with the year exactly right.
  exact_years: rounds.filter(r => r.guessYear === r.actualYear).length,
  // The share text's rows, as shortcodes.
  rows: rounds.map(r => `:earth_americas:${placeBar(r)} :date:${yearBar(r)}`),
};
