// NYT keeps game state in localStorage under games-state-connections/<user>
// ("ANON" when logged out), rewritten after every guess:
//   {"states": [{"puzzleId": "1320", "printDate": "2026-10-07",
//     "data": {"puzzleComplete": true, "puzzleWon": true, "mistakes": 0,
//              "guesses": [{"cards": [{"position": 5, "level": 0}, ...], "correct": true}, ...],
//              "solvedCategories": [{"cards": [...], "level": 0, "orderSolved": 1}, ...],
//              "isPlayingArchive": false}}]}
// level is the card's group: 0 yellow, 1 green, 2 blue, 3 purple. puzzleId is
// NYT's internal id, not the "No." shown on the page. puzzleComplete flips to
// true on the last guess, for a win or a loss (4 mistakes, puzzleWon false,
// solvedCategories holding only the groups found before then).
const st = (() => {
  const key = Object.keys(localStorage).find(k => k.startsWith("games-state-connections/"));
  return ls(key)?.states?.find(s => s.printDate && s.data && !s.data.isPlayingArchive);
})();

// One emoji row per guess, coloured by each card's group: the game's share grid.
const rows = (() => {
  const emoji = [":yellow_square:", ":green_square:", ":blue_square:", ":purple_square:"];
  return (st?.data?.guesses ?? []).map(g => g.cards.map(c => emoji[c.level] ?? ":white_large_square:").join(""));
})();

const finished = !!st?.data?.puzzleComplete;
