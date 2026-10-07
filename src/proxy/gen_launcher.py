"""Regenerate launcher/index.html from proxy/config.py."""

import json
from pathlib import Path

from src.proxy.config import GAME_CONFIGS, REPO_ROOT

__all__ = ["REPO_ROOT", "build", "write"]

CARD_TEMPLATE = """    <a class="card" href="http://localhost:{port}{path}" target="_blank" rel="noopener">
      <h2>{title}</h2>
      <p>localhost:{port}</p>
    </a>
"""

PAGE_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Daily Games Bot launcher</title>
<style>
  body {{ font-family: sans-serif; background: #111; color: #eee; margin: 0; padding: 2rem; }}
  h1 {{ margin-top: 0; }}
  .grid {{ display: flex; flex-wrap: wrap; gap: 1rem; }}
  .card {{ display: block; width: 220px; padding: 1.25rem; border-radius: 8px;
           background: #222; color: inherit; text-decoration: none; border: 1px solid #333; }}
  .card:hover {{ border-color: #666; }}
  .card h2 {{ margin: 0 0 0.5rem; font-size: 1.1rem; }}
  .card p {{ margin: 0; color: #888; font-size: 0.85rem; }}
  #today {{ margin-top: 2.5rem; }}
  .board {{ width: 220px; padding: 1.25rem; border-radius: 8px;
            background: #222; border: 1px solid #333; }}
  .board h3 {{ margin: 0 0 0.75rem; font-size: 1rem; }}
  .board table {{ width: 100%; border-collapse: collapse; font-size: 0.9rem; }}
  .board td {{ padding: 0.25rem 0; }}
  .board td.rank {{ color: #888; width: 1.75rem; }}
  .board td.score {{ text-align: right; font-variant-numeric: tabular-nums; }}
  .board tr.me td {{ color: #8cf; }}
  .empty {{ color: #888; }}
  .warning {{
    display: none;
    position: fixed;
    inset: 0;
    z-index: 9999;
    background: #111;
    color: #eee;
    align-items: center;
    justify-content: center;
    text-align: center;
    padding: 2rem;
    font-size: 1.25rem;
  }}
</style>
</head>
<body>
  <div class="warning" id="warning">
    Run /play on the Daily Games Bot to get your link to play some games!
  </div>
  <h1>Daily Games Bot</h1>
  <div class="grid" id="grid">
{cards}  </div>
  <section id="today">
    <h2>Today's scores</h2>
    <div class="grid" id="boards"><p class="empty">Loading...</p></div>
  </section>
<script>
  (function () {{
    var params = new URLSearchParams(window.location.search);
    var discordId = params.get("discord_id");
    if (discordId) {{
      localStorage.setItem("discord_id", discordId);
      params.delete("discord_id");
      var query = params.toString();
      var newUrl =
        window.location.pathname + (query ? "?" + query : "") + window.location.hash;
      window.history.replaceState({{}}, "", newUrl);
    }} else {{
      discordId = localStorage.getItem("discord_id");
    }}

    if (discordId) {{
      // Games run on other localhost ports, which can't read this page's
      // localStorage but do share its cookies; the proxy reads this one when
      // a game reports a result.
      document.cookie = "dgb_discord_id=" + encodeURIComponent(discordId) +
        "; path=/; max-age=31536000; SameSite=Lax";
    }}

    if (!discordId) {{
      document.getElementById("warning").style.display = "flex";
    }}

    var gameTitles = {game_titles};

    function formatScore(d) {{
      var score = d.score === null || d.score === undefined ? null : d.score;
      var text;
      if (d.max_score !== undefined && d.max_score !== null) {{
        text = (score === null ? "X" : score) + "/" + d.max_score;
      }} else {{
        text = score === null ? "-" : String(score);
      }}
      if (d.won === false && score !== null) text += " \u2717";
      return text;
    }}

    // Lower is better for every game so far (Wordle guesses, Minute Cryptic
    // help over par); no score (a loss) sorts last, then earliest finish.
    function compare(a, b) {{
      var sa = a.data.score, sb = b.data.score;
      var na = typeof sa !== "number", nb = typeof sb !== "number";
      if (na !== nb) return na ? 1 : -1;
      if (!na && sa !== sb) return sa - sb;
      return a.captured_at < b.captured_at ? -1 : 1;
    }}

    function render(rows) {{
      var byGame = {{}};
      rows.forEach(function (r) {{ (byGame[r.game] = byGame[r.game] || []).push(r); }});
      var boards = document.getElementById("boards");
      boards.textContent = "";
      var games = Object.keys(byGame).sort(function (a, b) {{
        return (gameTitles[a] || a).localeCompare(gameTitles[b] || b);
      }});
      if (!games.length) {{
        var p = document.createElement("p");
        p.className = "empty";
        p.textContent = "Nobody has finished a game yet today.";
        boards.appendChild(p);
        return;
      }}
      games.forEach(function (game) {{
        var board = document.createElement("div");
        board.className = "board";
        var h = document.createElement("h3");
        h.textContent = gameTitles[game] || game;
        board.appendChild(h);
        var table = document.createElement("table");
        byGame[game].sort(compare).forEach(function (r, i) {{
          var tr = table.insertRow();
          if (r.discord_id === discordId) tr.className = "me";
          var cells = [
            ["rank", (i + 1) + "."],
            ["name", r.name || "Player \u2026" + r.discord_id.slice(-4)],
            ["score", formatScore(r.data)],
          ];
          cells.forEach(function (c) {{
            var td = tr.insertCell();
            td.className = c[0];
            td.textContent = c[1];
          }});
        }});
        board.appendChild(table);
        boards.appendChild(board);
      }});
    }}

    function refresh() {{
      var midnight = new Date();
      midnight.setHours(0, 0, 0, 0);
      fetch("/api/results?since=" + encodeURIComponent(midnight.toISOString()))
        .then(function (res) {{ return res.json(); }})
        .then(render)
        .catch(function () {{}});
    }}
    refresh();
    setInterval(refresh, 30000);
  }})();
</script>
</body>
</html>
"""


def build() -> str:
    cards = "".join(
        CARD_TEMPLATE.format(port=port, path=game.landing_path, title=game.title)
        for port, game in sorted(GAME_CONFIGS.items())
    )
    titles = {game.name: game.title for game in GAME_CONFIGS.values()}
    return PAGE_TEMPLATE.format(cards=cards, game_titles=json.dumps(titles))


def write() -> Path:
    out = REPO_ROOT / "launcher" / "index.html"
    out.write_text(build())
    return out


if __name__ == "__main__":
    print(f"wrote {write()}")
