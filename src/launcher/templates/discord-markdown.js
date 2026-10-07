// Renders announcement text as Discord would show it, for the result dialog.
var discordMarkdown = (function () {
  // Discord shortcodes the announcement templates use; any others show as
  // typed.
  var SHORTCODES = {
    bee: "🐝", green_square: "🟩", yellow_square: "🟨", white_large_square: "⬜",
    black_large_square: "⬛", purple_square: "🟪", blue_square: "🟦",
    orange_square: "🟧", red_square: "🟥", brown_square: "🟫",
    green_circle: "🟢", yellow_circle: "🟡", red_circle: "🔴", white_circle: "⚪",
    black_circle: "⚫", blue_circle: "🔵", purple_circle: "🟣", orange_circle: "🟠",
    white_check_mark: "✅", x: "❌", trophy: "🏆", first_place: "🥇",
    second_place: "🥈", third_place: "🥉", fire: "🔥", star: "⭐", tada: "🎉",
    stopwatch: "⏱️", clock: "🕐", brain: "🧠", bulb: "💡", skull: "💀",
    game_die: "🎲", puzzle_piece: "🧩", thinking: "🤔", heart: "❤️",
    shrimp: "🦐", fish: "🐟", bubbles: "🫧", squid: "🦑", clown: "🤡",
    izakaya_lantern: "🏮", star2: "🌟", arrow_up: "⬆️", arrow_down: "⬇️",
    dart: "🎯"
  };

  var HTML_ESCAPES = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };

  function escapeHtml(text) {
    return text.replace(/[&<>"']/g, function (c) { return HTML_ESCAPES[c]; });
  }

  // Only the subset announcements use: mentions, shortcodes, `code`,
  // **bold**, __underline__, *italic*/_italic_ and ~~strike~~.
  function toHtml(text, nameForId) {
    return escapeHtml(text)
      .replace(/&lt;@!?(\d+)&gt;/g, function (_, id) {
        return '<span class="mention">@' + escapeHtml(nameForId(id)) + "</span>";
      })
      .replace(/:([a-z0-9_+-]+):/g, function (match, code) {
        return SHORTCODES[code] || match;
      })
      .replace(/`([^`\n]+)`/g, "<code>$1</code>")
      .replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>")
      .replace(/__([^_\n]+)__/g, "<u>$1</u>")
      .replace(/\*([^*\n]+)\*|\b_([^_\n]+)_\b/g, function (_, starred, underscored) {
        return "<em>" + (starred || underscored) + "</em>";
      })
      .replace(/~~([^~\n]+)~~/g, "<s>$1</s>");
  }

  return { toHtml: toHtml };
})();
