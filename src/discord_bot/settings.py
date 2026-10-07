"""The bot's environment settings, from .env or the process environment."""

import os

from dotenv import load_dotenv


def bot_token() -> str:
    load_dotenv()
    return os.environ["DISCORD_BOT_TOKEN"]


def results_channel_id() -> int | None:
    """The channel results are announced in, or None to not announce them."""
    load_dotenv()
    raw = os.environ.get("DISCORD_RESULTS_CHANNEL_ID", "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        raise SystemExit(
            f"DISCORD_RESULTS_CHANNEL_ID must be a channel ID, got {raw!r}"
        ) from None
