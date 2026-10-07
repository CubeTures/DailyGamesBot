// Run with the Playwright MCP tool browser_run_code_unsafe (filename: this
// file's absolute path). Installs an init script in the browser context so
// every page/frame/reload records what the game does while the user plays:
// fetch/XHR/sendBeacon (with bodies), local/sessionStorage writes, cookie
// writes, programmatic DOM events, postMessage, history changes and
// dataLayer (analytics) pushes. The log survives reloads via sessionStorage.
//
// Read it back with browser_evaluate:
//   () => __dgbRec.summary()              one line per entry
//   () => __dgbRec.summary({ kind: "net", grep: "state" })
//   () => __dgbRec.get(12)                full entry incl. bodies
//   () => __dgbRec.storage("game|puzzle") current local/sessionStorage (key filter)
//   () => __dgbRec.storageKeys()          keys written during the recording
//   () => __dgbRec.mark("user done")      add a marker entry
async (page) => {
  await page.context().addInitScript(() => {
    if (window.__dgbRec) return;
    var KEY = "__dgbRec";
    var MAX_BODY = 20000;
    var MAX_ENTRIES = 3000;
    var ss = null; // denied in sandboxed (ad) iframes
    try { ss = window.sessionStorage; } catch (e) { /* record without persisting */ }
    var ssGet = Storage.prototype.getItem;
    var ssSet = Storage.prototype.setItem;
    var entries = [];
    try { entries = JSON.parse((ss && ssGet.call(ss, KEY)) || "[]"); } catch (e) { entries = []; }
    var saveTimer = null;

    function trunc(v) {
      if (v == null) return v;
      if (typeof v !== "string") {
        try { v = JSON.stringify(v); } catch (e) { v = String(v); }
      }
      return v.length > MAX_BODY ? v.slice(0, MAX_BODY) + "...[truncated " + v.length + "]" : v;
    }
    function save() {
      saveTimer = null;
      if (!ss) return;
      try { ssSet.call(ss, KEY, JSON.stringify(entries)); } catch (e) {
        entries.splice(0, Math.floor(entries.length / 4)); // quota: drop oldest
      }
    }
    function rec(kind, data) {
      data.kind = kind;
      data.at = new Date().toISOString();
      data.page = location.pathname;
      if (window !== window.top) data.frame = location.href;
      entries.push(data);
      if (entries.length > MAX_ENTRIES) entries.shift();
      if (!saveTimer) saveTimer = setTimeout(save, 200);
    }
    function bodyStr(b) {
      if (b == null) return null;
      if (typeof b === "string") return trunc(b);
      if (b instanceof URLSearchParams) return trunc(b.toString());
      if (b instanceof FormData) {
        var o = {};
        b.forEach(function (v, k) { o[k] = typeof v === "string" ? v : "[file]"; });
        return trunc(o);
      }
      return "[" + (b.constructor && b.constructor.name) + "]";
    }
    function abs(u) { try { return new URL(u, location.href).href; } catch (e) { return String(u); } }
    function isStatic(u) { return /\.(js|css|png|jpe?g|gif|svg|webp|woff2?|ttf|ico|mp3|wav)(\?|$)/i.test(u); }

    rec("load", { url: location.href, title: document.title });

    // network
    var origFetch = window.fetch;
    if (origFetch) {
      window.fetch = function (input, init) {
        var url = abs(typeof input === "string" || input instanceof URL ? input : input.url);
        var method = ((init && init.method) || (input && input.method) || "GET").toUpperCase();
        var reqBody = bodyStr(init && init.body);
        var p = origFetch.apply(this, arguments);
        if (!isStatic(url)) {
          p.then(function (r) {
            var e = { via: "fetch", method: method, url: url, status: r.status, req: reqBody };
            r.clone().text().then(function (t) { e.res = trunc(t); rec("net", e); },
                                  function () { rec("net", e); });
          }, function (err) { rec("net", { via: "fetch", method: method, url: url, error: String(err) }); });
        }
        return p;
      };
    }
    var X = XMLHttpRequest.prototype, xOpen = X.open, xSend = X.send;
    X.open = function (m, u) { this.__r = { method: String(m).toUpperCase(), url: abs(u) }; return xOpen.apply(this, arguments); };
    X.send = function (b) {
      var x = this, r = x.__r;
      if (r && !isStatic(r.url)) {
        r.req = bodyStr(b);
        x.addEventListener("loadend", function () {
          var res = null;
          try { res = x.responseType === "" || x.responseType === "text" ? x.responseText : x.responseType === "json" ? x.response : "[" + x.responseType + "]"; } catch (e) {}
          rec("net", { via: "xhr", method: r.method, url: r.url, status: x.status, req: r.req, res: trunc(res) });
        });
      }
      return xSend.apply(this, arguments);
    };
    if (navigator.sendBeacon) {
      var beacon = navigator.sendBeacon.bind(navigator);
      navigator.sendBeacon = function (u, d) {
        rec("net", { via: "beacon", method: "POST", url: abs(u), req: bodyStr(d) });
        return beacon(u, d);
      };
    }

    // storage
    ["setItem", "removeItem", "clear"].forEach(function (fn) {
      var orig = Storage.prototype[fn];
      Storage.prototype[fn] = function (k, v) {
        if (k !== KEY) {
          rec("storage", {
            store: this === window.localStorage ? "local" : "session",
            op: fn, key: fn === "clear" ? null : k, value: fn === "setItem" ? trunc(v) : undefined,
          });
        }
        return orig.apply(this, arguments);
      };
    });

    // cookies
    var cd = Object.getOwnPropertyDescriptor(Document.prototype, "cookie");
    if (cd && cd.set) {
      Object.defineProperty(document, "cookie", {
        configurable: true,
        get: function () { return cd.get.call(document); },
        set: function (v) { rec("cookie", { value: trunc(v) }); cd.set.call(document, v); },
      });
    }

    // programmatic events (anything the page dispatches itself)
    var NOISE = /^(mouse|pointer|touch|focus|blur|scroll|resize|key|wheel|animation|transition|load|error|readystatechange|visibilitychange|input|change|select)/i;
    var dispatch = EventTarget.prototype.dispatchEvent;
    EventTarget.prototype.dispatchEvent = function (ev) {
      if (ev && !NOISE.test(ev.type)) {
        var t = this, label = t === window ? "window" : t === document ? "document"
          : t && t.tagName ? t.tagName.toLowerCase() + (t.id ? "#" + t.id : "") : String(t && t.constructor && t.constructor.name);
        rec("event", { type: ev.type, target: label, cls: ev.constructor && ev.constructor.name, detail: trunc(ev.detail) });
      }
      return dispatch.apply(this, arguments);
    };
    window.addEventListener("message", function (ev) {
      rec("message", { origin: ev.origin, data: trunc(ev.data) });
    });

    // history
    ["pushState", "replaceState"].forEach(function (fn) {
      var orig = history[fn];
      history[fn] = function (s, t, u) {
        rec("history", { op: fn, url: u == null ? null : abs(u), state: trunc(s) });
        return orig.apply(this, arguments);
      };
    });
    window.addEventListener("hashchange", function () { rec("history", { op: "hashchange", url: location.href }); });

    // analytics dataLayer (gtag/GTM); games often push "level_complete" etc.
    var wrapped = null;
    setInterval(function () {
      var dl = window.dataLayer;
      if (!dl || dl === wrapped || typeof dl.push !== "function") return;
      wrapped = dl;
      dl.forEach(function (e) { rec("dataLayer", { entry: trunc(e && e.length !== undefined ? Array.prototype.slice.call(e) : e) }); });
      var push = dl.push;
      dl.push = function () {
        for (var i = 0; i < arguments.length; i++) {
          var e = arguments[i];
          rec("dataLayer", { entry: trunc(e && e.length !== undefined ? Array.prototype.slice.call(e) : e) });
        }
        return push.apply(this, arguments);
      };
    }, 300);

    function size(s) { return s == null ? "-" : String(s).length + "B"; }
    window.__dgbRec = {
      entries: entries,
      mark: function (label) { rec("mark", { label: label }); save(); return entries.length - 1; },
      get: function (i) { return entries[i]; },
      clear: function () { entries.length = 0; save(); },
      summary: function (opts) {
        opts = opts || {};
        var re = opts.grep ? new RegExp(opts.grep, "i") : null;
        var out = [];
        entries.forEach(function (e, i) {
          if (opts.kind && e.kind !== opts.kind) return;
          if (opts.from != null && i < opts.from) return;
          var line;
          switch (e.kind) {
            case "net": line = e.via + " " + e.method + " " + e.url + " -> " + (e.status != null ? e.status : e.error || "") + " req:" + size(e.req) + " res:" + size(e.res); break;
            case "storage": line = e.store + "." + e.op + " " + e.key + " " + size(e.value); break;
            case "cookie": line = String(e.value).slice(0, 120); break;
            case "event": line = e.type + " on " + e.target + " (" + e.cls + ")" + (e.detail != null ? " detail:" + String(e.detail).slice(0, 120) : ""); break;
            case "dataLayer": line = String(e.entry).slice(0, 200); break;
            case "message": line = e.origin + " " + String(e.data).slice(0, 120); break;
            case "history": line = e.op + " " + e.url; break;
            case "mark": line = "=== " + e.label + " ==="; break;
            default: line = e.url || "";
          }
          var full = "#" + i + " " + e.at.slice(11, 19) + " [" + e.kind + "] " + line;
          if (!re || re.test(full) || re.test(JSON.stringify(e))) out.push(full);
        });
        return out.join("\n");
      },
      storageKeys: function () {
        var seen = {};
        entries.forEach(function (e) { if (e.kind === "storage" && e.key) seen[e.store + ":" + e.key] = (seen[e.store + ":" + e.key] || 0) + 1; });
        return seen;
      },
      // grep: optional regex on keys, e.g. storage("game|puzzle|stat")
      storage: function (grep) {
        var re = grep ? new RegExp(grep, "i") : null;
        var dump = function (s) { var o = {}; if (!s) return o; for (var i = 0; i < s.length; i++) { var k = s.key(i); if (k !== KEY && (!re || re.test(k))) o[k] = trunc(s.getItem(k)); } return o; };
        return { local: dump(localStorage), session: dump(ss), cookies: document.cookie };
      },
    };
  });
  return "recorder installed; navigate or reload the game page to start recording";
}
