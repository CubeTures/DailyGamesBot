// Cross with Friends has no daily puzzle: players pick any puzzle, which
// starts a shared game (/beta/game/<gid>) that others join by its URL. Its
// state lives on the server and comes over a socket, so nothing useful is
// in storage. On solving, every player's page POSTs
// /api/record_solve/<pid> (pid: the puzzle) with the shared game's final
// state, trimmed:
//
//   {gid: "103379552-blen", time_to_solve: 64639, player_count: 2,
//    dfacId: "7c202179-…",            // this browser's player
//    snapshot: {
//      grid: [[{black: true}, {value: "B", user_id: "3b8d9e9d-…",
//               good: true, revealed: false}, …], …],
//      users: {"7c202179-…": {displayName: "Taxing Raven", color: "…"},
//              "3b8d9e9d-…": {displayName: "Stunning Marten", …}},
//      clock: {totalTime: 64639, paused: true}}}
//
// The player's dfac-id is also in localStorage under "dfac-id", which the
// start trigger reports before there's any solve. time_to_solve is the
// site's clock, in ms. A cell's user_id is whoever
// last filled it; a reveal clears it unless the letter was already right,
// so revealed squares count for nobody. There's no losing: a game is
// either solved or abandoned (and then never reported).

const solve = req?.json;
const cells = (solve?.snapshot?.grid ?? [])
  .flat()
  .filter(c => c && !c.black && !c.isImage);
const solved = !!solve?.gid && cells.length > 0;

// Squares each player filled, by their id.
const squaresBy = {};
cells.forEach(c => { if (c.user_id) squaresBy[c.user_id] = (squaresBy[c.user_id] ?? 0) + 1; });
// Everyone in the game, plus anyone who filled a square but left the list.
const users = solve?.snapshot?.users ?? {};
const playerIds = [...new Set([...Object.keys(users), ...Object.keys(squaresBy)])];

// The shared game, from the solve or else the page's URL.
const gid = solve?.gid ?? location.pathname.match(/\/game\/([^/?#]+)/)?.[1];
const title = document.title.replace(/\s*-\s*Cross with Friends$/, "").trim() || null;

// Start trigger, which also tells the proxy who this player is in the game:
// on a shared game that isn't solved (the clock gets .clock--solved once it
// is), the player has typed and a square has a letter. Others' pages see
// the letters too but not the typing.
const started = !!gid && /\/game\//.test(location.pathname) && typed()
  && exists(".clock") && !exists(".clock--solved")
  && texts(".cell--value").some(v => v);
