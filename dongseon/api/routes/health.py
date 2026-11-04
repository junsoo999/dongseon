"""Health check endpoint."""

from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError

from dongseon import __version__
from dongseon.api.deps import SettingsDep
from dongseon.core.config import Settings
from dongseon.db.models import JobLog
from dongseon.db.session import get_engine, session_scope

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Server status and configuration summary."""

    status: str
    version: str
    last_daily_at: datetime | None
    database_exists: bool
    profile_loaded: bool
    keys: dict[str, bool]


def _last_daily_at(settings: Settings) -> datetime | None:
    if not settings.database_file.exists():
        return None
    try:
        with session_scope(get_engine(settings.database_file)) as session:
            return session.scalar(select(func.max(JobLog.ran_at)).where(JobLog.job == "daily", JobLog.status == "ok"))
    except OperationalError:  # schema not created yet
        return None


@router.get("/health", response_model=HealthResponse)
def health(settings: SettingsDep) -> HealthResponse:
    """Report server status, the last successful daily run, and which API keys are configured."""
    return HealthResponse(
        status="ok",
        version=__version__,
        last_daily_at=_last_daily_at(settings),
        database_exists=settings.database_file.exists(),
        profile_loaded=settings.profile_file.exists(),
        keys=settings.configured_keys,
    )
