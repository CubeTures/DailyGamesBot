// Which game day a puzzle belongs to, shared by the capture script
// (src/proxy/capture/runtime.js) and the launcher page. The Python twin is
// Reset.day_at in src/games/models.py.

// `date` as YYYY-MM-DD in the local timezone.
function isoDate(date) {
  function pad(n) { return (n < 10 ? "0" : "") + n; }
  return date.getFullYear() + "-" + pad(date.getMonth() + 1) + "-" + pad(date.getDate());
}

// The current game day as YYYY-MM-DD: the date, in reset.timezone (the
// player's own if null), of reset.minutes before now.
function gameDay(reset) {
  var shifted = new Date(Date.now() - reset.minutes * 60000);
  if (!reset.timezone) return isoDate(shifted);
  // en-CA formats dates as YYYY-MM-DD.
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: reset.timezone, year: "numeric", month: "2-digit", day: "2-digit",
  }).format(shifted);
}
