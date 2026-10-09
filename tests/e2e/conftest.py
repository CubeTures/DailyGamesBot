"""Fixtures for the live tests: the proxy (on a scratch database), a browser,
and players, each in a fresh browser context with its own Discord ID.

When a test fails, everything a player saw is saved under
tests/e2e/.artifacts/<test>/<player>/: a Playwright trace (open with
`uv run playwright show-trace trace.zip`), a screenshot, the page's console,
and __dgb.status() / dryRun() from every frame running the capture script.
"""

import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
from collections.abc import Callable, Generator
from pathlib import Path
from typing import cast

import pytest
from playwright.sync_api import Browser, sync_playwright

from src.games.registry import GAMES_BY_NAME
from src.settings import LAUNCHER_PORT, PROXY_PORT, REPO_ROOT
from tests.e2e.harness import Player

ARTIFACTS_DIR = Path(__file__).with_name(".artifacts")

# Discord IDs are digits (the launcher checks); a per-session base keeps
# reruns of the same test apart in the launcher's player list.
_ID_BASE = 900_000_000_000_000_000 + (int(time.time()) % 1_000_000) * 1000


def _port_open(port: int) -> bool:
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


@pytest.fixture(scope="session")
def db_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return tmp_path_factory.mktemp("dgb") / "results.db"


@pytest.fixture(scope="session")
def proxy(db_path: Path) -> Generator[None]:
    """`python -m src.proxy`, saving to `db_path`."""
    ports = [LAUNCHER_PORT, PROXY_PORT]
    if busy := [p for p in ports if _port_open(p)]:
        pytest.exit(
            f"ports {busy} are in use; stop the running proxy first"
            " (pkill -TERM -f -- '-m [s]rc\\.proxy$')",
            returncode=1,
        )
    ARTIFACTS_DIR.mkdir(exist_ok=True)
    log = (ARTIFACTS_DIR / "proxy.log").open("w")
    process = subprocess.Popen(
        [sys.executable, "-m", "src.proxy"],
        cwd=REPO_ROOT,
        env={**os.environ, "DGB_DB_PATH": str(db_path)},
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    try:
        deadline = time.monotonic() + 60
        while not all(_port_open(p) for p in ports):
            if process.poll() is not None:
                pytest.exit(f"proxy exited early; see {log.name}", returncode=1)
            if time.monotonic() > deadline:
                pytest.exit(f"proxy didn't start in 60s; see {log.name}", returncode=1)
            time.sleep(0.5)
        yield
    finally:
        process.terminate()
        try:
            process.wait(10)
        except subprocess.TimeoutExpired:
            process.kill()
        log.close()


@pytest.fixture(scope="session")
def browser(pytestconfig: pytest.Config) -> Generator[Browser]:
    with sync_playwright() as p:
        browser = p.chromium.launch(
            channel="chrome",
            headless=not pytestconfig.getoption("headed"),
            # Some sites refuse automated browsers outright.
            args=["--disable-blink-features=AutomationControlled"],
        )
        try:
            yield browser
        finally:
            browser.close()


# Ad and tracker hosts: blocked so ads can't cover the game or slow it down.
_ADS = re.compile(
    r"^https?://([^/]*\.)?(doubleclick\.net|googlesyndication\.com"
    r"|googletagservices\.com|amazon-adsystem\.com|adnxs\.com|rubiconproject\.com"
    r"|pubmatic\.com|criteo\.com|taboola\.com|outbrain\.com|adsafeprotected\.com"
    r"|moatads\.com|scorecardresearch\.com|casalemedia\.com|openx\.net"
    r"|advertising\.com|indexww\.com|3lift\.com|media\.net)/"
)

_FAILED = pytest.StashKey[bool]()


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(
    item: pytest.Item, call: pytest.CallInfo[None]
) -> Generator[None, pytest.TestReport, pytest.TestReport]:
    report = yield
    # Read by the players fixture to decide whether to keep artifacts.
    item.stash.setdefault(_FAILED, False)
    if report.failed:
        item.stash[_FAILED] = True
    return report


PlayerFactory = Callable[[str, str], Player]


def _user_agent(browser: Browser) -> str:
    # Headless Chrome says "HeadlessChrome" in its user agent, which some
    # sites block; claim to be the regular browser instead.
    return (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko)"
        f" Chrome/{browser.version} Safari/537.36"
    )


@pytest.fixture
def players(
    request: pytest.FixtureRequest, proxy: None, browser: Browser, db_path: Path
) -> Generator[PlayerFactory]:
    """players(game, label): a new player of `game` in a fresh context."""
    made: list[tuple[str, Player]] = []

    def make(game: str, label: str) -> Player:
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            locale="en-US",
            user_agent=_user_agent(browser),
        )
        context.route(_ADS, lambda route: route.abort())
        context.tracing.start(screenshots=True, snapshots=True, sources=False)
        page = context.new_page()
        player = Player(
            game=GAMES_BY_NAME[game],
            discord_id=str(_ID_BASE + len(made) + 100 * _test_index(request)),
            context=context,
            page=page,
            db_path=db_path,
        )
        page.on("console", lambda m: player.console.append(f"[{m.type}] {m.text}"))
        page.on("pageerror", lambda e: player.console.append(f"[pageerror] {e}"))
        made.append((label, player))
        return player

    yield make

    node = cast(pytest.Item, request.node)
    keep = node.stash.get(_FAILED, False) or bool(
        request.config.getoption("keep_artifacts")
    )
    test_dir = ARTIFACTS_DIR / re.sub(r"[^\w.-]+", "_", node.name)
    shutil.rmtree(test_dir, ignore_errors=True)
    for label, player in made:
        try:
            if keep:
                _save_artifacts(test_dir / label, player)
            else:
                player.context.tracing.stop()
        finally:
            player.context.close()


_test_counter: dict[str, int] = {}


def _test_index(request: pytest.FixtureRequest) -> int:
    node = cast(pytest.Item, request.node)
    return _test_counter.setdefault(node.nodeid, len(_test_counter))


def _save_artifacts(directory: Path, player: Player) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    player.context.tracing.stop(path=directory / "trace.zip")
    try:
        player.page.screenshot(path=directory / "screenshot.png", full_page=True)
    except Exception as e:
        (directory / "screenshot-error.txt").write_text(repr(e))
    (directory / "console.log").write_text("\n".join(player.console))
    info = {
        "discord_id": player.discord_id,
        "url": player.page.url,
        "rows": [r.__dict__ for r in player.rows()],
        "frames": player.status(),
    }
    (directory / "status.json").write_text(
        json.dumps(info, indent=2, ensure_ascii=False, default=str)
    )
