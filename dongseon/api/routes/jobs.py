"""Start long CLI jobs in the background, one at a time per job (file lock)."""

import subprocess
import sys
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from dongseon.api.deps import SessionDep, SettingsDep
from dongseon.core.config import REPO_ROOT
from dongseon.core.lock import is_locked
from dongseon.db.models import JobLog

router = APIRouter(tags=["jobs"])

JobName = Literal["places-resolve", "scout", "prices"]
JOB_ARGS: dict[str, list[str]] = {"places-resolve": ["places", "resolve"], "scout": ["scout"], "prices": ["prices"]}


class JobStatus(BaseModel):
    """Whether a job is running and how its last run ended."""

    name: str
    running: bool
    last_status: str | None
    last_ran_at: datetime | None
    last_rows: int | None
    last_error: str | None


def _status(session: SessionDep, settings: SettingsDep, name: str) -> JobStatus:
    last = session.scalar(select(JobLog).where(JobLog.job == name, JobLog.key == ""))
    return JobStatus(
        name=name,
        running=is_locked(settings.lock_path, name),
        last_status=last.status if last else None,
        last_ran_at=last.ran_at if last else None,
        last_rows=last.rows if last else None,
        last_error=last.error if last else None,
    )


def spawn_cli(args: list[str]) -> None:
    """Run ``dongseon <args>`` detached from the request (overridden in tests)."""
    subprocess.Popen(
        [sys.executable, "-m", "dongseon", *args],
        cwd=REPO_ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


@router.get("/jobs/{name}", response_model=JobStatus)
def job_status(name: JobName, session: SessionDep, settings: SettingsDep) -> JobStatus:
    """Report a job's state."""
    return _status(session, settings, name)


@router.post("/jobs/{name}", response_model=JobStatus, status_code=202)
def start_job(name: JobName, session: SessionDep, settings: SettingsDep) -> JobStatus:
    """Start a job in the background; 409 when it is already running."""
    if is_locked(settings.lock_path, name):
        raise HTTPException(status_code=409, detail="이미 실행 중입니다")
    spawn_cli(JOB_ARGS[name])
    status = _status(session, settings, name)
    return status.model_copy(update={"running": True})
