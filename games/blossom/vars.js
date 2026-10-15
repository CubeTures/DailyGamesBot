// Everything lives in localStorage "gameData-blossom-word-game":
//   puzzleCache[<date>] = {Center: "R", Letters: "DENTUW", Pangram: "UNDERWENT",
//     GameId: 1697, PuzzleId: "R-DENTUW", Words: [...]}
//     today's puzzle and a few around it, keyed by the player's local date in
//     en-US form ("10/15/2026", the game's dateKey).
//   puzzleStates[<date>] = [{score: 195, bonusIdx: 2,
//     words: ["TURN", "TURD", ..., "UNDERDREW"],
//     points_per_word: [2, 7, ..., 23], flowers: [...], rndState: "..."}]
//     one entry per attempt; replaying a puzzle pushes another. The game
//     saves after every word, adding to `words`, `points_per_word` and `score`
//     together, and the puzzle is over at 12 words (its isPuzzleStateSolved).
// There's no losing: every game ends after 12 words with a score. Archive
// puzzles are stored under their own date, so looking up today's ignores them.
const key = new Date().toLocaleDateString("en-US");
const data = ls("gameData-blossom-word-game");
const puz = data?.puzzleCache?.[key];
// The first attempt is the one that counts; later ones are replays.
const st = data?.puzzleStates?.[key]?.[0];

const finished = !!puz && st?.words?.length === 12 && st?.points_per_word?.length === 12;

// The game's own pangram test: 7+ letters using all 7 distinct letters.
const isPangram = w => w.length >= 7 && new Set(w).size === 7;

// The share text ends with one flower per letter of the longest word, in
// shuffled order; here rotated by the puzzle number so it's stable.
const FLOWERS = [":tulip:", ":cherry_blossom:", ":rose:", ":hibiscus:", ":sunflower:",
  ":blossom:", ":rosette:", ":white_flower:", ":bouquet:"];
const longest = Math.max(0, ...(st?.words ?? []).map(w => w.length));
const flowers = Array.from({ length: longest },
  (_, i) => FLOWERS[((puz?.GameId ?? 0) + i) % FLOWERS.length]).join("");
