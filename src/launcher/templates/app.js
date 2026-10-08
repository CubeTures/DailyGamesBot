(function () {
  var GAME_TITLES = JSON.parse(document.getElementById("game-titles").textContent);
  var RESETS = JSON.parse(document.getElementById("resets").textContent);
  var HIGHER_SCORE_WINS = JSON.parse(document.getElementById("higher-score-wins").textContent);
  var MEDALS = ["🥇", "🥈", "🥉"];
  var REFRESH_MS = 30000;
  // Rows a scoreboard card shows before the rest move to the full list.
  var BOARD_ROWS = 5;

  var discordId = rememberDiscordId();

  function rememberDiscordId() {
    var params = new URLSearchParams(location.search);
    var id = params.get("discord_id");
    if (id) {
      localStorage.setItem("discord_id", id);
      params.delete("discord_id");
      var query = params.toString();
      history.replaceState({}, "", location.pathname + (query ? "?" + query : "") + location.hash);
    } else {
      id = localStorage.getItem("discord_id");
    }
    if (id) {
      // Games run on other localhost ports, which can't read this page's
      // localStorage but do share its cookies; the proxy reads this one when
      // a game reports a result.
      document.cookie = "dgb_discord_id=" + encodeURIComponent(id) +
        "; path=/; max-age=31536000; SameSite=Lax";
    }
    return id;
  }

  function gameTitle(game) {
    return GAME_TITLES[game] || game;
  }

  function playerName(id, name) {
    return name || "Player …" + id.slice(-4);
  }

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function showMessage(container, text, loading) {
    container.textContent = "";
    container.appendChild(el("p", loading ? "empty loading" : "empty", text));
  }

  // Replays a one-off CSS animation class on an element that already exists.
  function replay(node, className) {
    node.classList.remove(className);
    void node.offsetWidth;
    node.classList.add(className);
  }

  // The game's card icon, reused at a smaller size.
  function smallIcon(game) {
    var cardIcon = document.querySelector('.card[data-game="' + game + '"] .icon');
    var icon = cardIcon ? cardIcon.cloneNode(true) : el("div", "icon mono", gameTitle(game).charAt(0));
    icon.classList.add("small");
    return icon;
  }

  function hasScore(data) {
    return typeof data.score === "number";
  }

  // Just the number: players know each game's scale, so no "/6".
  function formatScore(data) {
    return lost(data) || !hasScore(data) ? "–" : String(data.score);
  }

  function lost(data) {
    return data.won === false;
  }

  function hasTime(data) {
    return typeof data.time_secs === "number";
  }

  // Seconds as "1:05" or "1:02:03", like the announcements' `duration`.
  function formatTime(secs) {
    var total = Math.round(secs);
    var pad = function (n) { return (n < 10 ? "0" : "") + n; };
    var hours = Math.floor(total / 3600), minutes = Math.floor(total / 60) % 60;
    return (hours ? hours + ":" + pad(minutes) : String(minutes)) + ":" + pad(total % 60);
  }

  // Lower is better unless the game's config says `higher_score_wins`;
  // outright losses sort last, then no score. Ties go to the fastest time
  // (results without one after those with), then the earliest finish.
  function compareResults(a, b) {
    var aLost = lost(a.data), bLost = lost(b.data);
    if (aLost !== bLost) return aLost ? 1 : -1;
    var aScored = hasScore(a.data), bScored = hasScore(b.data);
    if (aScored !== bScored) return aScored ? -1 : 1;
    if (aScored && a.data.score !== b.data.score) {
      var diff = a.data.score - b.data.score;
      return HIGHER_SCORE_WINS.indexOf(a.game) >= 0 ? -diff : diff;
    }
    var aTimed = hasTime(a.data), bTimed = hasTime(b.data);
    if (aTimed !== bTimed) return aTimed ? -1 : 1;
    if (aTimed && a.data.time_secs !== b.data.time_secs) return a.data.time_secs - b.data.time_secs;
    return a.captured_at < b.captured_at ? -1 : 1;
  }

  function groupByGame(results) {
    var byGame = {};
    results.forEach(function (r) { (byGame[r.game] = byGame[r.game] || []).push(r); });
    return byGame;
  }

  // Results are filed by game day (when each game's puzzle changes), so a
  // game that resets in another timezone shows on the board of its puzzle's
  // date, which may be the viewer's tomorrow or yesterday.
  function fetchResults(day) {
    return fetch("/api/results?day=" + dayKey(day)).then(function (res) { return res.json(); });
  }

  var dialog = document.getElementById("dialog");
  var dialogHead = dialog.querySelector(".dialog-head");
  var dialogTitle = document.getElementById("dialog-title");
  var dialogBody = dialog.querySelector(".dialog-body");
  var backButton = dialog.querySelector(".back");
  var message = dialog.querySelector(".message");
  var fullBoard = dialog.querySelector(".ranks");
  var dialogBack = null;

  // Plays the closing animation (instant under reduced motion), then closes.
  function closeDialog() {
    if (dialog.open) dialog.classList.add("closing");
  }
  dialog.addEventListener("animationend", function (e) {
    if (e.target !== dialog || !dialog.classList.contains("closing")) return;
    dialog.classList.remove("closing");
    dialog.close();
  });
  dialog.addEventListener("cancel", function (e) {
    e.preventDefault();
    closeDialog();
  });
  dialog.querySelector(".close").addEventListener("click", closeDialog);
  backButton.addEventListener("click", function () { if (dialogBack) dialogBack(); });
  // A click on the backdrop lands on the dialog itself.
  dialog.addEventListener("click", function (e) {
    if (e.target === dialog) closeDialog();
  });

  // The dialog shows either an announcement or a game's full scoreboard;
  // `back`, if given, is what its back button returns to.
  function showDialog(game, title, showList, back) {
    var oldIcon = dialogHead.querySelector(".icon");
    if (oldIcon) oldIcon.remove();
    dialogHead.insertBefore(smallIcon(game), dialogTitle);
    dialogTitle.textContent = title;
    dialogBack = back || null;
    backButton.hidden = !back;
    message.hidden = showList;
    fullBoard.hidden = !showList;
    dialog.classList.remove("closing");
    if (!dialog.open) dialog.showModal();
    dialogBody.scrollTop = 0;
  }

  function showAnnouncement(result, namesById, back) {
    message.innerHTML = discordMarkdown.toHtml(
      result.announcement, function (id) { return playerName(id, namesById[id]); }, gameTitle);
    showDialog(result.game,
      gameTitle(result.game) + " · " + playerName(result.discord_id, result.name), false, back);
  }

  // Scrolls to `focusId`'s row and focuses it (coming back from their
  // announcement), or else just scrolls to the viewer's own row.
  function showFullBoard(game, ranked, namesById, focusId) {
    fullBoard.textContent = "";
    var target = null;
    ranked.forEach(function (result, rank) {
      var item = boardRow(result, rank, namesById, false, function () {
        showFullBoard(game, ranked, namesById, result.discord_id);
      });
      if (result.discord_id === (focusId || discordId)) target = item;
      fullBoard.appendChild(item);
    });
    showDialog(game, gameTitle(game) + " · " + playerCount(ranked.length), true);
    if (target) {
      target.scrollIntoView({ block: "center" });
      var row = target.querySelector(".row");
      if (focusId && row) row.focus({ preventScroll: true });
    }
  }

  var cardsRendered = false;
  function renderCards(byGame) {
    document.querySelectorAll(".card").forEach(function (card) {
      var mine = (byGame[card.dataset.game] || []).filter(function (r) {
        return r.discord_id === discordId;
      })[0];
      // Celebrate a result that arrives while the page is open.
      if (cardsRendered && mine && !card.classList.contains("done")) replay(card, "just-done");
      card.classList.toggle("done", !!mine);
      card.querySelector(".status").textContent =
        mine ? "✓ Done · " + formatScore(mine.data) : "Not played";
      card.querySelector(".play").textContent = mine ? "Open" : "Play";
    });
    cardsRendered = true;
  }

  // Keys ("game" and "game:discord_id") of what the scoreboard showed last,
  // or null after a day change so the next render animates in whole.
  var shownOnBoard = null;

  function playerCount(n) {
    return n + (n === 1 ? " player" : " players");
  }

  // Which ranks a card shows: everyone, or if that's too many the top
  // BOARD_ROWS, with the viewer's own row in place of the last if lower.
  // Cutting a single row would save nothing, so that never happens.
  function visibleRanks(ranked) {
    var all = ranked.map(function (_, rank) { return rank; });
    if (ranked.length <= BOARD_ROWS + 1) return all;
    var top = all.slice(0, BOARD_ROWS);
    var mine = ranked.findIndex(function (r) { return r.discord_id === discordId; });
    if (mine >= BOARD_ROWS) top[BOARD_ROWS - 1] = mine;
    return top;
  }

  // `back` is passed on to the announcement, for rows in the full list.
  function boardRow(result, rank, namesById, isNew, back) {
    var item = el("li", result.discord_id === discordId ? "me" : "");
    item.style.setProperty("--r", String(Math.min(rank, 10)));
    if (isNew) item.classList.add("fresh");
    var row = el(result.announcement ? "button" : "div", "row");
    if (result.announcement) {
      row.type = "button";
      row.title = "Show the Discord announcement";
      row.addEventListener("click", function () { showAnnouncement(result, namesById, back); });
    }
    var scored = hasScore(result.data) && !lost(result.data);
    var rankCell = lost(result.data) ? el("span", "rank medal", "💀")
      : rank < 3 && scored ? el("span", "rank medal", MEDALS[rank])
      : el("span", "rank", String(rank + 1));
    if (lost(result.data)) rankCell.title = "Lost";
    row.appendChild(rankCell);
    row.appendChild(el("span", "name", playerName(result.discord_id, result.name)));
    row.appendChild(el("span", scored ? "score" : "score lost", formatScore(result.data)));
    row.appendChild(el("span", "time", hasTime(result.data) ? formatTime(result.data.time_secs) : ""));
    item.appendChild(row);
    return item;
  }

  function board(game, results, namesById, shown, index) {
    var ranked = results.slice().sort(compareResults);
    var container = el("div", "board");
    var entering = !shownOnBoard || !shownOnBoard[game];
    if (entering) {
      container.classList.add("entering");
      container.style.setProperty("--i", String(index));
    }
    var head = el("div", "board-head");
    head.appendChild(smallIcon(game));
    head.appendChild(el("h3", "", gameTitle(game)));
    var visible = visibleRanks(ranked);
    var truncated = visible.length < ranked.length;
    var openFull = function () { showFullBoard(game, ranked, namesById); };
    var count = el(truncated ? "button" : "span", "count", playerCount(ranked.length));
    if (truncated) {
      count.type = "button";
      count.title = "Show everyone's scores";
      count.addEventListener("click", openFull);
    }
    head.appendChild(count);
    container.appendChild(head);
    var list = el("ol", "ranks");
    var hiddenNew = false;
    ranked.forEach(function (result, rank) {
      var key = game + ":" + result.discord_id;
      var isNew = !entering && !shownOnBoard[key];
      shown[key] = true;
      if (visible.indexOf(rank) < 0) {
        hiddenNew = hiddenNew || isNew;
        return;
      }
      list.appendChild(boardRow(result, rank, namesById, isNew));
    });
    // A new result below the cut can't flash its row, so flash the count.
    if (hiddenNew) count.classList.add("fresh");
    shown[game] = true;
    container.appendChild(list);
    if (truncated) {
      var more = el("button", "see-all", "See all " + ranked.length);
      more.type = "button";
      more.addEventListener("click", openFull);
      container.appendChild(more);
    }
    return container;
  }

  function renderBoards(byGame, emptyText) {
    var boards = document.getElementById("boards");
    var games = Object.keys(byGame).sort(function (a, b) {
      return gameTitle(a).localeCompare(gameTitle(b));
    });
    if (!games.length) {
      showMessage(boards, emptyText);
      shownOnBoard = {};
      return;
    }
    var namesById = {};
    games.forEach(function (game) {
      byGame[game].forEach(function (r) {
        if (r.name) namesById[r.discord_id] = r.name;
      });
    });
    var shown = {};
    boards.textContent = "";
    games.forEach(function (game, index) {
      boards.appendChild(board(game, byGame[game], namesById, shown, index));
    });
    shownOnBoard = shown;
  }

  // viewDay is a local midnight, or null to follow today (also across
  // midnight). Kept in the URL hash as #day=YYYY-MM-DD so it can be linked.

  function today() {
    var now = new Date();
    return new Date(now.getFullYear(), now.getMonth(), now.getDate());
  }

  function addDays(day, n) {
    return new Date(day.getFullYear(), day.getMonth(), day.getDate() + n);
  }

  function dayKey(day) {
    var pad = function (n) { return (n < 10 ? "0" : "") + n; };
    return day.getFullYear() + "-" + pad(day.getMonth() + 1) + "-" + pad(day.getDate());
  }

  function parseDayKey(key) {
    var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(key || "");
    return m ? new Date(+m[1], +m[2] - 1, +m[3]) : null;
  }

  // The game day a game's current puzzle belongs to, as a local midnight like
  // today(): the date, in its reset timezone (the viewer's own if none), of
  // its reset time before now. Mirrors gameDay() in proxy/capture/runtime.js.
  function currentGameDay(game) {
    var reset = RESETS[game];
    var shifted = new Date(Date.now() - reset.minutes * 60000);
    if (!reset.timezone) return new Date(shifted.getFullYear(), shifted.getMonth(), shifted.getDate());
    // en-CA formats dates as YYYY-MM-DD.
    return parseDayKey(new Intl.DateTimeFormat("en-CA", {
      timeZone: reset.timezone, year: "numeric", month: "2-digit", day: "2-digit",
    }).format(shifted));
  }

  function dayFromHash() {
    return parseDayKey((/^#day=(.*)$/.exec(location.hash) || [])[1]);
  }

  var viewDay = null;
  var prevButton = document.getElementById("day-prev");
  var nextButton = document.getElementById("day-next");
  var todayButton = document.getElementById("day-today");
  var dayPicker = document.getElementById("day-pick");

  function setViewDay(day, fromHash) {
    var from = viewDay || today();
    viewDay = day && day < today() ? day : null;
    var to = viewDay || today();
    // New boards slide in from the side the viewer moved towards.
    document.getElementById("boards").style.setProperty(
      "--dx", to < from ? "-16px" : to > from ? "16px" : "0px");
    if (!fromHash) {
      var hash = viewDay ? "#day=" + dayKey(viewDay) : "";
      history.replaceState({}, "", location.pathname + location.search + hash);
    }
    showViewDay();
  }

  // Today's results drive the scoreboard while it's on today.
  function renderToday(results) {
    if (viewDay) return;
    renderBoards(groupByGame(results), "Nobody has finished a game yet today. Be the first!");
  }

  // Each card's "Done" state is for its game's current puzzle, whatever day
  // the scoreboard shows: a game that resets in an earlier timezone may
  // already be on the viewer's tomorrow. So fetch today plus any such day.
  function refreshToday() {
    var todayKey = dayKey(today());
    var cardDays = {};
    var days = {};
    days[todayKey] = today();
    Object.keys(RESETS).forEach(function (game) {
      var day = currentGameDay(game);
      cardDays[game] = dayKey(day);
      days[dayKey(day)] = day;
    });
    var keys = Object.keys(days);
    Promise.all(keys.map(function (key) { return fetchResults(days[key]); })).then(function (lists) {
      var byDay = {};
      keys.forEach(function (key, i) { byDay[key] = groupByGame(lists[i]); });
      var current = {};
      Object.keys(cardDays).forEach(function (game) {
        current[game] = byDay[cardDays[game]][game];
      });
      renderCards(current);
      renderToday(lists[keys.indexOf(todayKey)]);
    }).catch(function () {});
  }

  var pastDayRequest = 0;
  function showPastDay(day) {
    var request = ++pastDayRequest;
    showMessage(document.getElementById("boards"), "Loading…", true);
    fetchResults(day).then(function (results) {
      // Ignore a slow answer for a day the viewer has already left.
      if (request !== pastDayRequest || !viewDay || viewDay.getTime() !== day.getTime()) return;
      renderBoards(groupByGame(results), "Nobody finished a game that day.");
    }).catch(function () {});
  }

  function showViewDay() {
    var day = viewDay || today();
    nextButton.disabled = !viewDay;
    todayButton.hidden = !viewDay;
    dayPicker.max = dayKey(today());
    dayPicker.value = dayKey(day);
    var title = document.getElementById("scores-title");
    title.textContent = viewDay
      ? "Scores · " + day.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" })
      : "Today's Scores";
    replay(title, "swap");
    document.getElementById("updated").textContent = "";
    shownOnBoard = null;
    if (viewDay) showPastDay(day);
    else refreshToday();
  }

  // Reset pills show the game's timezone abbreviated, e.g. "EDT"; the
  // template's fallback text is the IANA name.
  function labelResets() {
    document.querySelectorAll(".card .reset").forEach(function (tag) {
      var zone = tag.dataset.timezone, label = zone;
      try {
        var part = new Intl.DateTimeFormat(undefined, { timeZone: zone, timeZoneName: "short" })
          .formatToParts(new Date()).filter(function (p) { return p.type === "timeZoneName"; })[0];
        if (part) label = part.value;
      } catch (e) { /* keep the IANA name */ }
      tag.querySelector(".zone").textContent = label;
    });
  }
  labelResets();

  // Each card is tinted with its icon's dominant color: the icon is drawn
  // small, its opaque and not-too-grey pixels are binned by hue (weighted by
  // saturation), and the heaviest bin's pixels are averaged. The CSS mixes
  // --tint into the card's surface, so it stays muted in either theme.
  function dominantColor(img) {
    var size = 32, canvas = document.createElement("canvas");
    canvas.width = canvas.height = size;
    var ctx = canvas.getContext("2d", { willReadFrequently: true });
    ctx.drawImage(img, 0, 0, size, size);
    var pixels = ctx.getImageData(0, 0, size, size).data;
    var bins = [];
    for (var i = 0; i < pixels.length; i += 4) {
      var r = pixels[i], g = pixels[i + 1], b = pixels[i + 2];
      if (pixels[i + 3] < 128) continue;
      var max = Math.max(r, g, b), min = Math.min(r, g, b), chroma = max - min;
      if (chroma < 40 || max < 40) continue;
      var hue = max === r ? (g - b) / chroma : max === g ? 2 + (b - r) / chroma : 4 + (r - g) / chroma;
      var bin = bins[Math.floor(((hue + 6) % 6) * 2)] ||
        (bins[Math.floor(((hue + 6) % 6) * 2)] = { weight: 0, r: 0, g: 0, b: 0 });
      var weight = chroma / max;
      bin.weight += weight; bin.r += r * weight; bin.g += g * weight; bin.b += b * weight;
    }
    var best = bins.reduce(function (a, c) { return c && (!a || c.weight > a.weight) ? c : a; }, null);
    if (!best) return null;
    // Keep the hue and saturation but fix the lightness, so pale and dark
    // icons tint equally.
    var r = best.r / best.weight, g = best.g / best.weight, b = best.b / best.weight;
    var max = Math.max(r, g, b), min = Math.min(r, g, b), chroma = max - min;
    var hue = max === r ? (g - b) / chroma : max === g ? 2 + (b - r) / chroma : 4 + (r - g) / chroma;
    var sat = chroma / (255 - Math.abs(max + min - 255));
    return "hsl(" + Math.round(((hue + 6) % 6) * 60) + " " + Math.round(sat * 100) + "% 50%)";
  }

  function tintCards() {
    document.querySelectorAll(".card img.icon").forEach(function (img) {
      function tint() {
        try {
          var color = dominantColor(img);
          if (color) img.closest(".card").style.setProperty("--tint", color);
        } catch (e) { /* leave the card untinted */ }
      }
      if (img.complete) tint(); else img.addEventListener("load", tint);
    });
  }
  tintCards();

  // The bell on each card toggles the game's Discord role; the bot gives or
  // takes it within a few seconds.
  function setPinged(button, pinged) {
    button.setAttribute("aria-pressed", String(pinged));
    button.title = pinged ? "You get pinged for this game" : "Get pinged when someone finishes this game";
  }

  function setUpPings() {
    var buttons = document.querySelectorAll(".card .ping");
    if (!buttons.length || !discordId) return;
    buttons.forEach(function (button) {
      var game = button.closest(".card").dataset.game;
      button.addEventListener("click", function () {
        var pinged = button.getAttribute("aria-pressed") !== "true";
        setPinged(button, pinged);
        if (pinged) replay(button, "rung");
        fetch("/api/subscriptions", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ discord_id: discordId, game: game, subscribed: pinged }),
        }).then(function (res) {
          if (!res.ok) throw new Error(res.statusText);
        }).catch(function () {
          setPinged(button, !pinged);
        });
      });
    });
    fetch("/api/subscriptions?discord_id=" + encodeURIComponent(discordId))
      .then(function (res) { return res.json(); })
      .then(function (body) {
        buttons.forEach(function (button) {
          setPinged(button, body.games.indexOf(button.closest(".card").dataset.game) !== -1);
          button.hidden = false;
        });
      }).catch(function () {});
  }

  if (!discordId) document.getElementById("warning").style.display = "flex";
  setUpPings();

  prevButton.addEventListener("click", function () {
    setViewDay(addDays(viewDay || today(), -1));
  });
  nextButton.addEventListener("click", function () {
    if (viewDay) setViewDay(addDays(viewDay, 1));
  });
  todayButton.addEventListener("click", function () { setViewDay(null); });
  dayPicker.addEventListener("change", function () {
    var day = parseDayKey(dayPicker.value);
    if (day) setViewDay(day);
  });
  window.addEventListener("hashchange", function () { setViewDay(dayFromHash(), true); });

  setViewDay(dayFromHash(), true);
  if (viewDay) refreshToday();
  setInterval(refreshToday, REFRESH_MS);
})();
