from mitmproxy import http
from mitmproxy.test import tflow

from src.proxy import addon


def _request_to(host: str, path: str = "/") -> http.HTTPFlow:
    flow = tflow.tflow()
    flow.request.scheme, flow.request.host, flow.request.port = "http", "x", 8090
    flow.request.path = path
    flow.request.headers["host"] = host
    flow.request.headers["cookie"] = "dgb_discord_id=42; theirs=1"
    addon.request(flow)
    return flow


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


def test_leaves_other_hosts_to_the_launcher() -> None:
    for host in ("localhost:8080", "nope.localhost:8080", "wordle.example.com"):
        flow = _request_to(host)
        assert flow.request.host == "x"
        assert flow.response is None
