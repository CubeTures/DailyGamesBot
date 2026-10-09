from collections.abc import Generator
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def scratch_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[Path]:
    """Every unit test gets its own empty results database."""
    path = tmp_path / "results.db"
    monkeypatch.setenv("DGB_DB_PATH", str(path))
    yield path
