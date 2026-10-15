// While playing, TimeGuessr keeps the game in localStorage tg_progress_daily.
// After the fifth round it removes that and writes the whole result to
// sessionStorage tg_final_score, then goes to /final-score, which reads it:
//   {"mode": "daily", "dailyNumber": "1232", "archive": null, "score": 25433,
//    "playArray": [{"Year": "2018", "Location": {...}, ...}, ...],
//    "roundResults": [{"guessYear": 2006, "actualYear": 2018,
//      "distanceMeters": 681352, "distanceScoreValue": 3819,
//      "yearScoreValue": 2000, "totalScore": 5819, ...}, ...],
//    "roundDurations": [212087, 24649, 36762, 12609, 22188]}
// Each round scores up to 5,000 for the place and 5,000 for the year, so a
// game is out of 50,000. There's no losing; every game ends with a score.
// Other modes (random games, community games) write mode "game"/etc. and no
// dailyNumber; past dailies carry `archive`.
const st = (() => {
  const s = ss("tg_final_score");
  return s?.mode === "daily" && s.dailyNumber && !s.archive ? s : null;
})();

const finished = !!st && st.roundResults?.length === 5 && typeof st.score === "number";

// The game's share text has a row per round: 🌎 then three squares for how
// close the pin was, 📅 then three for how close the year was. Same cut-offs
// as the game's own.
const G = ":green_square:", Y = ":yellow_square:", B = ":black_large_square:";
function placeBar(r) {
  const d = r.distanceMeters;
  if (r.noGuess || (d === 0 && r.distanceScoreValue === 0)) return B + B + B;
  return d <= 50 ? G + G + G : d < 37500 ? G + G + Y : d < 1e5 ? G + G + B
    : d < 2.5e5 ? G + Y + B : d < 1e6 ? G + B + B : d < 2e6 ? Y + B + B : B + B + B;
}
function yearBar(r) {
  const t = Math.abs(r.guessYear - r.actualYear);
  return t === 0 ? G + G + G : t <= 2 ? G + G + Y : t <= 4 ? G + G + B : t <= 7 ? G + Y + B
    : t <= 15 ? G + B + B : t <= 20 ? Y + B + B : B + B + B;
}
