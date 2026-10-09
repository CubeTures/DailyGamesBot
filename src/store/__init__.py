"""The SQLite store shared by the proxy, the launcher and the Discord bot.

They run in different processes (the proxy inside mitmdump), so they
coordinate through these tables rather than by calling each other: the proxy
saves results unannounced and marks the player's name stale, the launcher
saves role subscriptions unsynced, and the bot polls for both, acts on them
in Discord and marks them done. The bot also records which players are
admins, for the launcher to check.
"""
