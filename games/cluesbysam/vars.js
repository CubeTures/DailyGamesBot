// The daily puzzle (served at "/", one per New York date) keeps its state in
// localStorage "state-<YYYY-MM-DD>", rewritten after every guess:
//   {"flippedCards": [19, 17, 14, ...],          card indices revealed so far
//    "imperfections": [{"index": 17, "type": "error"},
//                      {"index": 6, "type": "hint"},
//                      {"index": 12, "type": "second-hint"}, ...],
//    "attemptCount": 34, "elapsedTime": 570820, "completeTime": 570820, ...}
// Cards are numbered row by row (A1, B1, C1, D1, A2, ...). completeTime is 0
// until every card is flipped, then the solve time in ms. There's no losing:
// a wrong guess ("error") or a hint just marks that card imperfect.
// Earlier puzzles of the week are played at /s/play?puzzleId=..., which this
// ignores by path.

// The page's puzzle date, taken on the first check (at page load), so a
// puzzle started before New York midnight and finished after keeps its day.
const day = (window.__dgbCbsDay ??= new Intl.DateTimeFormat("en-CA", {
  timeZone: "America/New_York", year: "numeric", month: "2-digit", day: "2-digit",
}).format(new Date()));
const st = location.pathname === "/" ? ls(`state-${day}`) : null;

// Grid width from the board's coordinate labels (A1..D5 is 4 wide).
const width = new Set(texts(".card .coord").map(c => c.replace(/\d+$/, ""))).size;
const cardCount = document.querySelectorAll(".card").length;

const finished = !!st && st.completeTime > 0 && width > 0;

// The share grid, as the game builds it: each card shows its worst
// imperfection (second-hint, then hint, then error), else green.
const TILE = { "second-hint": ":orange_circle:", hint: ":yellow_circle:", error: ":yellow_square:" };
const tileFor = i => {
  const types = (st?.imperfections ?? []).filter(m => m.index === i).map(m => m.type);
  const worst = ["second-hint", "hint", "error"].find(t => types.includes(t));
  return worst ? TILE[worst] : ":green_square:";
};
const rows = width > 0
  ? [...Array(Math.ceil(cardCount / width)).keys()].map(r =>
      [...Array(width).keys()].map(c => tileFor(r * width + c)).join(""))
  : [];

const countOf = type => (st?.imperfections ?? []).filter(m => m.type === type).length;

// "Daily Clues by Sam: Oct 8th 2026 (Tricky)" under the board.
const difficulty = [...document.querySelectorAll("p")]
  .map(p => p.textContent.match(/^Daily Clues by Sam:.*\((\w+)\)/)?.[1])
  .find(Boolean) ?? null;
