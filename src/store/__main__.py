"""Admin tasks on the store. Reset a player's /play link, e.g. after it
leaked, so the old one stops working and their next /play gets a new one:
`uv run python3 -m src.store reset-token DISCORD_ID`."""

import argparse
import sys

from src.store import players


def main() -> None:
    parser = argparse.ArgumentParser(prog="python3 -m src.store")
    commands = parser.add_subparsers(dest="command", required=True)
    reset = commands.add_parser("reset-token", help="invalidate a player's link")
    reset.add_argument("discord_id")
    args = parser.parse_args()
    if players.reset_token(args.discord_id):
        print(f"reset {args.discord_id}'s link; their next /play gets a new one")
    else:
        sys.exit(f"{args.discord_id} has no link to reset")


if __name__ == "__main__":
    main()
