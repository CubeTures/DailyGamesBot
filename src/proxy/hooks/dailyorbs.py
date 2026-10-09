"""Daily Orbs fetches its puzzles and game day from a separate API host."""

from src.proxy.hooks import route_foreign_hosts

request, response = route_foreign_hosts("dailyorbs", ["api.dailyorbs.com"])
