export default {
  puzzle_id: date,
  puzzle_number: day.dayNumber,
  score: day.score,
  max_score: 700, // 7 rounds, 100 for a "One in a Krillion" answer
  // The game shows the score as depth: 10m per point.
  depth_m: day.score * 10,
  band: band(day.score),
  tiers: day.tiers,
  round_scores: day.results?.map(r => r.score) ?? null,
  misses: day.tiers.filter(t => t === "miss").length,
  rows: day.tiers.map(t => tierEmoji[t]?.[1] ?? ":black_large_square:").join(""),
  share_text: `Krillion #${day.dayNumber} 🦐\n${day.score}\n\n${day.tiers.map(t => tierEmoji[t]?.[0] ?? "⬛").join("")}`,
};
