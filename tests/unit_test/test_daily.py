from pathlib import Path

import pytest

from dongseon import daily


def test_daily_runs_every_step_and_keeps_going(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        daily, "STEPS", (("도움말", ("--help",)), ("없는 명령", ("nope",)), ("다시 도움말", ("--help",)))
    )
    log = tmp_path / "daily.log"
    results = daily.run_daily(log)
    assert [r.returncode for r in results] == [0, 2, 0]  # Typer exits 2 on an unknown command; the run continues
    text = log.read_text(encoding="utf-8")
    assert "dongseon daily" in text and "===== 요약 =====" in text
