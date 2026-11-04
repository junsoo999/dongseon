"""SQLAlchemy ORM models.

Natural-key columns are NOT NULL because SQLite treats NULLs as distinct inside UNIQUE constraints,
which would silently allow duplicates.
"""

from datetime import datetime

from sqlalchemy import DateTime, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base for all models."""


class ApiUsage(Base):
    """Billable Google calls per SKU per billing month (``YYYY-MM`` in Google's billing timezone)."""

    __tablename__ = "api_usage"
    __table_args__ = (UniqueConstraint("month", "sku", name="uq_api_usage_month_sku"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    month: Mapped[str]
    sku: Mapped[str]
    count: Mapped[int] = mapped_column(default=0)


class JobLog(Base):
    """One row per job unit (job + key), updated on every run so jobs can resume."""

    __tablename__ = "job_log"
    __table_args__ = (UniqueConstraint("job", "key", name="uq_job_log_job_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    job: Mapped[str]  # e.g. "daily", "places-resolve"
    key: Mapped[str]  # e.g. "" for whole-job runs, "place:12" for one unit
    status: Mapped[str]  # "ok" | "error" | "quota"
    rows: Mapped[int] = mapped_column(default=0)
    ran_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    error: Mapped[str | None]
