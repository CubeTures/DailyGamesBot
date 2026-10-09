// Puzzmo has no result in storage: the gameplay lives on its server. When the
// completion screen shows, after finishing and on every revisit of a finished
// puzzle, the page POSTs api.puzzmo.com/graphql?useCompletionDataV2Query,
// which answers (trimmed):
//   {"data": {"gamePlay": {"slug": "hrm971rcn", "pointsAwarded": 4724,
//     "elapsedTimeSecs": 432, "completedAt": "2026-10-08T22:04:31.556Z",
//     "boardState": "v0/;;;;/11111/SLIPE,SLIP;WRAP;DRESS;POWER,PARTY;CODE/261003,263213;362936;347026;397985,432027;298418/;;339192;393735,425503,429393;/0",
//     "puzzle": {"dailyTitle": "Oct 8, 2026",
//       "mostRecentDaily": {"daily": {"dateKey": "2026-10-08", "isToday": true, "seriesNumber": 1089}}}}}}
// Circuits can't be lost: every game ends with the board solved, and only the
// score differs: points up to the puzzle's cap (5500 today), less for time,
// wrong submits and Bolts.
// Archive puzzles have an older daily, so isToday leaves them out.
const gp = res?.json?.data?.gamePlay;
const daily = gp?.puzzle?.mostRecentDaily?.daily;

// boardState is "/"-separated; sections 3-5 hold one ";"-separated entry per
// box, in board order:
//   [3] the words submitted in that box, ","-separated, the last one right
//   [4] the time (ms) of each of those submits
//   [5] the time (ms) of each Bolt (reveal) used on that box
// The game's own "hints" deed (4 here) is the count of [5]'s times, and its
// Submits stat (7) the count of [3]'s words.
const sections = (gp?.boardState ?? "").split("/");
const perBox = s => (sections[s] ?? "").split(";").map(x => (x ? x.split(",") : []));
const submits = perBox(3);
const bolts = perBox(5);

const finished = !!gp?.completedAt && daily?.isToday === true && submits.length > 0;
