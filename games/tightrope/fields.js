export default {
  puzzle_id: String(game.id),
  puzzle_number: game.id,
  won: !!st.hasWon,
  // The game's own total, higher is better: 100 per right answer, 10 per
  // second left on its 15s timer when answering right, and (only when the
  // rope is crossed) a difficulty bonus of 200 (Monday) to 320 (Sunday). A
  // perfect quick run is around 2,400, a typical win 1,700-2,200, a loss
  // whatever it had banked before the fall (e.g. 470).
  score: total,
  answer_points: answerPoints,
  time_bonus: timeBonus,
  difficulty_bonus: difficultyBonus,
  correct: st.responsePoints.filter(p => p > 0).length,
  // wrong picks and timeouts; three is a fall
  wrong: st.responsePoints.filter(p => !(p > 0)).length,
  // the game's rank for a win ("Clever Funambulist!"); null for a loss
  rank: rank,
  bar: bar,
};
