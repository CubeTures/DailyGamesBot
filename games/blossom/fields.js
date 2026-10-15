export default {
  puzzle_id: String(puz.GameId),
  puzzle_number: puz.GameId,
  // The game's own score: the sum of points_per_word. A word scores 2 (4
  // letters), 4 (5), 6 (6), 12 (7) or 12 + 3 per letter past 7, plus 5 per
  // use of the bonus letter and 7 for a pangram. Higher is better: twelve
  // 4-letter words make 24, a good game is around 150-250.
  score: st.score,
  words: st.words.length,
  pangrams: st.words.filter(isPangram).length,
  longest_word: longest,
  flowers: flowers,
  // The player's own words and what each scored, shown behind a spoiler.
  word_scores: st.words.map((w, i) => ({ word: w, points: st.points_per_word[i] })),
};
