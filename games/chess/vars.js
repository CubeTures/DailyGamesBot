// The daily puzzle keeps nothing in storage when logged out, and the server
// isn't told about the final, winning move (SubmitDailyPuzzleAction responses
// carry hearts and a move index, but no solved flag). A reload restarts the
// puzzle. So everything here comes from the sidebar of the puzzle page.

// The date picker reads "Oct 8, 2026". The URL has the date too, but only
// after browsing days (/daily/2026-10-07); plain /daily means today.
const day = (() => {
  const fromUrl = location.pathname.match(/^\/daily\/(\d{4}-\d{2}-\d{2})$/)?.[1];
  if (fromUrl) return fromUrl;
  const t = Date.parse(text(".game-mode-top-section-date-picker .cc-dropdown-button-label") ?? "");
  if (Number.isNaN(t)) return null;
  const d = new Date(t);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
})();

// "Next Day" is only disabled on the newest puzzle; archive days (the picker
// goes back a week) have it enabled, so they never count.
const isToday = !!document.querySelector('.game-mode-top-section-date-picker button[aria-label="Next Day"]')?.disabled;

// Five hearts; each wrong move turns one from daily-puzzle-hearts-filled to
// daily-puzzle-hearts-broken.
const hearts = document.querySelectorAll(".daily-puzzle-hearts-heart").length;
const heartsLeft = document.querySelectorAll(".daily-puzzle-hearts-heart.daily-puzzle-hearts-filled").length;

// Solved: the "Perfect!"/"Awesome!" success modal, or (once that's closed)
// the "Learn more from <author>" video card, which only appears on a solve.
// The coach bubble's check-mark icon isn't enough: it shows after every
// correct move.
const solved = exists(".daily-puzzle-success-modal-component") || exists(".video-prompt-component");

// Lost: every heart broken. The game then offers "Keep Going", but the first
// result saved is the one that counts.
const lost = hearts > 0 && heartsLeft === 0;

const finished = isToday && !!day && hearts > 0 && (solved || lost);
