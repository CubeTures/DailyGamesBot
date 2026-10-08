"""Matching a captured result's fields against what a scenario expects.

An expected value is either a plain value (compared with ==) or a Check,
which carries a description so a failure says what was wanted.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Check:
    description: str
    test: Callable[[Any], bool]

    def __call__(self, value: Any) -> bool:
        try:
            return self.test(value)
        except Exception:
            return False


def where(description: str, test: Callable[[Any], bool]) -> Check:
    return Check(description, test)


def approx(value: float, tolerance: float = 1e-6) -> Check:
    return Check(
        f"≈ {value} (±{tolerance})",
        lambda v: isinstance(v, int | float) and abs(v - value) <= tolerance,
    )


def one_of(*values: Any) -> Check:
    return Check(f"one of {values!r}", lambda v: v in values)


def length(n: int) -> Check:
    return Check(f"a list of {n}", lambda v: isinstance(v, list) and len(v) == n)  # pyright: ignore[reportUnknownArgumentType]


def between(low: float, high: float) -> Check:
    return Check(
        f"a number in [{low}, {high}]",
        lambda v: isinstance(v, int | float) and low <= v <= high,
    )


ANY_POSITIVE = Check("a number > 0", lambda v: isinstance(v, int | float) and v > 0)
NOT_NONE = Check("not null", lambda v: v is not None)


def mismatches(expected: dict[str, Any], actual: dict[str, Any]) -> list[str]:
    """One line per expected field that doesn't match."""
    lines: list[str] = []
    for key, want in expected.items():
        missing = key not in actual
        got = actual.get(key)
        ok = want(got) if isinstance(want, Check) else (not missing and got == want)
        if ok and not missing:
            continue
        wanted = want.description if isinstance(want, Check) else json.dumps(want)
        shown = "<missing>" if missing else json.dumps(got, ensure_ascii=False)
        lines.append(f"  {key}: expected {wanted}, got {shown}")
    return lines
