import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("live", "live game tests (-m live)")
    group.addoption(
        "--headed", action="store_true", help="show the browser while playing"
    )
    group.addoption(
        "--keep-artifacts",
        action="store_true",
        help="save traces and screenshots for passing tests too",
    )
