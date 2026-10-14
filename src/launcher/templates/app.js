(function () {
  var GAME_TITLES = JSON.parse(document.getElementById("game-titles").textContent);
  var RESETS = JSON.parse(document.getElementById("resets").textContent);
  var HIGHER_SCORE_WINS = JSON.parse(document.getElementById("higher-score-wins").textContent);
  var MEDALS = ["🥇", "🥈", "🥉"];
  var REFRESH_MS = 30000;
  // Rows a scoreboard card shows before the rest move to the full list.
  var BOARD_ROWS = 5;

  // The token from the player's /play link, which the server maps to their
  // Discord ID. It stops working if an admin resets it (say, after a leak).
  var token = rememberToken();
  // The viewer's Discord ID, once identify() has asked the server.
  var discordId = null;
  // Each game's icon color, by game name, once tintCards() has found it.
  var TINTS = {};
  // Games the viewer has hidden, by name: "card" hides just its card, "all"
  // its scoreboard too. See setUpHiding().
  var hiddenGames = loadHiddenGames();

  function rememberToken() {
    // The server only sends this page for a working token, from the /play
    // link's ?token= or the cookie it set then, and fills it in here.
    var value = document.querySelector('meta[name="dgb-token"]').content;
    // Left over from when the page kept the token (and before it, the
    // Discord ID) itself.
    localStorage.removeItem("token");
    localStorage.removeItem("discord_id");
    var params = new URLSearchParams(location.search);
    if (params.has("token")) {
      params.delete("token");
      var query = params.toString();
      history.replaceState({}, "", location.pathname + (query ? "?" + query : "") + location.hash);
    }
    tagGameLinks(value);
    return value;
  }

  // Resolves to the viewer's Discord ID, or null if the server can't say.
  function identify() {
    return fetch("/api/me?token=" + encodeURIComponent(token)).then(function (res) {
      if (res.status === 401) {
        // Reset by an admin since the page loaded: the server now sends the
        // "link expired" page instead.
        location.reload();
        return null;
      }
      return res.json().then(function (body) { return body.discord_id; });
    }).catch(function () { return null; });
  }

  // Games run on their own subdomains, which can't read this page's storage
  // or cookies. Their links go through the proxy's /__dgb/enter, which sets
  // the cookie the proxy reads when a game reports a result.
  function tagGameLinks(value) {
    document.querySelectorAll("a.card-link").forEach(function (link) {
      var url = new URL(link.href);
      url.searchParams.set("token", value);
      link.href = url.toString();
    });
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

  function pad(n) {
    return (n < 10 ? "0" : "") + n;
  }

  function getJson(url) {
    return fetch(url).then(function (res) { return res.json(); });
  }

  // Rejects unless the server accepted it.
  function postJson(url, body) {
    return fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then(function (res) {
      if (!res.ok) throw new Error(res.statusText);
    });
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
    return getJson("/api/results?day=" + isoDate(day) + "&token=" + encodeURIComponent(token));
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

  // Spoilers in an announcement reveal on click or Enter/Space, as in Discord.
  function revealSpoiler(e) {
    var spoiler = e.target.closest(".spoiler:not(.revealed)");
    if (!spoiler || (e.type === "keydown" && e.key !== "Enter" && e.key !== " ")) return;
    e.preventDefault();
    spoiler.classList.add("revealed");
    spoiler.removeAttribute("role");
    spoiler.removeAttribute("tabindex");
    spoiler.removeAttribute("title");
  }
  message.addEventListener("click", revealSpoiler);
  message.addEventListener("keydown", revealSpoiler);

  // The dialog shows either an announcement or a game's full scoreboard;
  // `back`, if given, is what its back button returns to.
  function showDialog(game, title, showList, back) {
    var oldIcon = dialogHead.querySelector(".icon");
    if (oldIcon) oldIcon.remove();
    dialogHead.insertBefore(smallIcon(game), dialogTitle);
    dialogTitle.textContent = title;
    if (TINTS[game]) dialog.style.setProperty("--tint", TINTS[game]);
    else dialog.style.removeProperty("--tint");
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
      if (mine) {
        // A loss is stamped "Done", not "Cleared", and has no score line.
        var score = formatScore(mine.data);
        card.querySelector(".stamp-word").textContent = "Cleared";
        card.querySelector(".stamp-score").textContent = score === "–" ? "---" : score;
      }
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
    container.dataset.game = game;
    if (TINTS[game]) container.style.setProperty("--tint", TINTS[game]);
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

  // What renderBoards() last drew, to redraw when the viewer hides a board.
  var lastBoards = null;

  function renderBoards(byGame, emptyText) {
    lastBoards = { byGame: byGame, emptyText: emptyText };
    var boards = document.getElementById("boards");
    var played = Object.keys(byGame);
    var games = played.filter(function (game) {
      return hiddenGames[game] !== "all";
    }).sort(function (a, b) {
      return gameTitle(a).localeCompare(gameTitle(b));
    });
    if (!games.length) {
      showMessage(boards, played.length ? "Only games you've hidden have scores." : emptyText);
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

  function today() {
    var now = new Date();
    return new Date(now.getFullYear(), now.getMonth(), now.getDate());
  }

  function addDays(day, n) {
    return new Date(day.getFullYear(), day.getMonth(), day.getDate() + n);
  }

  function parseDayKey(key) {
    var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(key || "");
    return m ? new Date(+m[1], +m[2] - 1, +m[3]) : null;
  }

  // The game day a game's current puzzle belongs to, as a local midnight
  // like today() (gameDay() is in src/games/game_day.js).
  function currentGameDay(game) {
    return parseDayKey(gameDay(RESETS[game]));
  }

  function sameDay(a, b) {
    return a.getTime() === b.getTime();
  }

  // The last day with a puzzle out: tomorrow while a game that resets in an
  // earlier timezone is already on it, otherwise today.
  function latestDay() {
    return Object.keys(RESETS).reduce(function (latest, game) {
      var day = currentGameDay(game);
      return day > latest ? day : latest;
    }, today());
  }

  function dayFromHash() {
    return parseDayKey((/^#day=(.*)$/.exec(location.hash) || [])[1]);
  }

  // The scoreboard's home day, where it opens and where "Today" goes: the
  // latest day the viewer has a result on if that's ahead of today (they've
  // moved on to puzzles that reset before their midnight), otherwise today.
  // Null until refreshToday() has first looked.
  var homeDay = null;

  function home() {
    return homeDay && homeDay >= today() ? homeDay : today();
  }

  // A local midnight, or null to follow the home day (also across midnight).
  // Kept in the URL hash as #day=YYYY-MM-DD so it can be linked.
  var viewDay = null;
  var prevButton = document.getElementById("day-prev");
  var nextButton = document.getElementById("day-next");
  var todayButton = document.getElementById("day-today");
  var dayPicker = document.getElementById("day-pick");

  function shownDay() {
    return viewDay || home();
  }

  function writeHash() {
    var hash = viewDay ? "#day=" + isoDate(viewDay) : "";
    history.replaceState({}, "", location.pathname + location.search + hash);
  }

  // New boards slide in from the side the viewer moved towards.
  function slideFrom(from, to) {
    document.getElementById("boards").style.setProperty(
      "--dx", to < from ? "-16px" : to > from ? "16px" : "0px");
  }

  function setViewDay(day, fromHash) {
    var from = shownDay();
    viewDay = day && day <= latestDay() && !(homeDay && sameDay(day, home())) ? day : null;
    slideFrom(from, shownDay());
    if (!fromHash) writeHash();
    showViewDay();
  }

  function dayTitle(day) {
    if (sameDay(day, today())) return "Today's Scores";
    if (sameDay(day, addDays(today(), 1))) return "Tomorrow's Scores";
    return "Scores · " + day.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
  }

  function emptyText(day) {
    if (sameDay(day, today())) return "Nobody has finished a game yet today. Be the first!";
    if (day > today()) return "Nobody has finished one of tomorrow's games yet. Be the first!";
    return "Nobody finished a game that day.";
  }

  function hasMine(results) {
    return results.some(function (r) { return r.discord_id === discordId; });
  }

  // Each card's "Done" state is for its game's current puzzle, whatever day
  // the scoreboard shows: a game that resets in an earlier timezone may
  // already be on the viewer's tomorrow. So fetch today plus any such day.
  // That's also every day the home day can be, and the scoreboard follows
  // the home day forward when the viewer's first result on tomorrow lands.
  function refreshToday() {
    var days = {};
    days[isoDate(today())] = today();
    var cardDays = {};
    Object.keys(RESETS).forEach(function (game) {
      var day = currentGameDay(game);
      cardDays[game] = isoDate(day);
      days[isoDate(day)] = day;
    });
    var keys = Object.keys(days);
    Promise.all(keys.map(function (key) { return fetchResults(days[key]); })).then(function (lists) {
      var byDay = {};
      var newHome = today();
      keys.forEach(function (key, i) {
        byDay[key] = groupByGame(lists[i]);
        if (days[key] > newHome && hasMine(lists[i])) newHome = days[key];
      });
      var current = {};
      Object.keys(cardDays).forEach(function (game) {
        current[game] = byDay[cardDays[game]][game];
      });
      renderCards(current);

      var oldHome = homeDay && home();
      homeDay = newHome;
      if (viewDay && sameDay(viewDay, newHome)) {
        viewDay = null;
        writeHash();
      }
      if (!viewDay && !(oldHome && sameDay(oldHome, newHome))) {
        slideFrom(oldHome || newHome, newHome);
        showNav();
      } else {
        updateNavButtons();
      }
      var shown = shownDay();
      if (byDay[isoDate(shown)]) renderBoards(byDay[isoDate(shown)], emptyText(shown));
    }).catch(function () {});
  }

  var dayRequest = 0;
  function showDay(day) {
    var request = ++dayRequest;
    showMessage(document.getElementById("boards"), "Loading…", true);
    fetchResults(day).then(function (results) {
      // Ignore a slow answer for a day the viewer has already left.
      if (request !== dayRequest || !viewDay || !sameDay(viewDay, day)) return;
      renderBoards(groupByGame(results), emptyText(day));
    }).catch(function () {});
  }

  function updateNavButtons() {
    var latest = latestDay();
    nextButton.disabled = shownDay() >= latest;
    todayButton.hidden = !viewDay;
    // It goes to the home day, so it's named after it.
    todayButton.textContent = sameDay(home(), today()) ? "Today" : "Tomorrow";
    dayPicker.max = isoDate(latest);
  }

  function showNav() {
    var day = shownDay();
    updateNavButtons();
    dayPicker.value = isoDate(day);
    // Until the home day is known, keep the page's own title rather than
    // flash today's before moving on to tomorrow's.
    if (viewDay || homeDay) {
      var title = document.getElementById("scores-title");
      title.textContent = dayTitle(day);
      replay(title, "swap");
    }
    document.getElementById("updated").textContent = "";
    shownOnBoard = null;
  }

  function showViewDay() {
    showNav();
    if (viewDay) showDay(viewDay);
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

  // Each card, scoreboard and the dialog showing its game is tinted with its icon's dominant color. The
  // CSS mixes --tint into their surfaces, so it stays muted in either theme.
  function tintCards() {
    document.querySelectorAll(".card img.icon").forEach(function (img) {
      function tint() {
        try {
          var color = iconColor.dominant(img);
          if (!color) return;
          var game = img.closest(".card").dataset.game;
          TINTS[game] = color;
          // Boards drawn before this ran pick it up here; later ones in board().
          document.querySelectorAll('.card[data-game="' + game + '"], .board[data-game="' + game + '"]')
            .forEach(function (node) { node.style.setProperty("--tint", color); });
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
        postJson("/api/subscriptions", { token: token, game: game, subscribed: pinged })
          .catch(function () { setPinged(button, !pinged); });
      });
    });
    getJson("/api/subscriptions?token=" + encodeURIComponent(token))
      .then(function (body) {
        buttons.forEach(function (button) {
          setPinged(button, body.games.indexOf(button.closest(".card").dataset.game) !== -1);
          button.hidden = false;
        });
      }).catch(function () {});
  }

  // The pencil beside "Games" lets players choose which games they see.
  // While editing, every card shows, and a click on one cycles it through
  // shown, card hidden, and card and scoreboard hidden. The choice is saved
  // for the player on the server, and cached here so hidden cards don't
  // flash on load.
  var HIDE_CYCLE = ["shown", "card", "all"];
  var HIDE_LABELS = { shown: "Shown", card: "Hidden", all: "Invisible" };

  function loadHiddenGames() {
    try {
      return JSON.parse(localStorage.getItem("hidden_games")) || {};
    } catch (e) {
      return {};
    }
  }

  function showHideLevel(card, level) {
    var title = gameTitle(card.dataset.game);
    card.dataset.hide = level;
    card.querySelector(".hide-level").textContent = HIDE_LABELS[level];
    var button = card.querySelector(".visibility");
    button.title = HIDE_LABELS[level];
    button.setAttribute("aria-label", level === "shown" ? "Hide " + title
      : level === "card" ? "Hide " + title + "'s scores too" : "Show " + title);
  }

  function applyHiddenGames() {
    document.querySelectorAll(".card").forEach(function (card) {
      showHideLevel(card, hiddenGames[card.dataset.game] || "shown");
    });
    try {
      localStorage.setItem("hidden_games", JSON.stringify(hiddenGames));
    } catch (e) { /* only costs a flash on the next load */ }
    if (lastBoards) renderBoards(lastBoards.byGame, lastBoards.emptyText);
  }

  function setUpHiding() {
    if (!discordId) return;
    var games = document.getElementById("games");
    var editButton = document.getElementById("edit-games");
    var note = document.getElementById("edit-note");

    function setLevel(game, level) {
      if (level === "shown") delete hiddenGames[game];
      else hiddenGames[game] = level;
      applyHiddenGames();
    }

    function cycle(card) {
      var game = card.dataset.game;
      var from = hiddenGames[game] || "shown";
      var to = HIDE_CYCLE[(HIDE_CYCLE.indexOf(from) + 1) % HIDE_CYCLE.length];
      setLevel(game, to);
      postJson("/api/hidden", { token: token, game: game, level: to })
        .catch(function () { setLevel(game, from); });
    }

    document.querySelectorAll(".card").forEach(function (card) {
      card.querySelector(".visibility").addEventListener("click", function () { cycle(card); });
      // While editing, a click anywhere on the card cycles it too.
      card.addEventListener("click", function (e) {
        if (games.classList.contains("editing") && !e.target.closest("button")) cycle(card);
      });
    });
    editButton.hidden = false;
    editButton.addEventListener("click", function () {
      var editing = games.classList.toggle("editing");
      editButton.setAttribute("aria-pressed", String(editing));
      editButton.title = editing ? "Done choosing games" : "Choose which games you see";
      note.hidden = !editing;
    });
    getJson("/api/hidden?token=" + encodeURIComponent(token))
      .then(function (body) {
        hiddenGames = body.games;
        applyHiddenGames();
      }).catch(function () {});
  }

  applyHiddenGames();

  prevButton.addEventListener("click", function () {
    setViewDay(addDays(shownDay(), -1));
  });
  nextButton.addEventListener("click", function () {
    setViewDay(addDays(shownDay(), 1));
  });
  todayButton.addEventListener("click", function () { setViewDay(null); });
  dayPicker.addEventListener("change", function () {
    var day = parseDayKey(dayPicker.value);
    if (day) setViewDay(day);
  });
  window.addEventListener("hashchange", function () { setViewDay(dayFromHash(), true); });

  // The scoreboard waits for the viewer's ID: it marks their rows, and
  // whether they've played tomorrow's games decides the day it opens on.
  identify().then(function (id) {
    discordId = id;
    setUpPings();
    setUpHiding();
    setViewDay(dayFromHash(), true);
    if (viewDay) refreshToday();
    setInterval(refreshToday, REFRESH_MS);
  });
})();
