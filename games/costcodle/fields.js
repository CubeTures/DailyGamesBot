const arrows = { "&uarr;": ":arrow_up:", "&darr;": ":arrow_down:", "&check;": ":white_check_mark:" };
const colors = { "guess-far": ":red_square:", "guess-near": ":yellow_square:" };

export default {
  puzzle_id: String(st.gameNumber),
  puzzle_number: st.gameNumber,
  won: st.hasWon === true,
  attempts: st.guesses.length,
  score: st.hasWon ? st.guesses.length : null, // null = X/6
  max_score: 6,
  // guessed prices, e.g. "24.99"; the last one of a win is within 5% of the answer
  guesses: st.guesses.map(g => g.guess),
  // the share screen's rows: direction, then red/yellow for far/near
  rows: st.guesses.map(g => (arrows[g.direction] ?? "") + (colors[g.closeness] ?? "")),
  product: window.productName ?? document.getElementById("product-info")?.textContent?.trim() ?? null,
};
