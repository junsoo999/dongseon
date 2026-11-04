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


class AreaPlace(Base):
    """A city's stay area or airport from ``config/cities/<city>.yaml``, linked to a Google place ID."""

    __tablename__ = "area_places"
    __table_args__ = (UniqueConstraint("city_key", "kind", "key", name="uq_area_places_city_kind_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    city_key: Mapped[str]
    kind: Mapped[str]  # stay_area | airport
    key: Mapped[str]  # area label or airport code
    query: Mapped[str]  # the config query used to find it (re-resolved when the config changes)
    google_place_id: Mapped[str | None]
    resolved_at: Mapped[datetime] = mapped_column(UTCDateTime())


class Stay(Base):
    """A stay candidate or booking. Location is a Google place or a point the user picked on the map."""

    __tablename__ = "stays"

    id: Mapped[int] = mapped_column(primary_key=True)
    trip_id: Mapped[int] = mapped_column(ForeignKey("trips.id", ondelete="CASCADE"), index=True)
    place_id: Mapped[int | None] = mapped_column(ForeignKey("places.id", ondelete="SET NULL"))
    label: Mapped[str]
    user_lat: Mapped[float | None]  # picked by the user (user data, not Google content)
    user_lng: Mapped[float | None]
    check_in: Mapped[date | None] = mapped_column(Date)
    check_out: Mapped[date | None] = mapped_column(Date)
    total_amount: Mapped[int | None]  # in the original currency's major unit (JPY and KRW have no minor unit)
    currency: Mapped[str] = mapped_column(String(3))
    booking_url: Mapped[str | None]
    note: Mapped[str | None]
    status: Mapped[str] = mapped_column(default="candidate")  # candidate | booked
    created_at: Mapped[datetime] = mapped_column(UTCDateTime())

    place: Mapped[Place | None] = relationship()


class FxRate(Base):
    """A reference exchange rate (ECB via Frankfurter) for one publication date."""

    __tablename__ = "fx_rates"
    __table_args__ = (UniqueConstraint("rate_date", "base", "quote", name="uq_fx_rates_date_base_quote"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    rate_date: Mapped[date] = mapped_column(Date)
    base: Mapped[str] = mapped_column(String(3))
    quote: Mapped[str] = mapped_column(String(3))
    rate: Mapped[float]
    fetched_at: Mapped[datetime] = mapped_column(UTCDateTime())


class FlightOption(Base):
    """A round-trip flight candidate or booking (searched by hand elsewhere, compared here)."""

    __tablename__ = "flight_options"

    id: Mapped[int] = mapped_column(primary_key=True)
    trip_id: Mapped[int] = mapped_column(ForeignKey("trips.id", ondelete="CASCADE"), index=True)
    label: Mapped[str]
    total_amount: Mapped[int | None]  # all travelers, in the currency's major unit
    currency: Mapped[str] = mapped_column(String(3))
    baggage_note: Mapped[str | None]
    booking_url: Mapped[str | None]
    note: Mapped[str | None]
    status: Mapped[str] = mapped_column(default="candidate")  # candidate | booked
    created_at: Mapped[datetime] = mapped_column(UTCDateTime())

    legs: Mapped[list["FlightLeg"]] = relationship(
        back_populates="option", cascade="all, delete-orphan", order_by="FlightLeg.dep_at"
    )


class FlightLeg(Base):
    """One flight segment. Times are stored in UTC; the airports' timezones give local time."""

    __tablename__ = "flight_legs"

    id: Mapped[int] = mapped_column(primary_key=True)
    option_id: Mapped[int] = mapped_column(ForeignKey("flight_options.id", ondelete="CASCADE"), index=True)
    direction: Mapped[str]  # out | back
    seq: Mapped[int]
    carrier: Mapped[str | None]
    flight_no: Mapped[str | None]
    dep_airport: Mapped[str] = mapped_column(String(3))
    dep_at: Mapped[datetime] = mapped_column(UTCDateTime())
    arr_airport: Mapped[str] = mapped_column(String(3))
    arr_at: Mapped[datetime] = mapped_column(UTCDateTime())

    option: Mapped[FlightOption] = relationship(back_populates="legs")
