"""Runs just the game proxy and launcher page, without the Discord bot.

    uv run python3 -m src.proxy

Useful when developing a game config (see the add-game skill), since it
needs no DISCORD_BOT_TOKEN.
"""

import asyncio

from src.proxy.runner import run_mitmproxy, start_launcher_server


def main() -> None:
    server = start_launcher_server()
    try:
        asyncio.run(run_mitmproxy())
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()


if __name__ == "__main__":
    main()
