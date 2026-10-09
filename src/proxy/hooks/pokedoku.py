"""PokeDoku fetches its puzzle API and Lottie animations from other hosts."""

from src.proxy.hooks import route_foreign_hosts

request, response = route_foreign_hosts(
    "pokedoku",
    ["api.pokedoku.com", "pokedoku-space.nyc3.cdn.digitaloceanspaces.com"],
)
