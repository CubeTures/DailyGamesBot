import socket
from collections.abc import Generator
from pathlib import Path

import pytest

from src.launcher import build, server


@pytest.fixture(autouse=True)
def scratch_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[Path]:
    """Every unit test gets its own empty results database."""
    path = tmp_path / "results.db"
    monkeypatch.setenv("DGB_DB_PATH", str(path))
    yield path


@pytest.fixture
def launcher(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[str]:
    """The launcher on a free port, writing its page under `tmp_path`."""
    monkeypatch.setattr(build, "OUTPUT_PATH", tmp_path / "index.html")
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    with server.serve_launcher(port):
        yield f"http://127.0.0.1:{port}"
