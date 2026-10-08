(function () {
  var GAME_TITLES = JSON.parse(document.getElementById("game-titles").textContent);
  var HIGHER_SCORE_WINS = JSON.parse(document.getElementById("higher-score-wins").textContent);
  var MEDALS = ["🥇", "🥈", "🥉"];
  var REFRESH_MS = 30000;

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

  // Lower is better unless the game's config says `higher_score_wins`;
  // outright losses sort last, then no score, then earliest finish.
  function compareResults(a, b) {
    var aLost = lost(a.data), bLost = lost(b.data);
    if (aLost !== bLost) return aLost ? 1 : -1;
    var aScored = hasScore(a.data), bScored = hasScore(b.data);
    if (aScored !== bScored) return aScored ? -1 : 1;
    if (aScored && a.data.score !== b.data.score) {
      var diff = a.data.score - b.data.score;
      return HIGHER_SCORE_WINS.indexOf(a.game) >= 0 ? -diff : diff;
    }
    return a.captured_at < b.captured_at ? -1 : 1;
  }

  function groupByGame(results) {
    var byGame = {};
    results.forEach(function (r) { (byGame[r.game] = byGame[r.game] || []).push(r); });
    return byGame;
  }

  function fetchResults(since, until) {
    var url = "/api/results?since=" + encodeURIComponent(since.toISOString());
    if (until) url += "&until=" + encodeURIComponent(until.toISOString());
    return fetch(url).then(function (res) { return res.json(); });
  }

  var dialog = document.getElementById("announcement");

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
  // A click on the backdrop lands on the dialog itself.
  dialog.addEventListener("click", function (e) {
    if (e.target === dialog) closeDialog();
  });

  function showAnnouncement(result, namesById) {
    var head = dialog.querySelector(".dialog-head");
    var oldIcon = head.querySelector(".icon");
    if (oldIcon) oldIcon.remove();
    head.insertBefore(smallIcon(result.game), head.firstChild);
    document.getElementById("announcement-title").textContent =
      gameTitle(result.game) + " · " + playerName(result.discord_id, result.name);
    dialog.querySelector(".message").innerHTML = discordMarkdown.toHtml(
      result.announcement, function (id) { return playerName(id, namesById[id]); }, gameTitle);
    dialog.classList.remove("closing");
    if (!dialog.open) dialog.showModal();
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

  function boardRow(result, rank, namesById, isNew) {
    var item = el("li", result.discord_id === discordId ? "me" : "");
    item.style.setProperty("--r", String(Math.min(rank, 10)));
    if (isNew) item.classList.add("fresh");
    var row = el(result.announcement ? "button" : "div", "row");
    if (result.announcement) {
      row.type = "button";
      row.title = "Show the Discord announcement";
      row.addEventListener("click", function () { showAnnouncement(result, namesById); });
    }
    var scored = hasScore(result.data) && !lost(result.data);
    var rankCell = lost(result.data) ? el("span", "rank medal", "💀")
      : rank < 3 && scored ? el("span", "rank medal", MEDALS[rank])
      : el("span", "rank", String(rank + 1));
    if (lost(result.data)) rankCell.title = "Lost";
    row.appendChild(rankCell);
    row.appendChild(el("span", "name", playerName(result.discord_id, result.name)));
    row.appendChild(el("span", scored ? "score" : "score lost", formatScore(result.data)));
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
    head.appendChild(el("span", "count",
      ranked.length + (ranked.length === 1 ? " player" : " players")));
    container.appendChild(head);
    var list = el("ol");
    ranked.forEach(function (result, rank) {
      var key = game + ":" + result.discord_id;
      shown[key] = true;
      list.appendChild(boardRow(result, rank, namesById, !entering && !shownOnBoard[key]));
    });
    shown[game] = true;
    container.appendChild(list);
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

  // Today's results drive the game cards' "Done" state whatever day the
  // scoreboard shows, and the scoreboard too while it's on today.
  function renderToday(results) {
    var byGame = groupByGame(results);
    renderCards(byGame);
    if (viewDay) return;
    renderBoards(byGame, "Nobody has finished a game yet today. Be the first!");
    var updated = document.getElementById("updated");
    updated.textContent = "Updated " +
      new Date().toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
    replay(updated, "tick");
  }

  function refreshToday() {
    fetchResults(today()).then(renderToday).catch(function () {});
  }

  var pastDayRequest = 0;
  function showPastDay(day) {
    var request = ++pastDayRequest;
    showMessage(document.getElementById("boards"), "Loading…", true);
    fetchResults(day, addDays(day, 1)).then(function (results) {
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
      : "Today's scores";
    replay(title, "swap");
    document.getElementById("updated").textContent = "";
    shownOnBoard = null;
    if (viewDay) showPastDay(day);
    else refreshToday();
  }

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
