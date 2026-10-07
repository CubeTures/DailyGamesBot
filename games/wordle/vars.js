// NYT keeps game state in localStorage under games-state-wordleV2/<user>
// ("ANON" when logged out), rewritten after every guess:
//   {"states": [{"puzzleId": "985", "printDate": "2026-10-06",
//     "data": {"boardState": ["crane", "pluto", "dimly", "", "", ""],
//              "currentRowIndex": 3, "status": "WIN", "hardMode": false,
//              "isPlayingArchive": false}}]}
// status is IN_PROGRESS while playing. A loss is caught by all six rows being
// used, whatever NYT names that status.
const st = (() => {
  const key = Object.keys(localStorage).find(k => k.startsWith("games-state-wordleV2/"));
  return ls(key)?.states?.find(s => s.printDate && s.data && !s.data.isPlayingArchive);
})();

// The state holds no answer and no tile colors; those are only on the board,
// where each row is <div role="group" aria-label="Row 1"> and each tile has
// data-state empty/tbd while unrevealed, then correct/present/absent as it
// flips. These are the fully flipped rows, as Wordle's share-text emoji.
const rows = (() => {
  const emoji = { correct: ":green_square:", present: ":yellow_square:", absent: ":white_large_square:" };
  return [...document.querySelectorAll('[role="group"][aria-label^="Row "]')]
    .map(r => [...r.querySelectorAll("[data-state]")].map(t => emoji[t.dataset.state]))
    .filter(tiles => tiles.length === 5 && tiles.every(Boolean))
    .map(tiles => tiles.join(""));
})();

// Won or out of rows, and every used row has flipped (so `rows` is complete).
const finished = !!st
  && (st.data.status === "WIN" || (st.data.status !== "IN_PROGRESS" && st.data.currentRowIndex >= 6))
  && rows.length === st.data.currentRowIndex;
