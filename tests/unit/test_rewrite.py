from mitmproxy import http
from mitmproxy.test import tutils

from src.proxy import rewrite


def _response(content: bytes, content_type: str = "text/html") -> http.Response:
    response = tutils.tresp(content=content)
    response.headers["content-type"] = content_type
    return response


def test_localize_cookies() -> None:
    response = _response(b"")
    response.headers.set_all(
        "set-cookie",
        [
            "a=1; Domain=.example.com; Secure; Path=/",
            "__Host-b=2; Secure; Path=/",
        ],
    )
    rewrite.localize_cookies(response)
    assert response.headers.get_all("set-cookie") == [
        "a=1; Path=/",
        "__Host-b=2; Secure; Path=/",
    ]


def test_origin_rewriter_rewrites_text_and_redirects() -> None:
    rewriter = rewrite.OriginRewriter("https://example.com", "http://localhost:8099")
    response = _response(
        b'<a href="https://example.com/x">'
        b'{"u":"https:\\/\\/example.com\\/y"}'
        b'"https:\\u002F\\u002Fexample.com"'
    )
    response.headers["location"] = "https://example.com/moved?q=1"
    rewriter.apply(response)
    assert response.content == (
        b'<a href="http://localhost:8099/x">'
        b'{"u":"http:\\/\\/localhost:8099\\/y"}'
        b'"http:\\u002F\\u002Flocalhost:8099"'
    )
    assert response.headers["location"] == "http://localhost:8099/moved?q=1"


def test_origin_rewriter_leaves_binary_and_other_hosts() -> None:
    rewriter = rewrite.OriginRewriter("https://example.com", "http://localhost:8099")
    image = _response(b"https://example.com", "image/png")
    rewriter.apply(image)
    assert image.content == b"https://example.com"
    other = _response(b"")
    other.headers["location"] = "https://example.com.evil/"
    rewriter.apply(other)
    assert other.headers["location"] == "https://example.com.evil/"


def test_foreign_host_router() -> None:
    router = rewrite.ForeignHostRouter(
        "https://game.com", "http://localhost:8099", ["api.game.com"]
    )
    request = tutils.treq(path=b"/__host/api.game.com/v1/day?x=1")
    request.headers["origin"] = "http://localhost:8099"
    router.route(request)
    assert request.url == "https://api.game.com/v1/day?x=1"
    assert request.headers["origin"] == "https://game.com"

    untouched = tutils.treq(path=b"/__host/other.com/v1")
    router.route(untouched)
    assert untouched.path == "/__host/other.com/v1"

    response = _response(b'fetch("https://api.game.com/v1")', "text/javascript")
    router.apply(response)
    assert response.content == b'fetch("http://localhost:8099/__host/api.game.com/v1")'
