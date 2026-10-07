"""Runs the game proxy and launcher page without the Discord bot:
`uv run python3 -m src.proxy`.

Useful when developing a game config (see the add-game skill), since it
needs no DISCORD_BOT_TOKEN.
"""

import asyncio
from contextlib import suppress

from src.launcher.server import serve_launcher
from src.proxy.mitmdump import run_mitmdump


def main() -> None:
    with suppress(KeyboardInterrupt), serve_launcher():
        asyncio.run(run_mitmdump())


if __name__ == "__main__":
    main()
