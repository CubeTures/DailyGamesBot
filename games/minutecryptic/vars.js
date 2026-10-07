// The daily puzzle's onGameEnd writes mc-daily-solves-2[<date>] =
// {ds, h: helpUsed ("HINT"/"LETTER" per use), st: startedAt, ct: completedAt}.
// It runs both when solved and when every letter has been revealed (the game's
// "gave_up" result), and nothing writes it mid-game. Archive puzzles key on
// their own date, so looking up today() ignores them.
const d = today();
const s = ls("mc-daily-solves-2")?.[d];

// mc-puzzle holds the daily puzzle's state, including the par the game scores
// against.
const p = (() => { const p = ls("mc-puzzle"); return p?.date === d ? p : null; })();

// Same as the game's own score: puzzles from 2025-09-22 on use averagePar.
const par = p?.parDetails?.averagePar ?? p?.par;
