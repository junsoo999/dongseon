from pathlib import Path

import pytest
from typer.testing import CliRunner

from dongseon.cli import app
from dongseon.core.lock import JobLockedError, is_locked, job_lock


def test_job_lock_is_exclusive(tmp_path: Path) -> None:
    with job_lock(tmp_path, "daily"):
        assert is_locked(tmp_path, "daily")
        with pytest.raises(JobLockedError), job_lock(tmp_path, "daily"):
            pass
    assert not is_locked(tmp_path, "daily")


def test_cli_help_is_korean() -> None:
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "명령줄 도구" in result.output


def test_cli_usage_prints_skus(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from dongseon.core.config import get_settings

    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "c.db"))
    get_settings.cache_clear()
    try:
        result = CliRunner().invoke(app, ["usage"])
    finally:
        get_settings.cache_clear()
    assert result.exit_code == 0, result.output
    assert "places_details_pro" in result.output
