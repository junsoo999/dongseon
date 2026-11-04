"""SQLAlchemy ORM models.

Natural-key columns are NOT NULL because SQLite treats NULLs as distinct inside UNIQUE constraints,
which would silently allow duplicates. Google data is limited by ``docs/google-terms.md``: ``place_id``
is the only Google value stored permanently; coordinates live in ``geo_cache`` for at most 30 days.
"""

from datetime import date, datetime

from sqlalchemy import Date, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from dongseon.db.types import UTCDateTime


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
    ran_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    error: Mapped[str | None]


class Trip(Base):
    """One trip to one city."""

    __tablename__ = "trips"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str]
    city_key: Mapped[str]
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    timezone: Mapped[str]
    pace: Mapped[str]  # relaxed | normal | packed
    status: Mapped[str] = mapped_column(default="planning")  # planning | done
    created_at: Mapped[datetime] = mapped_column(UTCDateTime())

    pins: Mapped[list["TripPin"]] = relationship(back_populates="trip", cascade="all, delete-orphan")


class Place(Base):
    """A place the household cares about, reusable across trips. Label, category and note are user data."""

    __tablename__ = "places"

    id: Mapped[int] = mapped_column(primary_key=True)
    google_place_id: Mapped[str | None] = mapped_column(String, unique=True)
    label: Mapped[str]
    category: Mapped[str]
    user_note: Mapped[str | None]
    tag: Mapped[str | None]  # e.g. the Takeout list name
    source: Mapped[str]  # takeout | url | search | ai
    source_ref: Mapped[str | None]  # the user's URL or query
    resolve_status: Mapped[str]  # ok | pending | failed
    place_id_checked_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    created_at: Mapped[datetime] = mapped_column(UTCDateTime())


class TripPin(Base):
    """A place put into a trip, with planning attributes."""

    __tablename__ = "trip_pins"
    __table_args__ = (UniqueConstraint("trip_id", "place_id", name="uq_trip_pins_trip_place"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    trip_id: Mapped[int] = mapped_column(ForeignKey("trips.id", ondelete="CASCADE"), index=True)
    place_id: Mapped[int] = mapped_column(ForeignKey("places.id", ondelete="CASCADE"))
    priority: Mapped[str] = mapped_column(default="want")  # must | want | maybe
    dwell_min: Mapped[int]
    meal: Mapped[str | None]  # lunch | dinner
    reserved_start: Mapped[datetime | None] = mapped_column(UTCDateTime())
    reserved_end: Mapped[datetime | None] = mapped_column(UTCDateTime())
    locked_date: Mapped[date | None] = mapped_column(Date)
    note: Mapped[str | None]
    added_by: Mapped[str] = mapped_column(default="user")  # user | ai
    created_at: Mapped[datetime] = mapped_column(UTCDateTime())

    trip: Mapped[Trip] = relationship(back_populates="pins")
    place: Mapped[Place] = relationship()


class GeoCache(Base):
    """Google coordinates for a place ID, kept at most 30 days (Service Specific Terms)."""

    __tablename__ = "geo_cache"

    google_place_id: Mapped[str] = mapped_column(String, primary_key=True)
    lat: Mapped[float]
    lng: Mapped[float]
    fetched_at: Mapped[datetime] = mapped_column(UTCDateTime())
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
