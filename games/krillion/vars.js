// Finishing the daily dive (all 7 rounds) runs recordFinishedDay, which writes
// the day into krillion:stats:v1 in one go and deletes the in-progress
// krillion:game:v1. Nothing writes the history mid-dive:
//   {"history": {"2026-10-07": {"dayNumber": 84, "score": 230,
//     "tiers": ["schooler", "plankton", "rare", ..., "miss"],
//     "results": [{"promptText": "Name a dating app", "answer": "Grindr",
//                  "tier": "schooler", "score": 30}, ...]}},
//    "gamesPlayed": 1, "currentStreak": 1, "lastPlayedDate": "2026-10-07", ...}
// There's no losing: every dive ends with a score out of 700, and a round with
// no accepted answer is tier "miss" (0 points). Archive days and themed packs
// are saved under other keys, so this history only holds daily dives. The key
// gets an owner prefix when signed in, hence the endsWith.
const stats = ls(Object.keys(localStorage).find(k => k.endsWith("krillion:stats:v1")));

// The daily puzzle turns over at midnight America/New_York (the game's
// etDateString), and the history is keyed on that date.
const date = new Intl.DateTimeFormat("en-CA", { timeZone: "America/New_York" }).format(new Date());
const day = stats?.history?.[date];

// The game's TIERS, deepest last: each round's share-text emoji.
const tierEmoji = {
  plankton: ["🫧", ":bubbles:"],
  tooclever: ["🤡", ":clown:"],
  schooler: ["🐟", ":fish:"],
  rare: ["🦑", ":squid:"],
  deepcut: ["🏮", ":izakaya_lantern:"],
  krillion: ["🌟", ":star2:"],
  miss: ["⬛", ":black_large_square:"],
};

// The results screen's "bearing" bands for the day's score.
const band = (s) => s >= 450 ? "One in a krillion" : s >= 351 ? "Deep cut"
  : s >= 251 ? "Rare" : s >= 151 ? "Schooler" : "Plankton";
