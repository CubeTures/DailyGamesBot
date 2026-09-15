"""Regenerate launcher/index.html from proxy/config.py."""

from pathlib import Path

from src.proxy.config import GAMES, LANDING_PATH

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

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

    if (!discordId) {{
      document.getElementById("warning").style.display = "flex";
    }}
  }})();
</script>
</body>
</html>
"""


def build() -> str:
    cards = "".join(
        CARD_TEMPLATE.format(port=port, path=LANDING_PATH[name], title=name.title())
        for port, (name, _origin) in sorted(GAMES.items())
    )
    return PAGE_TEMPLATE.format(cards=cards)


def write() -> Path:
    out = REPO_ROOT / "launcher" / "index.html"
    out.write_text(build())
    return out


if __name__ == "__main__":
    print(f"wrote {write()}")
