"""The daily test run: with DISCORD_ADMIN_CHANNEL_ID set, the bot runs the
unit tests and the live tests once a day and, only if any are degraded
(failed, errored, or the run itself broke), posts them in that channel with
the pytest output and the live tests' artifacts attached.

The report opens with a level: red if capturing is degraded (a live test's
capture went wrong, raising the harness's CaptureFailed, or a unit test
failed), yellow if only drivers are (a live test couldn't play its game, or a
run broke).

The live tests start their own proxy, so they run on ports of their own
(LIVE_PROXY_PORT, LIVE_LAUNCHER_PORT) beside the bot's. They need the dev
dependencies (`uv sync`) and the system Chrome, as when run by hand.
"""

import asyncio
import io
import logging
import os
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field
from datetime import UTC, time
from pathlib import Path

import discord

from src.settings import REPO_ROOT

# When the tests run each day. Live scenarios are skipped within 10 minutes
# of their game's reset, so it's away from midnight in the US.
RUN_AT = time(hour=12, tzinfo=UTC)
# The live tests' proxy and launcher, kept off the running ones' ports.
LIVE_PROXY_PORT = 18080
LIVE_LAUNCHER_PORT = 18090
# A run taking longer than this is stopped and reported.
RUN_TIMEOUT_SECS = 2 * 60 * 60
ARTIFACTS_DIR = REPO_ROOT / "tests" / "e2e" / ".artifacts"
# Discord's attachment limit is 10 MiB per message; keep under it.
MAX_ATTACHMENTS_BYTES = 9 * 1024 * 1024
MAX_MESSAGE_CHARS = 2000
# Report levels.
DRIVERS_DEGRADED = "\N{LARGE YELLOW CIRCLE}"
CAPTURE_DEGRADED = "\N{LARGE RED CIRCLE}"
# The start of a failure message raised by tests.e2e.harness.CaptureFailed.
CAPTURE_FAILED = "tests.e2e.harness.CaptureFailed"

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Degraded:
    test: str  # e.g. test_capture.py::test_capture[wordle-win]
    outcome: str  # "failed" or "error"
    message: str
    # Capturing is broken, not just a driver: see the module docstring.
    capture: bool = False


@dataclass
class SuiteRun:
    """One pytest invocation."""

    name: str  # "unit" or "live"
    returncode: int | None  # None: timed out
    output: str
    total: int = 0
    degraded: list[Degraded] = field(default_factory=lambda: [])

    @property
    def broken(self) -> str | None:
        """Why the run itself went wrong, beyond failing tests."""
        if self.returncode is None:
            return f"timed out after {RUN_TIMEOUT_SECS // 60} minutes"
        if self.returncode not in (0, 1) or (
            self.returncode == 1 and not self.degraded
        ):
            return f"pytest exited with code {self.returncode}"
        return None


def _environment(scratch: Path, live: bool) -> dict[str, str]:
    # Blank, not unset, so .env doesn't fill them back in: the unit tests
    # expect the default localhost URLs, and the live tests get ports of
    # their own. Nothing touches the real database.
    env = os.environ | {
        "DGB_PUBLIC_URL": "",
        "DGB_GAME_HOST": "",
        "DGB_PROXY_PORT": "",
        "DGB_LAUNCHER_PORT": "",
        "DGB_DB_PATH": str(scratch / "results.db"),
    }
    if live:
        env["DGB_PUBLIC_URL"] = f"http://localhost:{LIVE_PROXY_PORT}"
        env["DGB_LAUNCHER_PORT"] = str(LIVE_LAUNCHER_PORT)
    return env


async def run_suite(name: str, marker: str) -> SuiteRun:
    """Run the tests with `marker` in a pytest subprocess."""
    with tempfile.TemporaryDirectory() as scratch:
        junit = Path(scratch) / "junit.xml"
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            *("-m", "pytest", "-m", marker, "--color=no", "-rfE"),
            f"--junitxml={junit}",
            cwd=REPO_ROOT,
            env=_environment(Path(scratch), live=marker == "live"),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        try:
            stdout, _ = await asyncio.wait_for(process.communicate(), RUN_TIMEOUT_SECS)
            returncode = process.returncode
        except TimeoutError:
            process.kill()
            stdout, _ = await process.communicate()
            returncode = None
        run = SuiteRun(name, returncode, stdout.decode(errors="replace"))
        if junit.exists():
            run.total, run.degraded = parse_junit(junit.read_text())
    return run


def parse_junit(xml: str) -> tuple[int, list[Degraded]]:
    """The number of tests run and the degraded ones, from pytest's JUnit
    XML report."""
    root = ET.fromstring(xml)
    total = 0
    degraded: list[Degraded] = []
    for case in root.iter("testcase"):
        if case.find("skipped") is not None:
            continue
        total += 1
        for outcome in ("failure", "error"):
            problem = case.find(outcome)
            if problem is None:
                continue
            classname = case.get("classname") or ""
            module = classname.rsplit(".", 1)[-1]
            message = (problem.get("message") or "").strip().splitlines()
            first = message[0] if message else ""
            capture = not classname.startswith("tests.e2e.")
            if first.startswith(CAPTURE_FAILED):
                capture = True
                first = first.removeprefix(CAPTURE_FAILED + ": ")
            degraded.append(
                Degraded(
                    test=f"{module}.py::{case.get('name')}",
                    outcome="failed" if outcome == "failure" else "error",
                    message=first,
                    capture=capture,
                )
            )
            break
    return total, degraded


def report(runs: list[SuiteRun]) -> str | None:
    """The admin channel message, or None if nothing is degraded."""
    lines: list[str] = []
    for run in runs:
        if run.broken:
            lines.append(f"- {run.name} tests: {run.broken}")
        for d in run.degraded:
            detail = f": {d.message[:150]}" if d.message else ""
            capture = " (capture)" if d.capture else ""
            lines.append(f"- `{d.test}` {d.outcome}{capture}{detail}")
    if not lines:
        return None
    count = sum(len(run.degraded) for run in runs)
    total = sum(run.total for run in runs)
    capture = any(d.capture for run in runs for d in run.degraded)
    level = CAPTURE_DEGRADED if capture else DRIVERS_DEGRADED
    text = f"{level} **Daily tests: {count} of {total} degraded**"
    for i, line in enumerate(lines):
        if len(text) + len(line) + 40 > MAX_MESSAGE_CHARS:
            text += f"\n…and {len(lines) - i} more; see the logs."
            break
        text += "\n" + line
    return text


def attachments(runs: list[SuiteRun]) -> list[discord.File]:
    """Each run's pytest output, and the live tests' artifacts (screenshots,
    console logs, capture status, proxy log; not the traces) if they fit."""
    logs = [(f"{run.name}-tests.log", run.output.encode()) for run in runs]
    files = [discord.File(io.BytesIO(data), filename=name) for name, data in logs]
    used = sum(len(data) for _, data in logs)
    if any(run.name == "live" and run.degraded for run in runs):
        artifacts = _zip_artifacts()
        if artifacts is not None and used + len(artifacts) <= MAX_ATTACHMENTS_BYTES:
            files.append(discord.File(io.BytesIO(artifacts), filename="artifacts.zip"))
    return files


def _zip_artifacts() -> bytes | None:
    if not ARTIFACTS_DIR.is_dir():
        return None
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(ARTIFACTS_DIR.rglob("*")):
            if path.is_file() and path.name != "trace.zip":
                archive.write(path, path.relative_to(ARTIFACTS_DIR))
    return buffer.getvalue()


async def run_and_report(channel: discord.abc.Messageable) -> None:
    """Run the unit and live tests and post any degraded ones in `channel`."""
    log.info("Running the daily tests")
    runs = [await run_suite("unit", "not live"), await run_suite("live", "live")]
    text = report(runs)
    if text is None:
        log.info("Daily tests passed")
        return
    log.warning("Daily tests degraded; reporting them")
    try:
        await channel.send(
            text,
            files=attachments(runs),
            allowed_mentions=discord.AllowedMentions.none(),
        )
    except discord.HTTPException as e:
        log.error("Couldn't post the daily test report: %s", e)
