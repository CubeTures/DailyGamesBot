"""What a game driver uses to play: a Player in its own browser context, with
its own Discord ID, whose results land in the test session's database."""

import contextlib
import json
import sqlite3
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from playwright.sync_api import BrowserContext, Frame, Locator, Page

from src.games.models import Game
from src.settings import LAUNCHER_URL

# The day's solution, as a driver's learn() found it. Cached as JSON.
Solution = dict[str, Any]
# Expected result fields: plain values or expect.Check.
Expected = dict[str, Any]


@dataclass(frozen=True)
class Row:
    puzzle_id: str
    game_day: str
    trigger: str
    data: dict[str, Any]


class NoResult(AssertionError):
    pass


@dataclass
class Player:
    game: Game
    discord_id: str
    context: BrowserContext
    page: Page
    db_path: Path
    console: list[str] = field(default_factory=lambda: [])

    def url(self, path: str | None = None) -> str:
        return f"http://localhost:{self.game.port}{path or self.game.landing_path}"

    def open(self, path: str | None = None) -> Page:
        """Visit the launcher as this player (setting the dgb_discord_id
        cookie, as a /play link does), then the game."""
        self.page.goto(f"{LAUNCHER_URL}/?discord_id={self.discord_id}")
        self.page.wait_for_function("document.cookie.includes('dgb_discord_id=')")
        self.page.goto(self.url(path), wait_until="domcontentloaded")
        return self.page

    def dismiss(self, *locators: Locator) -> None:
        """Click each of these away whenever it shows up (ads, welcome and
        help modals), before any other action."""
        for locator in locators:
            self.page.add_locator_handler(locator, _click_away, no_wait_after=True)

    def capture_frames(self) -> list[Frame]:
        """The frames running the capture script (Bracket City has two)."""
        found: list[Frame] = []
        for frame in self.page.frames:
            try:
                if frame.evaluate("!!window.__dgb"):
                    found.append(frame)
            except Exception:
                pass
        return found

    def status(self) -> list[dict[str, Any]]:
        """__dgb.status() and __dgb.dryRun() from every capturing frame."""
        out: list[dict[str, Any]] = []
        for frame in self.capture_frames():
            try:
                out.append(
                    frame.evaluate(
                        "({url: location.href, ...__dgb.status(),"
                        " dryRun: __dgb.dryRun()})"
                    )
                )
            except Exception as e:
                out.append({"url": frame.url, "error": repr(e)})
        return out

    def rows(self) -> list[Row]:
        if not self.db_path.exists():
            return []
        conn = sqlite3.connect(self.db_path)
        try:
            found = conn.execute(
                "SELECT puzzle_id, game_day, trigger, data FROM results"
                " WHERE game = ? AND discord_id = ?",
                (self.game.name, self.discord_id),
            ).fetchall()
        except sqlite3.OperationalError:
            return []  # no results table until the first save
        finally:
            conn.close()
        return [Row(p, d, t, json.loads(data)) for p, d, t, data in found]

    def wait_for_result(self, timeout: float = 30) -> Row:
        """The row this player's play saved, once it's there."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            found = self.rows()
            if found:
                return found[0]
            self.page.wait_for_timeout(500)
        raise NoResult(
            f"no {self.game.name} result saved for {self.discord_id} within"
            f" {timeout:.0f}s.\n__dgb state per frame:\n"
            + json.dumps(self.status(), indent=2, ensure_ascii=False)[:6000]
        )

    def assert_no_result(self, wait: float = 4) -> None:
        """Nothing was saved (for a game left unfinished)."""
        self.page.wait_for_timeout(wait * 1000)
        assert not self.rows(), f"unexpected result: {self.rows()}"


def _click_away(locator: Locator) -> None:
    # Overlays animate in and out; one that's gone by now is fine.
    with contextlib.suppress(Exception):
        locator.first.click(timeout=3000)


# A scenario plays the game to one outcome and returns the fields the saved
# result should have.
Scenario = Callable[[Player, Solution], Expected]


@dataclass(frozen=True)
class Driver:
    name: str  # games/<name>
    scenarios: dict[str, Scenario]
    # Finds the day's solution, playing in its own context if it has to.
    # None for games whose scenarios need no solution.
    learn: Callable[[Player], Solution] | None = None
    # Scenarios that fail because of a known capture bug: scenario -> why.
    # They run as strict xfails, so fixing the bug flags them to move back.
    known_failures: dict[str, str] = field(default_factory=lambda: {})
