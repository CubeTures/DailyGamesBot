from src.discord_bot.daily_tests import (
    CAPTURE_DEGRADED,
    DRIVERS_DEGRADED,
    Degraded,
    SuiteRun,
    parse_junit,
    report,
)

JUNIT = """<?xml version="1.0" encoding="utf-8"?>
<testsuites><testsuite name="pytest">
  <testcase classname="tests.e2e.test_capture" name="test_capture[wordle-win]"/>
  <testcase classname="tests.e2e.test_capture" name="test_capture[wordle-lose]">
    <failure message="tests.e2e.harness.CaptureFailed: won: expected false, got true&#10;more">tb</failure>
  </testcase>
  <testcase classname="tests.e2e.test_capture" name="test_capture[chess-win]">
    <error message="failed on setup with &quot;TimeoutError&quot;">tb</error>
  </testcase>
  <testcase classname="tests.e2e.test_capture" name="test_capture[wordle-mixed]">
    <failure message="tests.e2e.harness.NoResult: no wordle result saved">tb</failure>
  </testcase>
  <testcase classname="tests.e2e.test_capture" name="test_capture[fermi-win]">
    <skipped type="pytest.skip" message="resets soon"/>
  </testcase>
</testsuite></testsuites>
"""


def test_parse_junit() -> None:
    total, degraded = parse_junit(JUNIT)
    assert total == 4
    assert degraded == [
        Degraded(
            "test_capture.py::test_capture[wordle-lose]",
            "failed",
            "won: expected false, got true",
            capture=True,
        ),
        Degraded(
            "test_capture.py::test_capture[chess-win]",
            "error",
            'failed on setup with "TimeoutError"',
        ),
        Degraded(
            "test_capture.py::test_capture[wordle-mixed]",
            "failed",
            "tests.e2e.harness.NoResult: no wordle result saved",
        ),
    ]


def test_parse_junit_unit_failures_are_capture() -> None:
    xml = """<testsuites><testsuite>
      <testcase classname="tests.unit.test_store" name="test_x">
        <failure message="AssertionError: nope">tb</failure>
      </testcase>
    </testsuite></testsuites>"""
    _, degraded = parse_junit(xml)
    assert [d.capture for d in degraded] == [True]


def test_no_report_when_all_pass() -> None:
    assert report([SuiteRun("unit", 0, "", total=5)]) is None


def test_report_lists_degraded() -> None:
    total, degraded = parse_junit(JUNIT)
    text = report(
        [SuiteRun("unit", 0, "", 5), SuiteRun("live", 1, "", total, degraded)]
    )
    assert text is not None
    assert text.startswith(f"{CAPTURE_DEGRADED} **Daily tests: 3 of 9 degraded**")
    assert "`test_capture.py::test_capture[wordle-lose]` failed (capture): won:" in text


def test_report_drivers_only_is_yellow() -> None:
    _, degraded = parse_junit(JUNIT)
    drivers = [d for d in degraded if not d.capture]
    text = report([SuiteRun("live", 1, "", 4, drivers)])
    assert text is not None and text.startswith(DRIVERS_DEGRADED + " ")


def test_report_when_run_breaks() -> None:
    for run in (
        SuiteRun("live", None, ""),
        SuiteRun("live", 1, ""),
        SuiteRun("live", 4, ""),
    ):
        text = report([run])
        assert text is not None and "- live tests: " in text
        assert text.startswith(DRIVERS_DEGRADED)


def test_report_fits_a_message() -> None:
    many = [Degraded(f"t.py::test_{i}", "failed", "x" * 300) for i in range(50)]
    text = report([SuiteRun("live", 1, "", 50, many)])
    assert text is not None and len(text) <= 2000 and "more; see the logs" in text
