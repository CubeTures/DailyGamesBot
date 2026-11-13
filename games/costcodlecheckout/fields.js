const totalCents = rounds.reduce((sum, r) => sum + r.diffCents, 0);

// A product's row, by how far off the guess was as Classic colours it:
// within 5% of the price, within 25%, or further.
const row = r => {
  const pct = r.actualCents ? r.diffCents / r.actualCents : Infinity;
  return pct <= 0.05 ? ":white_check_mark:" : pct <= 0.25 ? ":yellow_square:" : ":red_square:";
};

export default {
  puzzle_id: String(st.gameNumber - 1147),
  // Checkout's own number, as in its share text ("Costcodle Checkout #2")
  puzzle_number: st.gameNumber - 1147,
  // The game's headline: total dollars off across the five products, lowest
  // first. 0 is perfect, a good game is under $15, a bad one over $150.
  score: totalCents / 100,
  total_cents: totalCents,
  // The receipt's band for the total, e.g. "Gold star member"
  rating: ratings.find(([max]) => totalCents <= max)[1],
  // Each product: its short name, the guess and the price (cents), and how far off
  items: rounds.map(r => ({
    name: r.short || r.name || null,
    guess_cents: r.guessCents,
    price_cents: r.actualCents,
    off_cents: r.diffCents,
  })),
  rows: rounds.map(row),
};
