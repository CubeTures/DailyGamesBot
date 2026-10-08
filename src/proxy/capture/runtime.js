// Daily Games Bot result capture runtime, injected at the top of every HTML
// page a game with triggers serves (see capture/script.py).
//
// The placeholders are filled with the game's name, its reset time and its
// triggers. Each
// trigger's `when` and `fields` is a function(req, res, event) that runs the
// game's vars.js and returns `when` / the fields object. They're compiled into
// this scope so they can use the helpers below (ls, ss, text, texts, exists,
// cookie, today). A solve timer fills in time_secs for games that don't
// report one.
//
// Debug from devtools: window.__dgb.status(), .dryRun(), .testNetwork(...)
(function () {
  "use strict";
  if (window.__dgb) return;

  var GAME = __DGB_GAME__;
  var RESULT_ENDPOINT = "/__dgb/result";
  var MAX_LOG_ENTRIES = 50;
  // Captured before wrapping, so reporting a result doesn't trip triggers.
  var originalFetch = window.fetch ? window.fetch.bind(window) : null;

  function parseJson(value) {
    if (value == null) return value;
    try { return JSON.parse(value); } catch (e) { return value; }
  }
  function ls(key) { try { return parseJson(localStorage.getItem(key)); } catch (e) { return null; } }
  function ss(key) { try { return parseJson(sessionStorage.getItem(key)); } catch (e) { return null; } }
  function text(selector) {
    var node = document.querySelector(selector);
    return node ? (node.textContent || "").trim() : null;
  }
  function texts(selector) {
    return Array.prototype.map.call(document.querySelectorAll(selector), function (node) {
      return (node.textContent || "").trim();
    });
  }
  function exists(selector) { return !!document.querySelector(selector); }
  function cookie(name) {
    var escaped = name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    var match = document.cookie.match(new RegExp("(?:^|; )" + escaped + "=([^;]*)"));
    return match ? decodeURIComponent(match[1]) : null;
  }
  function today() {
    var d = new Date();
    var pad = function (n) { return (n < 10 ? "0" : "") + n; };
    return d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate());
  }

  var TRIGGERS = __DGB_TRIGGERS__;

  var state = {
    game: GAME,
    sent: {},       // puzzle_id -> payload, so one page load reports once
    errors: [],
    log: [],
  };

  function appendCapped(list, entry) {
    list.push(entry);
    if (list.length > MAX_LOG_ENTRIES) list.shift();
  }

  function noteError(trigger, expr, error) {
    appendCapped(state.errors, { trigger: trigger.name, expr: expr, error: String(error) });
  }

  function safeCall(trigger, label, fn, req, res, event) {
    try {
      return fn(req, res, event);
    } catch (e) {
      noteError(trigger, label, e);
      return undefined;
    }
  }

  // Solve timer, for games that don't time themselves: the first time a
  // page of the game loads in a game day, that's when the player started,
  // and a report's time_secs is how long ago that was. Kept in this game's
  // localStorage, so reloads and leaving the tab don't reset it. A game day
  // runs from the game's reset time (config.toml [reset]). The time is only
  // reported if the player has clicked or typed since the start, so a puzzle
  // already finished elsewhere, whose result fires on load, gets none.
  var RESET = __DGB_RESET__;
  var TIMER_KEY = "__dgb_timer";

  // The current game day, as YYYY-MM-DD: the date, in the reset timezone
  // (the player's own if none), of RESET.minutes before now.
  function gameDay() {
    var shifted = new Date(Date.now() - RESET.minutes * 60000);
    if (!RESET.timezone) {
      var pad = function (n) { return (n < 10 ? "0" : "") + n; };
      return shifted.getFullYear() + "-" + pad(shifted.getMonth() + 1) + "-" + pad(shifted.getDate());
    }
    // en-CA formats dates as YYYY-MM-DD.
    return new Intl.DateTimeFormat("en-CA", {
      timeZone: RESET.timezone, year: "numeric", month: "2-digit", day: "2-digit",
    }).format(shifted);
  }

  function saveTimer(timer) {
    // Through the prototype, so the setItem wrapper below doesn't schedule a check.
    try { Storage.prototype.setItem.call(localStorage, TIMER_KEY, JSON.stringify(timer)); } catch (e) { /* storage unavailable */ }
  }

  // {day, start (epoch ms), played (input seen since)} for today's game day,
  // started now if there isn't one yet.
  function currentTimer() {
    var day = gameDay();
    var timer = ls(TIMER_KEY);
    if (!timer || timer.day !== day || typeof timer.start !== "number") {
      timer = { day: day, start: Date.now(), played: false };
      saveTimer(timer);
    }
    return timer;
  }

  function timerSecs() {
    var timer = currentTimer();
    return timer.played ? Math.round((Date.now() - timer.start) / 1000) : null;
  }

  currentTimer();
  // The game day this page's puzzle belongs to, reported with its result so
  // the launcher files it under the right day. Taken at load, so a puzzle
  // started before the reset and finished after it keeps its own day.
  var PAGE_DAY = gameDay();
  ["pointerdown", "keydown"].forEach(function (name) {
    window.addEventListener(name, function (event) {
      var timer = currentTimer();
      if (!event.isTrusted || timer.played) return;
      timer.played = true;
      saveTimer(timer);
    }, true);
  });

  function toJsonValue(value) {
    try { return JSON.parse(JSON.stringify(value === undefined ? null : value)); } catch (e) { return String(value); }
  }

  // The payload a trigger would report right now, or null.
  function evaluate(trigger, req, res, event) {
    if (!safeCall(trigger, "when", trigger.when, req, res, event)) return null;
    var raw = safeCall(trigger, "fields", trigger.fields, req, res, event);
    if (!raw || typeof raw !== "object") {
      noteError(trigger, "fields", "fields.js gave no object");
      return null;
    }
    var fields = {};
    for (var key in raw) fields[key] = toJsonValue(raw[key]);
    var puzzleId = fields.puzzle_id;
    if (puzzleId === null || puzzleId === undefined || puzzleId === "") {
      noteError(trigger, "puzzle_id", "empty puzzle_id");
      return null;
    }
    if (typeof fields.time_secs !== "number") {
      var secs = timerSecs();
      if (secs !== null) fields.time_secs = secs;
    }
    return {
      game: GAME,
      trigger: trigger.name,
      puzzle_id: String(puzzleId),
      game_day: PAGE_DAY,
      fields: fields,
      url: location.href,
    };
  }

  function report(payload) {
    if (state.sent[payload.puzzle_id]) return;
    state.sent[payload.puzzle_id] = payload;
    var entry = { at: new Date().toISOString(), payload: payload, status: "sending" };
    appendCapped(state.log, entry);
    var sending = originalFetch
      ? originalFetch(RESULT_ENDPOINT, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
          keepalive: true,
          credentials: "same-origin",
        }).then(function (response) {
          return response.text().then(function (body) { entry.status = response.status + " " + body; });
        })
      : Promise.reject(new Error("no fetch"));
    sending.catch(function (e) {
      entry.status = "error " + e;
      delete state.sent[payload.puzzle_id]; // let a later check retry
    });
  }

  function fire(trigger, req, res, event) {
    var payload = evaluate(trigger, req, res, event);
    if (payload) report(payload);
  }

  function triggersOfType(type) {
    return TRIGGERS.filter(function (t) { return t.type === type; });
  }

  var pageTriggers = triggersOfType("page");
  var pendingCheck = null;

  function checkPage() {
    pendingCheck = null;
    pageTriggers.forEach(function (t) { fire(t); });
  }

  // Debounced: a burst of mutations or storage writes checks once.
  function scheduleCheck() {
    if (!pageTriggers.length || pendingCheck) return;
    pendingCheck = setTimeout(checkPage, 250);
  }

  function watchPage() {
    setInterval(scheduleCheck, 1000);
    var observeDom = function () {
      new MutationObserver(scheduleCheck).observe(document.documentElement, {
        subtree: true, childList: true, characterData: true, attributes: true,
      });
      scheduleCheck();
    };
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", observeDom);
    } else {
      observeDom();
    }
    ["localStorage", "sessionStorage"].forEach(function (name) {
      try {
        var store = window[name];
        var setItem = store.setItem.bind(store);
        store.setItem = function (key, value) { setItem(key, value); scheduleCheck(); };
      } catch (e) { /* storage unavailable */ }
    });
  }

  if (pageTriggers.length) watchPage();

  triggersOfType("event").forEach(function (t) {
    var target = t.target === "document" ? document : window;
    target.addEventListener(t.event, function (event) { fire(t, undefined, undefined, event); }, true);
  });

  var networkTriggers = triggersOfType("network");

  function parseBody(raw) {
    if (raw instanceof URLSearchParams) raw = raw.toString();
    if (typeof raw !== "string") return { body: null, json: null };
    var json = null;
    try { json = JSON.parse(raw); } catch (e) { /* not JSON */ }
    return { body: raw, json: json };
  }

  function absoluteUrl(url) {
    try { return new URL(url, location.href).href; } catch (e) { return String(url); }
  }

  function requestInfo(method, url, rawBody) {
    var parsed = parseBody(rawBody);
    return { url: absoluteUrl(url), method: String(method).toUpperCase(), body: parsed.body, json: parsed.json };
  }

  function responseInfo(status, rawBody) {
    var parsed = parseBody(rawBody);
    return { status: status, body: parsed.body, json: parsed.json };
  }

  function matchesRequest(trigger, req) {
    return (!trigger.method || trigger.method === req.method) && trigger.url.test(req.url);
  }

  function onNetworkResponse(req, res) {
    networkTriggers.forEach(function (t) {
      if (matchesRequest(t, req)) fire(t, req, res);
    });
    scheduleCheck();
  }

  function wrapFetch() {
    window.fetch = function (input, init) {
      var url = typeof input === "string" || input instanceof URL ? input : input.url;
      var method = (init && init.method) || (input && input.method) || "GET";
      var req = requestInfo(method, url, init && init.body);
      var pending = originalFetch(input, init);
      if (req.url.indexOf(RESULT_ENDPOINT) === -1) {
        pending.then(function (response) {
          response.clone().text().then(function (body) {
            onNetworkResponse(req, responseInfo(response.status, body));
          }).catch(function () {});
        }).catch(function () {});
      }
      return pending;
    };
  }

  function xhrResponseText(xhr) {
    try {
      if (xhr.responseType === "" || xhr.responseType === "text") return xhr.responseText;
      if (xhr.responseType === "json") return JSON.stringify(xhr.response);
    } catch (e) { /* unreadable */ }
    return null;
  }

  function wrapXhr(proto) {
    var open = proto.open, send = proto.send;
    proto.open = function (method, url) {
      this.__dgbRequest = { method: method, url: absoluteUrl(url) };
      return open.apply(this, arguments);
    };
    proto.send = function (body) {
      var xhr = this, opened = xhr.__dgbRequest;
      if (opened) {
        var req = requestInfo(opened.method, opened.url, body);
        xhr.addEventListener("loadend", function () {
          onNetworkResponse(req, responseInfo(xhr.status, xhrResponseText(xhr)));
        });
      }
      return send.apply(this, arguments);
    };
  }

  if (originalFetch) wrapFetch();
  if (window.XMLHttpRequest) wrapXhr(window.XMLHttpRequest.prototype);

  window.__dgb = {
    state: state,
    triggers: TRIGGERS.map(function (t) { return t.name + " (" + t.type + ")"; }),
    // What every page trigger evaluates to right now, without sending.
    dryRun: function () {
      return pageTriggers.map(function (t) {
        return { trigger: t.name, fired: !!safeCall(t, "when", t.when), payload: evaluate(t) };
      });
    },
    // Run network triggers against a sample request/response without sending.
    // e.g. __dgb.testNetwork("PUT", "/svc/state", reqBodyString, respBodyString)
    testNetwork: function (method, url, reqBody, resBody, status) {
      var req = requestInfo(method, url, reqBody);
      var res = responseInfo(status || 200, resBody);
      return networkTriggers.map(function (t) {
        var matched = matchesRequest(t, req);
        return { trigger: t.name, matched: matched, payload: matched ? evaluate(t, req, res) : null };
      });
    },
    status: function () {
      return { game: GAME, triggers: this.triggers, sent: state.sent, log: state.log, errors: state.errors, timer: ls(TIMER_KEY) };
    },
    check: checkPage,
  };
})();
