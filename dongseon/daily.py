"""The daily job: run each step as its own CLI process and keep going on failure.

Steps: live prices (Ignav fares, Rakuten vacancies) for upcoming trips, then AI scouting (headless Claude Code;
skipped when the input did not change within 7 days). The trip-window rules in docs/PLAN.md section 16
(hours, weather, matrices from D-14) join in M5.
"""

import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from dongseon.core.config import REPO_ROOT

STEPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("실시간 가격 (Ignav, 楽天トラベル)", ("prices",)),
    ("AI 추천 (Claude Code)", ("scout",)),
)

# Exit codes from dongseon.cli: 0 ok, 1 user error, 2 external/system error (incl. quota stops), 3 locked.
OUTCOME = {
    0: "완료",
    1: "입력 오류",
    2: "중단 (한도·외부 오류, 다음 실행에서 이어감)",
    3: "건너뜀 (같은 작업이 이미 실행 중)",
}


@dataclass(frozen=True)
class StepResult:
    """Outcome of one step."""

    name: str
    returncode: int
    seconds: float


def _cli() -> list[str]:
    exe = Path(sys.executable).parent / "dongseon"
    return [str(exe)] if exe.exists() else [sys.executable, "-m", "dongseon"]


def run_daily(log: Path | None = None) -> list[StepResult]:
    """Run every step, streaming output to stdout (and ``log`` when given).

    Args:
        log: Optional file to append the combined output to.

    Returns:
        One result per step.
    """
    results: list[StepResult] = []
    sink = log.open("a", encoding="utf-8") if log else None

    def emit(line: str) -> None:
        sys.stdout.write(line)
        sys.stdout.flush()
        if sink:
            sink.write(line)
            sink.flush()

    try:
        emit(f"\n===== dongseon daily {datetime.now().astimezone():%Y-%m-%d %H:%M:%S %Z} =====\n")
        for name, args in STEPS:
            emit(f"\n--- {name}: dongseon {' '.join(args)}\n")
            started = time.monotonic()
            with subprocess.Popen(
                [*_cli(), *args],
                cwd=REPO_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            ) as proc:
                assert proc.stdout is not None
                for line in proc.stdout:
                    emit(line)
                code = proc.wait()
            results.append(StepResult(name, code, time.monotonic() - started))
            emit(f"--- {name}: {OUTCOME.get(code, f'실패 (코드 {code})')} ({time.monotonic() - started:.0f}초)\n")
        emit("\n===== 요약 =====\n")
        for r in results:
            emit(f"{r.name:<24} {OUTCOME.get(r.returncode, f'실패 (코드 {r.returncode})')}\n")
    finally:
        if sink:
            sink.close()
    return results
