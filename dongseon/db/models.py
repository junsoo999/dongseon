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
    # Airports the first day starts at and the last day ends at until a flight is booked (IATA, city airports).
    arrival_airport: Mapped[str | None]
    departure_airport: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(UTCDateTime())

    pins: Mapped[list["TripPin"]] = relationship(back_populates="trip", cascade="all, delete-orphan")


class Place(Base):
    """A place the household cares about, reusable across trips. Label, category and note are user data."""

    __tablename__ = "places"

    id: Mapped[int] = mapped_column(primary_key=True)
    google_place_id: Mapped[str | None] = mapped_column(String, unique=True)
    label: Mapped[str]
    local_name: Mapped[str | None]  # the user's (or accepted AI research's) local-language name, for My Maps export
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


class LlmRun(Base):
    """One headless Claude Code call, for the daily token limit and troubleshooting."""

    __tablename__ = "llm_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str]  # e.g. "places_research"
    model: Mapped[str]
    prompt_version: Mapped[str]
    tokens: Mapped[int]
    cost_usd: Mapped[float | None]
    ok: Mapped[bool]
    error: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)


class AiSuggestion(Base):
    """An AI suggestion waiting for the user (accept turns it into a pin or stay candidate)."""

    __tablename__ = "ai_suggestions"

    id: Mapped[int] = mapped_column(primary_key=True)
    trip_id: Mapped[int] = mapped_column(ForeignKey("trips.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str]  # place | stay (later: review | rain | hours)
    key: Mapped[str]  # dedupe key: normalized name
    payload_json: Mapped[str]  # validated research item, incl. sources
    google_place_id: Mapped[str | None]
    status: Mapped[str] = mapped_column(default="pending")  # pending | accepted | rejected
    prompt_version: Mapped[str]
    input_hash: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)


class FareOffer(Base):
    """A round-trip fare from the latest Ignav search for a trip and route (replaced on each refresh)."""

    __tablename__ = "fare_offers"

    id: Mapped[int] = mapped_column(primary_key=True)
    trip_id: Mapped[int] = mapped_column(ForeignKey("trips.id", ondelete="CASCADE"), index=True)
    route: Mapped[str]  # e.g. "ICN-NRT"
    ignav_id: Mapped[str]
    amount: Mapped[int]  # all travelers
    currency: Mapped[str] = mapped_column(String(3))
    out_carrier: Mapped[str | None]
    in_carrier: Mapped[str | None]
    legs_json: Mapped[str]  # [{direction, carrier_code, flight_number, dep_airport, dep_at, arr_airport, arr_at}]
    fetched_at: Mapped[datetime] = mapped_column(UTCDateTime())


class HotelVacancy(Base):
    """A hotel with vacancies from the latest Rakuten Travel search around a stay area (replaced on refresh)."""

    __tablename__ = "hotel_vacancies"

    id: Mapped[int] = mapped_column(primary_key=True)
    trip_id: Mapped[int] = mapped_column(ForeignKey("trips.id", ondelete="CASCADE"), index=True)
    area: Mapped[str]
    hotel_no: Mapped[int]
    name: Mapped[str]
    lat: Mapped[float]  # Rakuten's coordinates
    lng: Mapped[float]
    nearest_station: Mapped[str | None]
    access: Mapped[str | None]
    review_average: Mapped[float | None]
    review_count: Mapped[int | None]
    thumbnail_url: Mapped[str | None]
    info_url: Mapped[str | None]
    plan_name: Mapped[str | None]
    room_name: Mapped[str | None]
    first_night_total: Mapped[int | None]  # JPY, all guests
    reserve_url: Mapped[str | None]
    bath_hint: Mapped[bool]
    check_in: Mapped[date] = mapped_column(Date)
    check_out: Mapped[date] = mapped_column(Date)
    fetched_at: Mapped[datetime] = mapped_column(UTCDateTime())


class PriceSnapshot(Base):
    """The lowest price seen per day for a trip's route or area, for trends."""

    __tablename__ = "price_snapshots"
    __table_args__ = (UniqueConstraint("trip_id", "kind", "key", "day", name="uq_price_snapshots_key_day"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    trip_id: Mapped[int] = mapped_column(ForeignKey("trips.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str]  # flight | hotel
    key: Mapped[str]  # route ("ICN-NRT") or area label
    day: Mapped[date] = mapped_column(Date)
    min_amount: Mapped[int]
    currency: Mapped[str] = mapped_column(String(3))


class FarePrefs(Base):
    """Flight search conditions for a trip (unset fields fall back to the profile and city config)."""

    __tablename__ = "fare_prefs"

    trip_id: Mapped[int] = mapped_column(ForeignKey("trips.id", ondelete="CASCADE"), primary_key=True)
    adults: Mapped[int | None]
    children: Mapped[int] = mapped_column(default=0)
    origins_json: Mapped[str | None]  # ["ICN"]; null = profile home_airports
    destinations_json: Mapped[str | None]  # ["HND", "NRT"]; null = city airports
    max_stops: Mapped[int | None] = mapped_column(default=0)  # null = any
    checked_bags: Mapped[int | None]
    out_dep_from: Mapped[int | None]  # local hours, 0-23
    out_dep_to: Mapped[int | None]
    back_dep_from: Mapped[int | None]
    back_dep_to: Mapped[int | None]
    max_price_krw: Mapped[int | None]
    airlines_exclude_json: Mapped[str | None]  # ["7C"]
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime())


class HoursOverride(Base):
    """Opening hours for one place on one date from the user or AI research (Google hours are never stored)."""

    __tablename__ = "hours_overrides"
    __table_args__ = (UniqueConstraint("place_id", "day", "source", name="uq_hours_overrides_place_date_source"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    place_id: Mapped[int] = mapped_column(ForeignKey("places.id", ondelete="CASCADE"), index=True)
    day: Mapped[date] = mapped_column(Date)
    status: Mapped[str]  # open | closed | special | unknown
    open_min: Mapped[int | None]  # minutes after local midnight
    close_min: Mapped[int | None]  # may exceed 1440 when closing after midnight
    source: Mapped[str]  # user | ai_research
    source_url: Mapped[str | None]
    checked_at: Mapped[datetime] = mapped_column(UTCDateTime())


class Itinerary(Base):
    """One version of a trip's day-by-day plan (solver draft, AI suggestion or user edit)."""

    __tablename__ = "itineraries"

    id: Mapped[int] = mapped_column(primary_key=True)
    trip_id: Mapped[int] = mapped_column(ForeignKey("trips.id", ondelete="CASCADE"), index=True)
    version: Mapped[int]
    origin: Mapped[str]  # solver | ai | user
    status: Mapped[str] = mapped_column(default="active")  # active | archived
    created_at: Mapped[datetime] = mapped_column(UTCDateTime())
    solver_stats_json: Mapped[str | None]  # objective, dropped pins with reasons, approximations used

    items: Mapped[list["ItineraryItem"]] = relationship(
        back_populates="itinerary", cascade="all, delete-orphan", order_by="(ItineraryItem.day, ItineraryItem.seq)"
    )


class ItineraryItem(Base):
    """A visit, move or stay segment in an itinerary. Times are the plan's own estimates (app data)."""

    __tablename__ = "itinerary_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    itinerary_id: Mapped[int] = mapped_column(ForeignKey("itineraries.id", ondelete="CASCADE"), index=True)
    day: Mapped[date] = mapped_column(Date)
    seq: Mapped[int]
    kind: Mapped[str]  # visit | meal | move | stay | flight
    pin_id: Mapped[int | None] = mapped_column(ForeignKey("trip_pins.id", ondelete="SET NULL"))
    label: Mapped[str]
    start_at: Mapped[datetime] = mapped_column(UTCDateTime())
    end_at: Mapped[datetime] = mapped_column(UTCDateTime())
    move_mode: Mapped[str | None]  # walk | rail
    move_min: Mapped[int | None]
    locked: Mapped[bool] = mapped_column(default=False)
    warnings_json: Mapped[str | None]

    itinerary: Mapped[Itinerary] = relationship(back_populates="items")


class Weather(Base):
    """Daily weather for a city: Open-Meteo forecast (up to 16 days ahead) or past-years climate for the date."""

    __tablename__ = "weather"
    __table_args__ = (UniqueConstraint("city_key", "day", "kind", name="uq_weather_city_day_kind"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    city_key: Mapped[str]
    day: Mapped[date] = mapped_column(Date)
    kind: Mapped[str]  # forecast | climate
    payload_json: Mapped[str]  # weather code, temperatures, precipitation (see dongseon/sources/open_meteo.py)
    fetched_at: Mapped[datetime] = mapped_column(UTCDateTime())


class TripAlert(Base):
    """Something the household should look at, e.g. warnings that changed when hours were re-checked.

    Holds only the app's own warning text (labels are user data); never Google hours or travel times.
    """

    __tablename__ = "trip_alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    trip_id: Mapped[int] = mapped_column(ForeignKey("trips.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str]  # hours_changed
    itinerary_id: Mapped[int | None] = mapped_column(ForeignKey("itineraries.id", ondelete="SET NULL"))
    payload_json: Mapped[str]  # {"added": [...], "resolved": [...]}
    status: Mapped[str] = mapped_column(default="new")  # new | dismissed
    created_at: Mapped[datetime] = mapped_column(UTCDateTime())


class ChecklistItem(Base):
    """A preparation checklist entry for a trip (seeded from ``config/checklist.yaml``, then the user's own)."""

    __tablename__ = "checklist_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    trip_id: Mapped[int] = mapped_column(ForeignKey("trips.id", ondelete="CASCADE"), index=True)
    section: Mapped[str]
    text: Mapped[str]
    url: Mapped[str | None]
    done: Mapped[bool] = mapped_column(default=False)
    sort: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(UTCDateTime())
