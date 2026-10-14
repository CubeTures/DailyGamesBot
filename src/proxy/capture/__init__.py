"""Result capture: the script injected into game pages, and the /__dgb/
endpoints it reports to on the game's own local origin."""

PATH_PREFIX = "/__dgb/"
SCRIPT_PATH = PATH_PREFIX + "capture.js"
RESULT_PATH = PATH_PREFIX + "result"
ENTER_PATH = PATH_PREFIX + "enter"

# Holds the player's /play token, on the launcher's host and on each game's.
TOKEN_COOKIE = "dgb_token"
_COOKIE_MAX_AGE_SECS = 365 * 24 * 60 * 60


def token_cookie(token: str) -> str:
    """A Set-Cookie value remembering the token on the host it's sent from."""
    return (
        f"{TOKEN_COOKIE}={token}; Path=/; HttpOnly;"
        f" Max-Age={_COOKIE_MAX_AGE_SECS}; SameSite=Lax"
    )
