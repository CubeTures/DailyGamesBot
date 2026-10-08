// The game runs in a same-origin iframe (/games-embed/bracket-city/) inside
// The Atlantic's page (/games/bracket-city/). Both frames get this script and
// share localStorage, so only check from the game's frame to report once.
const inGame = location.pathname.startsWith("/games-embed/");

// The game's "today" is the New York date; archive puzzles are stored under
// their own date, so looking only at today's key ignores them.
const d = new Intl.DateTimeFormat("en-CA", { timeZone: "America/New_York" }).format(new Date());

// bracketPuzzle_<YYYY-MM-DD>, rewritten on every move, e.g. when finished:
// {displayState: "<mark class=\"solved\">Ray</mark>theon patents the microwave",
//  solvedExpressions: ["compass RIGHT", ...],   clues solved, by the player or revealed
//  totalKeystrokes: 121, minimumKeystrokes: 41,
//  peekedClues: [...5],      clues whose first letter was shown (5 points each)
//  megaPeekedClues: [...5],  clues whose answer was revealed (15 points each)
//  wrongGuesses: 17, wrongGuessList: ["tear", ...],  2 points each
//  isComplete: true, progress: "complete",   "notStarted"/"inProgress" before
//  solvedOnPubDate: true, puzzleDate: "2026-10-08", ...}
// There is no losing: a stuck player reveals answers and scores down to 0.
const st = inGame ? ls("bracketPuzzle_" + d) : null;

// "submit" (default) or "classic" (hard mode: scored on keystrokes instead of
// wrong guesses). Only changeable before a puzzle is started.
const mode = ls("bracketCityInputMode") === "classic" ? "classic" : "submit";

const finished = !!st && st.isComplete === true && st.puzzleDate === d;

// The game's own scoring (Z0/WE in its bundle). Every peek costs 5 and every
// reveal 15, even of a clue peeked first; a wrong guess costs 2, except in
// classic mode, which starts from keystroke efficiency instead of 100.
const peeks = st?.peekedClues?.length ?? 0;
const reveals = st?.megaPeekedClues?.length ?? 0;
const efficiency = st?.totalKeystrokes > 0 ? (st.minimumKeystrokes / st.totalKeystrokes) * 100 : 100;
const score = Math.min(100, Math.max(0,
  (mode === "classic" ? efficiency : 100 - 2 * (st?.wrongGuesses ?? 0)) - 5 * peeks - 15 * reveals));
const rank = efficiency === 100 && peeks === 0 && reveals === 0 && !st?.wrongGuesses ? "Puppet Master"
  : (mode === "classic"
    ? [["Kingmaker", 91], ["Power Broker", 79], ["Mayor", 68], ["Chief of Police", 51], ["Council Member", 31], ["Resident", 21], ["Commuter", 11]]
    : [["Kingmaker", 100], ["Power Broker", 90], ["Mayor", 80], ["Chief of Police", 65], ["Council Member", 45], ["Resident", 20], ["Commuter", 10]]
  ).find(([, min]) => score >= min)?.[0] ?? "Tourist";
