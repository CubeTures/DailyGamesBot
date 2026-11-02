from src.discord_bot.daily_tests import Degraded, SuiteRun, parse_junit, report

JUNIT = """<?xml version="1.0" encoding="utf-8"?>
<testsuites><testsuite name="pytest">
  <testcase classname="tests.e2e.test_capture" name="test_capture[wordle-win]"/>
  <testcase classname="tests.e2e.test_capture" name="test_capture[wordle-lose]">
    <failure message="AssertionError: won: expected false, got true&#10;more">tb</failure>
  </testcase>
  <testcase classname="tests.e2e.test_capture" name="test_capture[chess-win]">
    <error message="failed on setup with &quot;TimeoutError&quot;">tb</error>
  </testcase>
  <testcase classname="tests.e2e.test_capture" name="test_capture[fermi-win]">
    <skipped type="pytest.skip" message="resets soon"/>
  </testcase>
</testsuite></testsuites>
"""


def test_parse_junit() -> None:
    total, degraded = parse_junit(JUNIT)
    assert total == 3
    assert degraded == [
        Degraded(
            "test_capture.py::test_capture[wordle-lose]",
            "failed",
            "AssertionError: won: expected false, got true",
        ),
        Degraded(
            "test_capture.py::test_capture[chess-win]",
            "error",
            'failed on setup with "TimeoutError"',
        ),
    ]


def test_no_report_when_all_pass() -> None:
    assert report([SuiteRun("unit", 0, "", total=5)]) is None


def test_report_lists_degraded() -> None:
    total, degraded = parse_junit(JUNIT)
    text = report(
        [SuiteRun("unit", 0, "", 5), SuiteRun("live", 1, "", total, degraded)]
    )
    assert text is not None
    assert text.startswith("**Daily tests: 2 of 8 degraded**")
    assert "`test_capture.py::test_capture[wordle-lose]` failed: AssertionError" in text


def test_report_when_run_breaks() -> None:
    for run in (
        SuiteRun("live", None, ""),
        SuiteRun("live", 1, ""),
        SuiteRun("live", 4, ""),
    ):
        text = report([run])
        assert text is not None and "- live tests: " in text


def test_report_fits_a_message() -> None:
    many = [Degraded(f"t.py::test_{i}", "failed", "x" * 300) for i in range(50)]
    text = report([SuiteRun("live", 1, "", 50, many)])
    assert text is not None and len(text) <= 2000 and "more; see the logs" in text
