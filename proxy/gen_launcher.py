"""Regenerate launcher/index.html from proxy/config.py."""

from pathlib import Path

from proxy.config import GAMES, LANDING_PATH

CARD_TEMPLATE = """    <a class="card" href="http://localhost:{port}{path}" target="_blank" rel="noopener">
      <h2>{title}</h2>
      <p>localhost:{port}</p>
    </a>
"""

PAGE_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>word-game-bot launcher</title>
<style>
  body {{ font-family: sans-serif; background: #111; color: #eee; margin: 0; padding: 2rem; }}
  h1 {{ margin-top: 0; }}
  .grid {{ display: flex; flex-wrap: wrap; gap: 1rem; }}
  .card {{ display: block; width: 220px; padding: 1.25rem; border-radius: 8px;
           background: #222; color: inherit; text-decoration: none; border: 1px solid #333; }}
  .card:hover {{ border-color: #666; }}
  .card h2 {{ margin: 0 0 0.5rem; font-size: 1.1rem; }}
  .card p {{ margin: 0; color: #888; font-size: 0.85rem; }}
</style>
</head>
<body>
  <h1>word-game-bot</h1>
  <div class="grid">
{cards}  </div>
</body>
</html>
"""


def build() -> str:
    cards = "".join(
        CARD_TEMPLATE.format(port=port, path=LANDING_PATH[name], title=name.title())
        for port, (name, _origin) in sorted(GAMES.items())
    )
    return PAGE_TEMPLATE.format(cards=cards)


if __name__ == "__main__":
    out = Path(__file__).resolve().parent.parent / "launcher" / "index.html"
    out.write_text(build())
    print(f"wrote {out}")
