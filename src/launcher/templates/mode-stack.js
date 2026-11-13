// A game's modes as a stack of cards (or scoreboards): the mode showing on
// top, the next one peeking out behind, the rest hidden. However many modes
// there are, the stack is two deep: switching quietly makes the card behind
// the mode picked, then shuffles the front one behind it. Each item in a
// stack is an element with data-game; its .modes holds the switcher pill.
// app.js decides which modes a stack shows and wires up the events.
var modeStack = (function () {
  var CHECK = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg>';
  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  // Per element: a stack's {modes, opts} from layout(), a pill's key from
  // fillPill(), an item's running shuffle animation.
  var state = new WeakMap();

  function get(node) {
    var s = state.get(node);
    if (!s) state.set(node, s = {});
    return s;
  }

  function items(stack) {
    return Array.prototype.filter.call(stack.children, function (node) { return node.dataset.game; });
  }

  function item(stack, game) {
    return items(stack).filter(function (node) { return node.dataset.game === game; })[0];
  }

  function front(stack) {
    return items(stack).filter(function (node) { return node.dataset.depth === "0"; })[0];
  }

  function after(modes, game) {
    return modes[(modes.indexOf(game) + 1) % modes.length];
  }

  // Only the front item can be used: the others are out of the tab order
  // and hidden from screen readers. Their clicks go to the stack itself.
  function setDepth(node, depth) {
    node.dataset.depth = depth;
    node.setAttribute("aria-hidden", String(depth !== "0"));
    node.querySelectorAll("a, button:not(.mode)").forEach(function (control) {
      if (depth === "0") control.removeAttribute("tabindex");
      else control.tabIndex = -1;
    });
  }

  // The pill names the item's own mode; the others are just a badge
  // each, a green check once `isDone` says the viewer has played it. A
  // stack showing one mode still has its pill, naming that mode.
  function fillPill(node, modes, opts) {
    var pill = node.querySelector(".modes");
    if (!pill) return;
    // Unchanged pills are left alone, so a focused button stays focused.
    var key = node.dataset.depth + "|" + modes.map(function (game) {
      return game + (opts.isDone(game) ? "+" : "");
    }).join(",");
    if (get(pill).key === key) return;
    get(pill).key = key;
    var hadFocus = pill.contains(document.activeElement);
    pill.hidden = !modes.length;
    pill.textContent = "";
    modes.forEach(function (game) {
      var current = game === node.dataset.game;
      var done = opts.isDone(game);
      var name = opts.modeName(game);
      var button = document.createElement("button");
      button.type = "button";
      button.className = "mode" + (current ? " is-current" : "") + (done ? " is-done" : "");
      button.dataset.game = game;
      button.setAttribute("role", "tab");
      button.setAttribute("aria-selected", String(current));
      button.tabIndex = current && node.dataset.depth === "0" ? 0 : -1;
      button.title = name + (done ? ", played" : "");
      button.setAttribute("aria-label", button.title);
      button.innerHTML = '<span class="badge">' + CHECK + '</span><span class="label"></span>';
      button.querySelector(".label").textContent = name;
      pill.appendChild(button);
      if (hadFocus && current) button.focus({ preventScroll: true });
    });
  }

  // Shows `top` (or the first of `modes` if it isn't one) on top and the
  // mode after it behind. With one mode it's a plain card; with none the
  // stack is hidden. `opts` gives isDone(game) and modeName(game).
  function layout(stack, modes, top, opts) {
    get(stack).modes = modes;
    get(stack).opts = opts;
    if (modes.indexOf(top) < 0) top = modes[0];
    stack.hidden = !modes.length;
    stack.classList.toggle("stacked", modes.length > 1);
    var back = modes.length > 1 ? after(modes, top) : null;
    items(stack).forEach(function (node) {
      var game = node.dataset.game;
      if (get(node).shuffle) get(node).shuffle.cancel();
      setDepth(node, game === top ? "0" : game === back ? "1" : "none");
      fillPill(node, modes, opts);
    });
  }

  // Brings `game` to the top. The front item flies off towards `dir` (1 for
  // left, -1 for right), drops behind, and settles where the back one was.
  function shuffle(stack, game, dir) {
    var modes = get(stack).modes, opts = get(stack).opts;
    var leaving = front(stack), coming = item(stack, game);
    if (!modes || modes.indexOf(game) < 0 || !leaving || !coming || leaving === coming) return;
    if (reduceMotion.matches || !leaving.animate) {
      layout(stack, modes, game, opts);
      return;
    }
    if (get(leaving).shuffle) get(leaving).shuffle.cancel();
    // Set dressing: whatever was behind becomes the mode picked.
    items(stack).forEach(function (node) {
      if (node !== leaving && node !== coming) setDepth(node, "none");
    });
    if (coming.dataset.depth !== "1") {
      coming.style.transition = "none";
      setDepth(coming, "1");
      void coming.offsetWidth;
      coming.style.transition = "";
    }
    var start = getComputedStyle(leaving).transform;
    leaving.style.transition = "none";
    leaving.style.transform = "";
    leaving.classList.remove("dragging");
    setDepth(coming, "0");
    setDepth(leaving, "1");
    var end = getComputedStyle(leaving).transform;
    var out = "translate(" + (-dir * 70) + "%, -18px) rotate(" + (-dir * 10) + "deg)";
    leaving.classList.add("flying");
    var animation = leaving.animate([
      { transform: start, zIndex: 3, easing: "cubic-bezier(0.3, 0.6, 0.35, 1)" },
      { transform: out, zIndex: 3, offset: 0.44 },
      { transform: out, zIndex: 0, offset: 0.45, easing: "cubic-bezier(0.25, 0.9, 0.3, 1.05)" },
      { transform: end, zIndex: 0 },
    ], { duration: 620 });
    get(leaving).shuffle = animation;
    var settle = function () {
      get(leaving).shuffle = null;
      leaving.style.transition = "";
      leaving.classList.remove("flying");
    };
    animation.oncancel = settle;
    animation.onfinish = function () {
      settle();
      // Behind now: the mode after the one on top, which it already is
      // unless there are three or more.
      layout(stack, get(stack).modes, front(stack).dataset.game, get(stack).opts);
    };
    // Focus follows a switch made from the pill.
    if (stack.contains(document.activeElement) && document.activeElement.classList.contains("mode")) {
      var pillButton = coming.querySelector('.mode[data-game="' + game + '"]');
      if (pillButton) {
        pillButton.tabIndex = 0;
        pillButton.focus({ preventScroll: true });
      }
    }
  }

  // The modes the stack shows, in order, as last laid out.
  function modes(stack) {
    return get(stack).modes || [];
  }

  return {
    layout: layout,
    shuffle: shuffle,
    front: front,
    modes: modes,
  };
})();
