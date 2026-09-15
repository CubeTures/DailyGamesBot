"""Single source of truth for which local port maps to which game."""

LAUNCHER_PORT = 8090

# port -> (name, origin)
GAMES = {
    8081: ("wordle", "https://www.nytimes.com"),
    8082: ("fermi", "https://fermi.gg"),
    8083: ("minutecryptic", "https://www.minutecryptic.com"),
    8084: ("krillion", "https://krillion.io"),
}

# Path appended to the local URL so the launcher lands directly on the game.
LANDING_PATH = {
    "wordle": "/games/wordle/index.html",
    "fermi": "/",
    "minutecryptic": "/",
    "krillion": "/",
}
