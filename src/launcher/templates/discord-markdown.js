// Renders announcement text as Discord would show it, for the result dialog.
var discordMarkdown = (function () {
  // Discord shortcodes the announcement templates use; any others show as
  // typed.
  var SHORTCODES = {
    sun_with_face: "🌞", green_square: "🟩", yellow_square: "🟨", white_large_square: "⬜",
    black_large_square: "⬛", purple_square: "🟪", blue_square: "🟦",
    orange_square: "🟧", red_square: "🟥", brown_square: "🟫",
    green_circle: "🟢", yellow_circle: "🟡", red_circle: "🔴", white_circle: "⚪",
    black_circle: "⚫", blue_circle: "🔵", purple_circle: "🟣", orange_circle: "🟠",
    white_check_mark: "✅", x: "❌", trophy: "🏆", first_place: "🥇",
    second_place: "🥈", third_place: "🥉", fire: "🔥", star: "⭐", tada: "🎉",
    stopwatch: "⏱️", clock: "🕐", brain: "🧠", bulb: "💡", skull: "💀", sparkles: "✨",
    game_die: "🎲", puzzle_piece: "🧩", thinking: "🤔", heart: "❤️",
    green_heart: "💚", blue_heart: "💙", purple_heart: "💜", orange_heart: "🧡",
    broken_heart: "💔", face_with_head_bandage: "🤕",
    shrimp: "🦐", fish: "🐟", bubbles: "🫧", squid: "🦑", clown: "🤡",
    izakaya_lantern: "🏮", star2: "🌟", arrow_up: "⬆️", arrow_down: "⬇️",
    dart: "🎯", eyes: "👀", ring_buoy: "🛟", camera_with_flash: "📸",
    earth_americas: "🌎", date: "📅",
    steam_locomotive: "🚂", house: "🏠", classical_building: "🏛️",
    police_officer: "👮", medal: "🏅", briefcase: "💼", crown: "👑",
    crystal_ball: "🔮", zap: "⚡",
    tulip: "🌷", cherry_blossom: "🌸", rose: "🌹", hibiscus: "🌺", sunflower: "🌻",
    blossom: "🌼", rosette: "🏵️", white_flower: "💮", bouquet: "💐",
    straight_ruler: "📏"
  };

  var HTML_ESCAPES = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };

  function escapeHtml(text) {
    return text.replace(/[&<>"']/g, function (c) { return HTML_ESCAPES[c]; });
  }

  function mentionHtml(name) {
    return '<span class="mention">@' + escapeHtml(name) + "</span>";
  }

  // Only the subset announcements use: user and role mentions, shortcodes,
  // `code`, **bold**, __underline__, *italic*/_italic_, ~~strike~~,
  // ||spoilers|| and backslash escapes. A spoiler is a button-like span
  // that reveals its inner span when clicked (see app.js).
  function toHtml(text, nameForId, nameForRole) {
    // Escaped characters are set aside so no rule below matches them.
    var escaped = [];
    text = text.replace(/\\([^\w\s])/g, function (_, c) {
      escaped.push(c);
      return "\uE000" + (escaped.length - 1) + "\uE001";
    });
    return escapeHtml(text)
      .replace(/&lt;@!?(\d+)&gt;/g, function (_, id) {
        return mentionHtml(nameForId(id));
      })
      .replace(/&lt;@&amp;([\w-]+)&gt;/g, function (_, role) {
        return mentionHtml(nameForRole(role));
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
      .replace(/~~([^~\n]+)~~/g, "<s>$1</s>")
      .replace(/\|\|([\s\S]+?)\|\|/g,
        '<span class="spoiler" role="button" tabindex="0" title="Reveal spoiler"><span>$1</span></span>')
      .replace(/\uE000(\d+)\uE001/g, function (_, i) { return escapeHtml(escaped[+i]); });
  }

  return { toHtml: toHtml };
})();
