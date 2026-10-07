// Daily Games Bot result capture runtime.
//
// Injected by src/proxy/capture.py at the top of every HTML page a game
// serves. The two placeholders below are filled with the game's name and its
// triggers compiled from games/<name>/: each trigger's `when` and `fields` is
// a function(req, res, event) that runs the game's vars.js and then returns
// `when` / the fields object, evaluated in this scope so it can use the
// helpers below (ls, ss, text, texts, exists, cookie, today).
//
// Debug from devtools: window.__dgb.status(), .dryRun(), .testNetwork(...)
(function () {
  "use strict";
  if (window.__dgb) return;

  var GAME = __DGB_GAME__;
  var ENDPOINT = "/__dgb/result";
  var origFetch = window.fetch ? window.fetch.bind(window) : null;

  // ---- helpers usable from config expressions -------------------------------
  function parse(v) {
    if (v == null) return v;
    try { return JSON.parse(v); } catch (e) { return v; }
  }
  function ls(key) { try { return parse(localStorage.getItem(key)); } catch (e) { return null; } }
  function ss(key) { try { return parse(sessionStorage.getItem(key)); } catch (e) { return null; } }
  function text(sel) {
    var el = document.querySelector(sel);
    return el ? (el.textContent || "").trim() : null;
  }
  function texts(sel) {
    return Array.prototype.map.call(document.querySelectorAll(sel), function (el) {
      return (el.textContent || "").trim();
    });
  }
  function exists(sel) { return !!document.querySelector(sel); }
  function cookie(name) {
    var m = document.cookie.match(new RegExp("(?:^|; )" + name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + "=([^;]*)"));
    return m ? decodeURIComponent(m[1]) : null;
  }
  function today() {
    var d = new Date();
    var pad = function (n) { return (n < 10 ? "0" : "") + n; };
    return d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate());
  }

  var TRIGGERS = __DGB_TRIGGERS__;

  // ---- state ----------------------------------------------------------------
  var state = {
    game: GAME,
    sent: {},       // puzzle_id -> payload, so one page load reports once
    errors: [],     // last few expression errors, for debugging
    log: [],        // what fired and what happened to it
  };

  function note(list, entry) {
    list.push(entry);
    if (list.length > 50) list.shift();
  }

  function call(trigger, label, fn, req, res, event) {
    try {
      return fn(req, res, event);
    } catch (e) {
      note(state.errors, { trigger: trigger.name, expr: label, error: String(e) });
      return undefined;
    }
  }

  function jsonable(v) {
    try { return JSON.parse(JSON.stringify(v === undefined ? null : v)); } catch (e) { return String(v); }
  }

  // Evaluate a trigger; return the payload it would send, or null.
  function evaluate(trigger, req, res, event) {
    if (!call(trigger, "when", trigger.when, req, res, event)) return null;
    var raw = call(trigger, "fields", trigger.fields, req, res, event);
    if (!raw || typeof raw !== "object") {
      note(state.errors, { trigger: trigger.name, expr: "fields", error: "fields.js gave no object" });
      return null;
    }
    var fields = {};
    for (var k in raw) fields[k] = jsonable(raw[k]);
    var puzzleId = fields.puzzle_id;
    if (puzzleId === null || puzzleId === undefined || puzzleId === "") {
      note(state.errors, { trigger: trigger.name, expr: "puzzle_id", error: "empty puzzle_id" });
      return null;
    }
    return {
      game: GAME,
      trigger: trigger.name,
      puzzle_id: String(puzzleId),
      fields: fields,
      url: location.href,
    };
  }

  function report(payload) {
    if (state.sent[payload.puzzle_id]) return;
    state.sent[payload.puzzle_id] = payload;
    var entry = { at: new Date().toISOString(), payload: payload, status: "sending" };
    note(state.log, entry);
    var body = JSON.stringify(payload);
    var send = origFetch
      ? origFetch(ENDPOINT, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: body,
          keepalive: true,
          credentials: "same-origin",
        }).then(function (r) {
          return r.text().then(function (t) { entry.status = r.status + " " + t; });
        })
      : Promise.reject(new Error("no fetch"));
    send.catch(function (e) {
      entry.status = "error " + e;
      delete state.sent[payload.puzzle_id]; // let a later check retry
    });
  }

  function byType(type) {
    return TRIGGERS.filter(function (t) { return t.type === type; });
  }

  // ---- page triggers: re-checked on DOM/storage/network activity ------------
  var pageTriggers = byType("page");
  var checkTimer = null;
  function checkPage() {
    checkTimer = null;
    pageTriggers.forEach(function (t) {
      var p = evaluate(t);
      if (p) report(p);
    });
  }
  function scheduleCheck() {
    if (!pageTriggers.length || checkTimer) return;
    checkTimer = setTimeout(checkPage, 250);
  }

  if (pageTriggers.length) {
    setInterval(scheduleCheck, 1000);
    var startObserver = function () {
      new MutationObserver(scheduleCheck).observe(document.documentElement, {
        subtree: true, childList: true, characterData: true, attributes: true,
      });
      scheduleCheck();
    };
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", startObserver);
    } else {
      startObserver();
    }
    ["localStorage", "sessionStorage"].forEach(function (name) {
      try {
        var store = window[name];
        var set = store.setItem.bind(store);
        store.setItem = function (k, v) { set(k, v); scheduleCheck(); };
      } catch (e) { /* storage unavailable */ }
    });
  }

  // ---- event triggers -------------------------------------------------------
  byType("event").forEach(function (t) {
    var target = t.target === "document" ? document : window;
    target.addEventListener(t.event, function (ev) {
      var p = evaluate(t, undefined, undefined, ev);
      if (p) report(p);
    }, true);
  });

  // ---- network triggers: wrap fetch and XHR ---------------------------------
  var netTriggers = byType("network");

  function onNetwork(req, res) {
    netTriggers.forEach(function (t) {
      if (t.method && t.method !== req.method) return;
      if (!t.url.test(req.url)) return;
      var p = evaluate(t, req, res);
      if (p) report(p);
    });
    scheduleCheck();
  }

  function bodyOf(raw) {
    if (raw == null) return { body: null, json: null };
    if (typeof raw !== "string") {
      if (raw instanceof URLSearchParams) raw = raw.toString();
      else return { body: null, json: null };
    }
    var json = null;
    try { json = JSON.parse(raw); } catch (e) { /* not JSON */ }
    return { body: raw, json: json };
  }

  function absolute(url) {
    try { return new URL(url, location.href).href; } catch (e) { return String(url); }
  }

  if (origFetch) {
    window.fetch = function (input, init) {
      var url = absolute(typeof input === "string" || input instanceof URL ? input : input.url);
      var method = ((init && init.method) || (input && input.method) || "GET").toUpperCase();
      var reqBody = bodyOf(init && init.body);
      var p = origFetch(input, init);
      if (url.indexOf(ENDPOINT) === -1) {
        p.then(function (r) {
          r.clone().text().then(function (t) {
            var rb = bodyOf(t);
            onNetwork(
              { url: url, method: method, body: reqBody.body, json: reqBody.json },
              { status: r.status, body: rb.body, json: rb.json }
            );
          }).catch(function () {});
        }).catch(function () {});
      }
      return p;
    };
  }

  var XHR = window.XMLHttpRequest && window.XMLHttpRequest.prototype;
  if (XHR) {
    var open = XHR.open, send = XHR.send;
    XHR.open = function (method, url) {
      this.__dgb = { method: String(method).toUpperCase(), url: absolute(url) };
      return open.apply(this, arguments);
    };
    XHR.send = function (body) {
      var xhr = this, info = xhr.__dgb;
      if (info) {
        var reqBody = bodyOf(body);
        xhr.addEventListener("loadend", function () {
          var t = null;
          try {
            t = xhr.responseType === "" || xhr.responseType === "text"
              ? xhr.responseText
              : xhr.responseType === "json" ? JSON.stringify(xhr.response) : null;
          } catch (e) { /* unreadable */ }
          var rb = bodyOf(t);
          onNetwork(
            { url: info.url, method: info.method, body: reqBody.body, json: reqBody.json },
            { status: xhr.status, body: rb.body, json: rb.json }
          );
        });
      }
      return send.apply(this, arguments);
    };
  }

  // ---- debug API ------------------------------------------------------------
  window.__dgb = {
    state: state,
    triggers: TRIGGERS.map(function (t) { return t.name + " (" + t.type + ")"; }),
    // What every page trigger evaluates to right now, without sending.
    dryRun: function () {
      return pageTriggers.map(function (t) {
        return { trigger: t.name, fired: !!call(t, "when", t.when), payload: evaluate(t) };
      });
    },
    // Run network triggers against a sample request/response without sending.
    // e.g. __dgb.testNetwork("PUT", "/svc/state", reqBodyString, respBodyString)
    testNetwork: function (method, url, reqBody, resBody, status) {
      var req = bodyOf(reqBody), res = bodyOf(resBody);
      var r = { url: absolute(url), method: String(method).toUpperCase(), body: req.body, json: req.json };
      var s = { status: status || 200, body: res.body, json: res.json };
      return netTriggers.map(function (t) {
        var matched = (!t.method || t.method === r.method) && t.url.test(r.url);
        return { trigger: t.name, matched: matched, payload: matched ? evaluate(t, r, s) : null };
      });
    },
    status: function () {
      return { game: GAME, triggers: this.triggers, sent: state.sent, log: state.log, errors: state.errors };
    },
    check: checkPage,
  };
})();
