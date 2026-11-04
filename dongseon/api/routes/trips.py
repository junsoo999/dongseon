"""Trips and the cities they can use."""

from datetime import UTC, date, datetime
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select

from dongseon.api.deps import SessionDep, SettingsDep
from dongseon.core.cities import CityNotFoundError, list_cities, load_city
from dongseon.db.models import Trip, TripPin

router = APIRouter(tags=["trips"])

Pace = Literal["relaxed", "normal", "packed"]


class CityOut(BaseModel):
    """A configured city."""

    key: str
    name: str
    country: str
    timezone: str
    currency: str


class TripIn(BaseModel):
    """A new trip."""

    title: str = Field(min_length=1, max_length=100)
    city_key: str
    start_date: date
    end_date: date
    pace: Pace = "normal"

    @model_validator(mode="after")
    def _check_dates(self) -> "TripIn":
        if self.end_date < self.start_date:
            raise ValueError("end_date is before start_date")
        return self


class TripPatch(BaseModel):
    """Editable trip fields."""

    title: str | None = Field(default=None, min_length=1, max_length=100)
    start_date: date | None = None
    end_date: date | None = None
    pace: Pace | None = None
    status: Literal["planning", "done"] | None = None


class TripOut(BaseModel):
    """A trip with its pin count."""

    id: int
    title: str
    city_key: str
    city_name: str
    start_date: date
    end_date: date
    timezone: str
    pace: str
    status: str
    pin_count: int


def _city_name(settings: SettingsDep, key: str) -> str:
    try:
        return load_city(settings.cities_path, key).name
    except CityNotFoundError:
        return key


def _out(trip: Trip, settings: SettingsDep, pin_count: int) -> TripOut:
    return TripOut(
        id=trip.id,
        title=trip.title,
        city_key=trip.city_key,
        city_name=_city_name(settings, trip.city_key),
        start_date=trip.start_date,
        end_date=trip.end_date,
        timezone=trip.timezone,
        pace=trip.pace,
        status=trip.status,
        pin_count=pin_count,
    )


def get_trip_or_404(session: SessionDep, trip_id: int) -> Trip:
    """Load a trip or raise 404."""
    trip = session.get(Trip, trip_id)
    if trip is None:
        raise HTTPException(status_code=404, detail="여행을 찾을 수 없습니다")
    return trip


def _pin_count(session: SessionDep, trip_id: int) -> int:
    return session.scalar(select(func.count()).select_from(TripPin).where(TripPin.trip_id == trip_id)) or 0


@router.get("/cities", response_model=list[CityOut])
def cities(settings: SettingsDep) -> list[CityOut]:
    """List configured cities."""
    return [
        CityOut(key=c.key, name=c.name, country=c.country, timezone=c.timezone, currency=c.currency)
        for c in list_cities(settings.cities_path)
    ]


@router.get("/trips", response_model=list[TripOut])
def list_trips(session: SessionDep, settings: SettingsDep) -> list[TripOut]:
    """List trips, upcoming first."""
    trips = session.scalars(select(Trip).order_by(Trip.start_date.desc())).all()
    return [_out(t, settings, _pin_count(session, t.id)) for t in trips]


@router.post("/trips", response_model=TripOut, status_code=201)
def create_trip(body: TripIn, session: SessionDep, settings: SettingsDep) -> TripOut:
    """Create a trip in a configured city."""
    try:
        city = load_city(settings.cities_path, body.city_key)
    except CityNotFoundError as e:
        raise HTTPException(status_code=422, detail="설정에 없는 도시입니다") from e
    trip = Trip(
        title=body.title.strip(),
        city_key=city.key,
        start_date=body.start_date,
        end_date=body.end_date,
        timezone=city.timezone,
        pace=body.pace,
        created_at=datetime.now(UTC),
    )
    session.add(trip)
    session.flush()
    return _out(trip, settings, 0)


@router.get("/trips/{trip_id}", response_model=TripOut)
def get_trip(trip_id: int, session: SessionDep, settings: SettingsDep) -> TripOut:
    """Return one trip."""
    return _out(get_trip_or_404(session, trip_id), settings, _pin_count(session, trip_id))


@router.patch("/trips/{trip_id}", response_model=TripOut)
def patch_trip(trip_id: int, body: TripPatch, session: SessionDep, settings: SettingsDep) -> TripOut:
    """Update trip fields."""
    trip = get_trip_or_404(session, trip_id)
    for key, value in body.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(trip, key, value)
    if trip.end_date < trip.start_date:
        raise HTTPException(status_code=422, detail="종료일이 시작일보다 빠릅니다")
    return _out(trip, settings, _pin_count(session, trip_id))
