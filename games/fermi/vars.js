// Fermi saves each puzzle's guesses in localStorage under fermi:puzzle:<no>,
// rewritten after each of the three questions:
//   {"guesses": [1200, 300, 1000000000],
//    "questionIds": ["q494", "q499", "q405"], "mode": "daily"}
// Unanswered questions are null. There's no losing: three guesses always end
// in a score. Answers and scoring only live in the game's JS bundle, so the
// factors and score are read off the results screen below.
//
// The header shows today's number ("No. 073"). Archive puzzles are played at
// /?d=<date> and stored with mode "archive", but a past daily replayed from
// the archive keeps mode "daily", so the URL is checked too.
const no = parseInt(texts(".label").map(t => t.match(/^No\.\s*(\d+)$/)?.[1]).find(Boolean) ?? "", 10);
const st = no ? ls(`fermi:puzzle:${no}`) : null;
const daily = st?.mode === "daily" && !new URLSearchParams(location.search).has("d");
const complete = st?.guesses?.length === 3 && st.guesses.every(g => g != null);

// Results screen: one .q-row per question, each with a .q-factor like
// "> 2.18×", where the sign's aria-label says "You guessed too high/low".
// Factors are shown rounded (2 decimals under 10×, 1 under 100×, whole above).
const num = (s) => parseFloat(s?.replace(/[^\d.]/g, "") ?? "");
const factors = [...document.querySelectorAll(".q-row .q-factor")].map(f => ({
  text: f.textContent.replace(/[<>]/g, "").trim(),
  value: num(f.textContent),
  side: /too high/.test(f.querySelector("[aria-label]")?.getAttribute("aria-label") ?? "") ? "high"
    : /too low/.test(f.querySelector("[aria-label]")?.getAttribute("aria-label") ?? "") ? "low" : "exact",
}));
const scoreText = text(".grid .left .score")?.trim();

// "Top N%" arrives from the server a moment after the score renders. Wait up
// to 5s for it so it's captured, but don't let a failed fetch block the result.
const topText = text(".grid .left .pill");
const resultsShown = factors.length === 3 && factors.every(f => f.value > 0) && !!scoreText;
if (resultsShown) window.__dgbFermiSeen ??= Date.now();
const finished = daily && complete && resultsShown
  && (/Top \d+%/.test(topText ?? "") || Date.now() - window.__dgbFermiSeen > 5000);
