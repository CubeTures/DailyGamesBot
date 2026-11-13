(function () {
  var GAME_TITLES = JSON.parse(document.getElementById("game-titles").textContent);
  // "Costcodle Checkout" for a mode, otherwise the same as GAME_TITLES.
  var FULL_TITLES = JSON.parse(document.getElementById("full-titles").textContent);
  var RESETS = JSON.parse(document.getElementById("resets").textContent);
  var HIGHER_SCORE_WINS = JSON.parse(document.getElementById("higher-score-wins").textContent);
  // Games with modes, by the name of the game they're modes of: its modes
  // in order, as [{game, mode}]. Each mode is its own game with its own
  // results; the launcher shows them as one stack (mode-stack.js).
  var MODES = JSON.parse(document.getElementById("modes").textContent);
  // Every game in a stack of modes, the one they're modes of included: its
  // group, mode name and place in the stack.
  var STACK_OF = {};
  Object.keys(MODES).forEach(function (group) {
    MODES[group].forEach(function (m, index) {
      STACK_OF[m.game] = { group: group, mode: m.mode, index: index };
    });
  });
  var MEDALS = ["🥇", "🥈", "🥉"];
  var REFRESH_MS = 30000;
  // Rows a scoreboard card shows before the rest move to the full list.
  var BOARD_ROWS = 5;

  // The token from the player's /play link, which the server maps to their
  // Discord ID. It stops working if an admin resets it (say, after a leak).
  var token = rememberToken();
  // The viewer's Discord ID, once identify() has asked the server.
  var discordId = null;
  // The servers the viewer has registered with by running /play in them,
  // as [{id, name}], and the one the scoreboard shows (null with none, or
  // ALL_GUILDS for all of them). It shows that server's players' results,
  // plus the viewer's own.
  var ALL_GUILDS = "all";
  var guilds = [];
  var guildId = null;
  // The viewer's primary server's name. With ALL_GUILDS its players' rows
  // are highlighted (the server marks them "in_primary").
  var primaryName = null;
  // Each game's icon color, by game name, once tintCards() has found it.
  var TINTS = {};
  // Games the viewer has hidden, by name: "card" hides just its card, "all"
  // its scoreboard too. See setUpHiding().
  var hiddenGames = loadHiddenGames();
  // The mode each stack shows on top, by group, as last picked here.
  var stackTops = loadStackTops();

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

  // Resolves to {discord_id, guilds, primary_guild} for the viewer, or null
  // if the server can't say.
  function identify() {
    return fetch("/api/me?token=" + encodeURIComponent(token)).then(function (res) {
      if (res.status === 401) {
        // Reset by an admin since the page loaded: the server now sends the
        // "link expired" page instead.
        location.reload();
        return null;
      }
      return res.json();
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

  // The game whose stack of modes `game` is in, or `game` itself.
  function groupOf(game) {
    return STACK_OF[game] ? STACK_OF[game].group : game;
  }

  function modeName(game) {
    return STACK_OF[game] ? STACK_OF[game].mode : "";
  }

  function fullTitle(game) {
    return FULL_TITLES[game] || game;
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
    return getJson("/api/results?day=" + isoDate(day) + "&token=" + encodeURIComponent(token) +
      (guildId ? "&guild=" + encodeURIComponent(guildId) : ""));
  }

  var dialog = document.getElementById("dialog");
  var dialogHead = dialog.querySelector(".dialog-head");
  var dialogTitle = document.getElementById("dialog-title");
  var dialogBody = dialog.querySelector(".dialog-body");
  var backButton = dialog.querySelector(".back");
  var message = dialog.querySelector(".message");
  var fullBoard = dialog.querySelector(".ranks");
  var inviteForm = dialog.querySelector(".invite");
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

  // The dialog shows an announcement ("message"), a game's full scoreboard
  // ("list") or a co-op game's invite prompt ("invite"); `back`, if given,
  // is what its back button returns to.
  function showDialog(game, title, view, back) {
    var oldIcon = dialogHead.querySelector(".icon");
    if (oldIcon) oldIcon.remove();
    dialogHead.insertBefore(smallIcon(game), dialogTitle);
    dialogTitle.textContent = title;
    if (TINTS[game]) dialog.style.setProperty("--tint", TINTS[game]);
    else dialog.style.removeProperty("--tint");
    dialogBack = back || null;
    backButton.hidden = !back;
    message.hidden = view !== "message";
    fullBoard.hidden = view !== "list";
    inviteForm.hidden = view !== "invite";
    dialog.classList.remove("closing");
    if (!dialog.open) dialog.showModal();
    dialogBody.scrollTop = 0;
  }

  // A co-op game's announcement carries the `names` of the players it
  // mentions, who may have no row on the scoreboard shown.
  function showAnnouncement(result, namesById, back) {
    var names = result.names || {};
    message.innerHTML = discordMarkdown.toHtml(result.announcement, function (id) {
      return playerName(id, namesById[id] || names[id]);
    }, gameTitle);
    showDialog(result.game,
      fullTitle(result.game) + " · " + playerName(result.discord_id, result.name), "message", back);
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
    showDialog(game, fullTitle(game) + " · " + playerCount(ranked.length), "list");
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
    // The mode pills turn green as modes are played.
    layoutCardStacks();
  }

  // ---- Stacks of a game's modes (mode-stack.js) ----

  function loadStackTops() {
    try {
      return JSON.parse(localStorage.getItem("stack_tops")) || {};
    } catch (e) {
      return {};
    }
  }

  function gameCard(game) {
    return document.querySelector('.card[data-game="' + game + '"]');
  }

  // A card stack shows the modes the viewer hasn't hidden, or all of them
  // while they're choosing which to hide.
  function layoutCardStacks() {
    var editing = document.getElementById("games").classList.contains("editing");
    document.querySelectorAll("#games .stack").forEach(function (stack) {
      var group = stack.dataset.group;
      var modes = MODES[group].map(function (m) { return m.game; }).filter(function (game) {
        return editing || !hiddenGames[game];
      });
      modeStack.layout(stack, modes, stackTops[group], {
        isDone: function (game) { return gameCard(game).classList.contains("done"); },
        modeName: modeName,
      });
    });
  }

  // Brings `game` to the top of its card stack and its scoreboard stack,
  // the front ones flying off towards `dir` (1 for left, -1 for right).
  function pickMode(group, game, dir) {
    stackTops[group] = game;
    try {
      localStorage.setItem("stack_tops", JSON.stringify(stackTops));
    } catch (e) { /* it just opens on the first mode next time */ }
    document.querySelectorAll('.stack[data-group="' + group + '"]').forEach(function (stack) {
      modeStack.shuffle(stack, game, dir);
    });
  }

  // The mode `step` places on from the one on top (-1 for the one before):
  // one on is what the card behind brings up.
  function nextMode(stack, step) {
    var modes = modeStack.modes(stack);
    var at = modes.indexOf(modeStack.front(stack).dataset.game);
    return modes[(at + (step || 1) + modes.length) % modes.length];
  }

  // Ways to switch: the pill (the mode showing goes on to the next), a
  // click on the card peeking out behind, the arrow keys on the pill, and
  // dragging the front card away.
  function setUpStacks() {
    document.addEventListener("click", function (e) {
      var stack = e.target.closest(".stack.stacked");
      if (!stack) return;
      var group = stack.dataset.group;
      var stop = function () { e.preventDefault(); e.stopPropagation(); };
      if (stack.dataset.dragged) return stop();
      var node = e.target.closest("[data-depth]");
      if (node && node.parentNode === stack && node.dataset.depth !== "0") {
        stop();
        pickMode(group, nextMode(stack), 1);
        return;
      }
      var button = e.target.closest(".modes .mode");
      if (!button) return;
      stop();
      var top = modeStack.front(stack).dataset.game;
      pickMode(group, button.dataset.game === top ? nextMode(stack) : button.dataset.game, 1);
    }, true);

    document.addEventListener("keydown", function (e) {
      var stack = e.target.closest && e.target.closest(".stack.stacked");
      if (!stack || !e.target.closest(".modes")) return;
      var step = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
      if (!step) return;
      e.preventDefault();
      pickMode(stack.dataset.group, nextMode(stack, step), step);
    });

    var drag = null;
    document.addEventListener("pointerdown", function (e) {
      var node = e.target.closest(".stack.stacked > [data-depth='0']");
      if (!node || e.button !== 0 || e.target.closest(".modes, .ping, .icon-btn")) return;
      if (document.getElementById("games").classList.contains("editing")) return;
      drag = { node: node, stack: node.parentNode, x: e.clientX, dx: 0, moved: false, id: e.pointerId };
    });
    window.addEventListener("pointermove", function (e) {
      if (!drag || e.pointerId !== drag.id) return;
      drag.dx = e.clientX - drag.x;
      if (!drag.moved && Math.abs(drag.dx) > 6) {
        drag.moved = true;
        drag.node.classList.add("dragging");
        try { drag.node.setPointerCapture(e.pointerId); } catch (err) { /* drags without it */ }
      }
      if (drag.moved) {
        drag.node.style.transform = "translate(" + drag.dx + "px, " + (-Math.abs(drag.dx) * 0.06) +
          "px) rotate(" + (drag.dx / 28) + "deg)";
      }
    });
    function endDrag(e) {
      if (!drag || e.pointerId !== drag.id) return;
      var d = drag;
      drag = null;
      if (!d.moved) return;
      // Swallow the click that ends the drag.
      d.stack.dataset.dragged = "1";
      setTimeout(function () { delete d.stack.dataset.dragged; }, 0);
      if (Math.abs(d.dx) > Math.min(90, d.node.offsetWidth * 0.25)) {
        // Like the arrow keys: thrown left brings up the next mode, right the one before.
        var step = d.dx < 0 ? 1 : -1;
        pickMode(d.stack.dataset.group, nextMode(d.stack, step), step);
      } else {
        d.node.classList.remove("dragging");
        d.node.style.transform = "";
      }
    }
    window.addEventListener("pointerup", endDrag);
    window.addEventListener("pointercancel", endDrag);
    document.addEventListener("dragstart", function (e) {
      if (e.target.closest && e.target.closest(".stack.stacked")) e.preventDefault();
    });
  }
  setUpStacks();

  // Each card's streak of two or more game days: "live" when the viewer has
  // played its current game day and the days before it in a row, "pending"
  // when the run ended on the day before (playing today keeps it going),
  // otherwise none. A single day isn't a streak yet.
  var streaksRendered = false;
  function renderStreaks(streaks) {
    document.querySelectorAll(".card").forEach(function (card) {
      var game = card.dataset.game;
      var streak = streaks[game];
      var current = currentGameDay(game);
      var last = streak && parseDayKey(streak.last_day);
      var state = !last || streak.days < 2 ? ""
        : sameDay(last, current) ? "live"
        : sameDay(last, addDays(current, -1)) ? "pending" : "";
      var was = card.dataset.streak || "";
      if (!state) {
        delete card.dataset.streak;
        return;
      }
      card.dataset.streak = state;
      card.querySelector(".streak .days").textContent = streak.days;
      // Celebrate the streak growing while the page is open.
      if (streaksRendered && state === "live" && was !== "live") replay(card, "streak-up");
    });
    streaksRendered = true;
  }

  function refreshStreaks() {
    return getJson("/api/streaks?token=" + encodeURIComponent(token)).then(function (body) {
      renderStreaks(body.streaks || {});
    }).catch(function () {});
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
    var item = el("li", result.discord_id === discordId ? "me" : result.in_primary ? "primary" : "");
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
    head.appendChild(el("h3", "", gameTitle(groupOf(game))));
    // In a stack of modes, the pill stands in for the count.
    if (STACK_OF[game]) {
      var pill = el("div", "modes");
      pill.setAttribute("role", "tablist");
      pill.setAttribute("aria-label", gameTitle(groupOf(game)) + " modes");
      pill.hidden = true;
      head.appendChild(pill);
    }
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
    var hiddenPrimary = 0;
    ranked.forEach(function (result, rank) {
      var key = game + ":" + result.discord_id;
      var isNew = !entering && !shownOnBoard[key];
      shown[key] = true;
      if (visible.indexOf(rank) < 0) {
        hiddenNew = hiddenNew || isNew;
        if (result.in_primary && result.discord_id !== discordId) hiddenPrimary++;
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
      // Players from the primary server below the cut tint the button.
      if (hiddenPrimary) {
        more.classList.add("has-primary");
        more.title = hiddenPrimary + " more from " + (primaryName || "your primary server");
      }
      if (hiddenNew) more.classList.add("fresh");
      more.addEventListener("click", openFull);
      var bar = el("div", "see-all-bar");
      bar.appendChild(more);
      container.appendChild(bar);
    }
    return container;
  }

  // What renderBoards() last drew, to redraw when the viewer hides a board.
  var lastBoards = null;

  function renderBoards(byGame, emptyText) {
    lastBoards = { byGame: byGame, emptyText: emptyText };
    var boards = document.getElementById("boards");
    var played = Object.keys(byGame);
    // A game's modes sort together, in their order.
    var modeIndex = function (game) {
      return STACK_OF[game] ? STACK_OF[game].index : 0;
    };
    var games = played.filter(function (game) {
      return hiddenGames[game] !== "all";
    }).sort(function (a, b) {
      return gameTitle(groupOf(a)).localeCompare(gameTitle(groupOf(b))) || modeIndex(a) - modeIndex(b);
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
    var stacks = {};
    boards.textContent = "";
    games.forEach(function (game, index) {
      var node = board(game, byGame[game], namesById, shown, index);
      if (!STACK_OF[game]) {
        boards.appendChild(node);
        return;
      }
      var group = groupOf(game);
      if (!stacks[group]) {
        stacks[group] = el("div", "stack");
        stacks[group].dataset.group = group;
        boards.appendChild(stacks[group]);
      }
      stacks[group].appendChild(node);
    });
    // A scoreboard stack has the modes someone has played that day.
    Object.keys(stacks).forEach(function (group) {
      var modes = games.filter(function (game) { return groupOf(game) === group; });
      modeStack.layout(stacks[group], modes, stackTops[group], {
        isDone: function (game) { return hasMine(byGame[game]); },
        modeName: modeName,
      });
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
    // Without a server, the board only has the viewer's own results.
    if (!guildId) return "Run /play in a Discord server to see its players' scores here.";
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
    var forGuild = guildId;
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
      refreshStreaks();

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
      // The viewer has switched servers since: its own refresh draws the board.
      if (forGuild !== guildId) return;
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

  // Milliseconds `zone`'s wall clock is ahead of UTC at `at`.
  function zoneOffset(zone, at) {
    var p = {};
    new Intl.DateTimeFormat("en-US", {
      timeZone: zone, hourCycle: "h23", year: "numeric", month: "numeric", day: "numeric",
      hour: "numeric", minute: "numeric",
    }).formatToParts(at).forEach(function (part) { p[part.type] = +part.value; });
    return Date.UTC(p.year, p.month - 1, p.day, p.hour, p.minute) - Math.floor(at / 60000) * 60000;
  }

  // The next instant `reset` (an entry of RESETS with a timezone) comes round.
  function nextReset(reset) {
    var now = Date.now(), offset = zoneOffset(reset.timezone, now);
    var wall = new Date(now + offset);
    var target = Date.UTC(wall.getUTCFullYear(), wall.getUTCMonth(), wall.getUTCDate()) + reset.minutes * 60000;
    if (target <= now + offset) target += 86400000;
    // Use the offset at the reset itself, in case DST changes before it.
    return new Date(target - zoneOffset(reset.timezone, target - offset));
  }

  // Reset pills on games that reset in a fixed timezone show when that is on
  // the player's clock, e.g. "5 PM". They stay hidden when it's the same
  // wall-clock time as the game's own reset, like local games.
  function labelResets() {
    document.querySelectorAll(".card .reset").forEach(function (tag) {
      var reset = RESETS[tag.closest(".card").dataset.game];
      try {
        var at = nextReset(reset);
      } catch (e) { return; /* unknown timezone; leave the pill hidden */ }
      var local = at.getHours() * 60 + at.getMinutes();
      var label = at.toLocaleTimeString([], at.getMinutes() ? { hour: "numeric", minute: "2-digit" } : { hour: "numeric" });
      tag.querySelector(".at").textContent = label;
      tag.title = "New puzzle at " + label + " your time";
      tag.hidden = local === reset.minutes;
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

  // Opening a co-op game's card first asks which of the viewer's servers
  // the bot should post a link to join them in when they start a game. The
  // pick is saved per game (no pick yet means all of them) and checked
  // again the next time.
  var inviteServers = inviteForm.querySelector(".servers");
  var invitePlay = inviteForm.querySelector(".play-btn");
  var invitePicks = {};
  var inviteGame = null;

  function invitedIds() {
    return Array.prototype.filter.call(inviteServers.querySelectorAll("input"), function (box) {
      return box.checked;
    }).map(function (box) { return box.value; });
  }

  function showInvite(game, href) {
    var picked = invitePicks[game];
    inviteGame = game;
    inviteServers.textContent = "";
    guilds.forEach(function (g) {
      var label = el("label", "server");
      var box = el("input");
      box.type = "checkbox";
      box.value = g.id;
      box.checked = !picked || picked.indexOf(g.id) !== -1;
      label.appendChild(box);
      label.appendChild(el("span", "", g.name || "Server " + g.id));
      inviteServers.appendChild(label);
    });
    invitePlay.href = href;
    showDialog(game, fullTitle(game), "invite");
    invitePlay.focus();
  }

  function setUpInvites() {
    var links = document.querySelectorAll(".card[data-invite] a.card-link");
    if (!links.length || !discordId || !guilds.length) return;
    inviteForm.addEventListener("submit", function (e) { e.preventDefault(); });
    // A real link into the game, so opening it is never blocked as a popup.
    invitePlay.addEventListener("click", function () {
      var game = inviteGame;
      var before = invitePicks[game];
      invitePicks[game] = invitedIds();
      postJson("/api/invites", { token: token, game: game, guilds: invitePicks[game] })
        .catch(function () { invitePicks[game] = before; });
      closeDialog();
    });
    // Asks only once the saved picks are in, so it never shows stale ones.
    getJson("/api/invites?token=" + encodeURIComponent(token))
      .then(function (body) { invitePicks = body.games || {}; })
      .catch(function () {})
      .then(function () {
        links.forEach(function (link) {
          link.addEventListener("click", function (e) {
            // A new-tab or middle click goes straight in, with the saved pick.
            if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
            e.preventDefault();
            showInvite(link.closest(".card").dataset.game, link.href);
          });
        });
      });
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
    var title = fullTitle(card.dataset.game);
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
    layoutCardStacks();
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
      // Hidden modes come back into their stacks while editing.
      layoutCardStacks();
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

  // Fills the server picker, which opens on the server the viewer last
  // picked here (else their primary one) and is only shown when they have
  // more than one, with an "All servers" option first.
  function setUpGuilds(me) {
    guilds = (me && me.guilds) || [];
    var ids = guilds.map(function (g) { return g.id; });
    if (guilds.length > 1) ids.push(ALL_GUILDS);
    var last = loadLastGuild();
    guildId = ids.indexOf(last) >= 0 ? last
      : me && ids.indexOf(me.primary_guild) >= 0 ? me.primary_guild : ids[0] || null;
    var primary = guilds.filter(function (g) { return me && g.id === me.primary_guild; })[0];
    primaryName = primary ? primary.name : null;
    var picker = document.getElementById("guild-pick");
    picker.textContent = "";
    if (guilds.length > 1) {
      var all = el("option", "", "All Servers");
      all.value = ALL_GUILDS;
      picker.appendChild(all);
    }
    guilds.forEach(function (g) {
      var option = el("option", "", g.name || "Server " + g.id);
      option.value = g.id;
      picker.appendChild(option);
    });
    picker.value = guildId || "";
    picker.hidden = guilds.length < 2;
    picker.addEventListener("change", function () {
      guildId = picker.value;
      saveLastGuild(guildId);
      shownOnBoard = null;
      lastBoards = null;
      if (viewDay) {
        showDay(viewDay);
      } else {
        showMessage(document.getElementById("boards"), "Loading…", true);
        refreshToday();
      }
    });
  }

  // The server picked last, kept per browser.
  function loadLastGuild() {
    try {
      return localStorage.getItem("guild");
    } catch (e) {
      return null;
    }
  }

  function saveLastGuild(id) {
    try {
      localStorage.setItem("guild", id);
    } catch (e) { /* it just opens on the primary server next time */ }
  }

  // The scoreboard waits for the viewer's ID: it marks their rows, and
  // whether they've played tomorrow's games decides the day it opens on.
  identify().then(function (me) {
    discordId = me && me.discord_id;
    setUpGuilds(me);
    setUpPings();
    setUpHiding();
    setUpInvites();
    setViewDay(dayFromHash(), true);
    if (viewDay) refreshToday();
    setInterval(refreshToday, REFRESH_MS);
  });
})();
