// localStorage "daily-orbs-profile:<browserId>:daily-orbs-<dateKey>" holds a
// day's progress, rewritten after every answer. <browserId> is the active
// profile's, from "daily-orbs-profile-registry-v1"; before profiles the key
// was plain "daily-orbs-<dateKey>". Trimmed, from a won run:
//   {dateKey: "2026-10-08",
//    puzzles: [{puzzleId: "just-dance-ii", color: "green", orbs: 3,
//               livesLeft: 1, completed: true, gameOver: false, gaveUp: false}, ...],
//    eventHistory: [{type: "heart", color: "green"}, {type: "orb", color: "green"},
//                   ..., {type: "complete", color: "green"}, ...]}
// eventHistory is the day in order: "orb" per orb earned, "heart" per heart
// lost, "complete"/"give-up" when a puzzle ends. Archive days are kept under
// their own date, so only today's game day is looked at.
//
// The game decides the day's outcome from eventHistory (its `ps()`), and we
// mirror it:
//   - "won" at the 6th orb, whatever is left unplayed
//   - "done" (lost) once all 4 puzzles are closed (3 hearts lost, completed or
//     given up) with fewer than 6 orbs; the game shows no banner for this
// Anything after that point (more orbs once the day is won) is left out, as
// the game's own share text does.

// The game day changes at midnight Hawaii-Aleutian time, the same as [reset]
// (en-CA formats a date as YYYY-MM-DD).
const day = new Intl.DateTimeFormat("en-CA", { timeZone: "America/Adak" }).format(new Date());
const profile = ls("daily-orbs-profile-registry-v1")?.activeBrowserId;
const st = (() => {
  const s = (profile && ls(`daily-orbs-profile:${profile}:daily-orbs-${day}`)) ?? ls(`daily-orbs-${day}`);
  return s?.dateKey === day ? s : null;
})();

const outcome = (() => {
  const events = st?.eventHistory ?? [];
  let orbs = 0;
  const hearts = {};
  const closed = new Set();
  for (let i = 0; i < events.length; i++) {
    const e = events[i];
    if (e.type === "orb") {
      if (++orbs >= 6) return { won: true, events: events.slice(0, i + 1) };
      continue;
    }
    if (e.type === "heart") {
      hearts[e.color] = (hearts[e.color] ?? 0) + 1;
      if (hearts[e.color] < 3) continue;
    } else if (e.type !== "complete" && e.type !== "give-up") {
      continue;
    }
    closed.add(e.color);
    if (closed.size >= 4) return { won: false, events: events.slice(0, i + 1) };
  }
  return null;
})();

const finished = !!outcome;
