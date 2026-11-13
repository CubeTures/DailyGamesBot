// Checkout keeps the game it's showing in localStorage "checkoutState",
// rewritten after every product (scripts/checkout/storage.js):
//   {"version": 1, "gameNumber": 1149, "productIds": [1155, ..., 1159],
//    "phase": "complete", "completedAt": "2026-11-12T18:03:11.000Z",
//    "totalCents": 1234, "rating": "GOLD STAR MEMBER",
//    "rounds": [{"productId": 1155, "name": "Kirkland Signature ...",
//                "short": "Kirkland Coffee", "image": "...",
//                "guessCents": 1999, "actualCents": 2199, "diffCents": 200}, ...]}
// phase is "guessing", "awaitingNext" (a price shown, before Next) or
// "complete" once the fifth product is priced; totalCents is the sum of the
// rounds' diffCents, set in the same write. There's no losing: every game
// ends after five products. gameNumber counts days like Classic's, so
// Checkout's own number (the share text's #N) is it minus 1147.
// The archive loads an old game into this same key, so it's excluded by
// gameNumber. Classic, the site's other mode, is games/costcodle, on a
// subdomain of its own.
const st = ls("checkoutState");

// Today's game number, worked out as the game does (daily.js getGameNumber()):
// days since 2023-09-21 by the player's local calendar, plus 2.
const now = new Date();
const todayNumber = Math.floor(
  (Date.UTC(now.getFullYear(), now.getMonth(), now.getDate()) - Date.UTC(2023, 8, 21)) / 864e5
) + 2;

const rounds = Array.isArray(st?.rounds) ? st.rounds : [];

const finished = st?.gameNumber === todayNumber
  && st.phase === "complete"
  && rounds.length === 5
  && rounds.every(r => Number.isFinite(r?.diffCents));

// The game's own rating for a total (ratings.js), as it shows on the receipt.
const ratings = [
  [500, "Executive member"],
  [1500, "Gold star member"],
  [3000, "Bulk buyer"],
  [6000, "Free sample hunter"],
  [15000, "Lost in aisle 12"],
  [Infinity, "Forgot your card"],
];
