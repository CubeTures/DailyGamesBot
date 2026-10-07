export default {
  puzzle_id: String(no),
  puzzle_number: no,
  // Lower is better: the geometric mean of the three factors, each capped at
  // 1,000×. 1× is a perfect day.
  score: num(scoreText),
  score_text: scoreText,
  // "Top 72%": the score ranks in the best 72% of today's players
  // (smaller is better).
  top_percent: parseInt(topText?.match(/Top (\d+)%/)?.[1] ?? "", 10) || null,
  // How far off each guess was, as a multiple of the answer (≥ 1×), and
  // whether it was too high or too low.
  factors: factors.map(f => f.value),
  factor_texts: factors.map(f => f.text),
  sides: factors.map(f => f.side),
  // The game's own "Copy Text" share string.
  share_text: [`Fermi · No. ${String(no).padStart(3, "0")}`,
    ...factors.map((f, i) => `0${i + 1}  ${f.text}`),
    "─────────",
    `${scoreText} score${topText ? ` · ${topText.toLowerCase()}` : ""}`,
    "fermi.gg"].join("\n"),
};
