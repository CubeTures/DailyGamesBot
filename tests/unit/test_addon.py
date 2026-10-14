from mitmproxy import http
from mitmproxy.test import tflow

from src.proxy import addon
from src.store import players


def _request_to(host: str, path: str = "/", token: str | None = "") -> http.HTTPFlow:
    """A request, by default from player 42 with their current token."""
    if token == "":
        token = players.token_for("42")
    flow = tflow.tflow()
    flow.request.scheme, flow.request.host, flow.request.port = "http", "x", 8090
    flow.request.path = path
    flow.request.headers["host"] = host
    flow.request.headers["cookie"] = (
        f"dgb_token={token}; theirs=1" if token else "theirs=1"
    )
    addon.request(flow)
    return flow


def _is_404(flow: http.HTTPFlow) -> bool:
    return (
        flow.request.host == "x"
        and flow.response is not None
        and flow.response.status_code == 404
    )


def test_routes_game_subdomain_to_its_origin() -> None:
    flow = _request_to("wordle.localhost:8080", "/games/wordle/index.html")
    request = flow.request
    assert (request.scheme, request.host, request.port) == (
        "https",
        "www.nytimes.com",
        443,
    )
    assert request.headers["host"] == "www.nytimes.com"
    assert request.path == "/games/wordle/index.html"
    assert dict(request.cookies) == {"theirs": "1"}


def test_answers_capture_paths_on_game_subdomain() -> None:
    flow = _request_to("wordle.localhost:8080", "/__dgb/capture.js")
    assert flow.response is not None and flow.response.status_code == 200
    assert flow.request.host == "x"


def test_leaves_launcher_host_to_the_launcher() -> None:
    for host in ("localhost:8080", "LOCALHOST:8080", "localhost"):
        flow = _request_to(host)
        assert flow.request.host == "x"
        assert flow.response is None


def test_answers_unknown_hosts_with_404() -> None:
    for host in ("nope.localhost:8080", "wordle.example.com", "127.0.0.1:8080", ""):
        assert _is_404(_request_to(host))


def test_answers_games_with_404_without_a_working_token() -> None:
    old = players.token_for("7")
    players.reset_token("7")
    for token in (None, "x", old):
        for path in ("/games/wordle/index.html", "/__dgb/capture.js"):
            assert _is_404(_request_to("wordle.localhost:8080", path, token))


def test_lets_enter_through_without_a_token_cookie() -> None:
    token = players.token_for("42")
    flow = _request_to(
        "wordle.localhost:8080", f"/__dgb/enter?token={token}&to=/x", None
    )
    assert flow.response is not None and flow.response.status_code == 302
