// Costcodle keeps the day's game in localStorage "state", rewritten after
// every guess:
//   {"gameNumber": 1114, "hasWon": false,
//    "guesses": [{"guess": "24.99", "closeness": "guess-far", "direction": "&uarr;"},
//                {"guess": "39.99", "closeness": "guess-win", "direction": "&check;"}]}
// closeness is guess-far (over 25% off), guess-near (within 25%) or guess-win
// (within 5%); direction is &uarr; (go higher), &darr; (go lower) or &check;.
// A loss is six guesses without hasWon. There's no archive or practice mode.
const st = ls("state");

// The game number, worked out as the game does (main.js getGameNumber()):
// days since the 2023-09-21 launch, by the player's local clock. The page only
// resets "state" once its games.json has loaded, so until then a finished
// game from an earlier day is still there; this keeps it from firing.
const gameNumber = Math.ceil((Date.now() - new Date("09/21/2023").getTime()) / 864e5) + 1;

const finished = st?.gameNumber === gameNumber
  && Array.isArray(st.guesses)
  && (st.hasWon === true || st.guesses.length >= 6);
