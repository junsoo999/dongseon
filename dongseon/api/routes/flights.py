"""Flight candidates and their usable local time (searched by hand on Google Flights etc., compared here)."""

from datetime import UTC, datetime
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from dongseon.api.deps import HttpDep, ProfileDep, SessionDep, SettingsDep
from dongseon.api.routes.places import OptionalPlacesDep
from dongseon.api.routes.stays import ScoreOut, build_score
from dongseon.api.routes.trips import get_trip_or_404
from dongseon.core.airports import AirportInfo, load_airports
from dongseon.db.models import FlightLeg, FlightOption, Stay, Trip
from dongseon.flights.evaluate import LegTimes, check_legs, evaluate
from dongseon.sources.fx import get_rate

router = APIRouter(tags=["flights"])

LOCAL_FMT = "%Y-%m-%dT%H:%M"
RefKind = Literal["booked_stay", "top_area", "first_area", "none"]
Reference = tuple[str | None, RefKind, dict[str, int]]


class AirportOut(BaseModel):
    """An airport for the leg form."""

    code: str
    name: str
    timezone: str


class LegIn(BaseModel):
    """A leg with times in each airport's local time (``YYYY-MM-DDTHH:MM``)."""

    direction: Literal["out", "back"]
    carrier: str | None = Field(default=None, max_length=50)
    flight_no: str | None = Field(default=None, max_length=20)
    dep_airport: str = Field(pattern=r"^[A-Z]{3}$")
    dep_local: datetime
    arr_airport: str = Field(pattern=r"^[A-Z]{3}$")
    arr_local: datetime


class FlightIn(BaseModel):
    """A round-trip option."""

    label: str = Field(min_length=1, max_length=100)
    total_amount: int | None = Field(default=None, ge=0)
    currency: str = Field(default="KRW", pattern=r"^[A-Z]{3}$")
    baggage_note: str | None = Field(default=None, max_length=200)
    booking_url: str | None = Field(default=None, max_length=2000)
    note: str | None = Field(default=None, max_length=2000)
    status: Literal["candidate", "booked"] = "candidate"
    legs: list[LegIn] = Field(min_length=1, max_length=8)


class LegOut(BaseModel):
    """A leg with local times and the airports' timezones."""

    direction: str
    carrier: str | None
    flight_no: str | None
    dep_airport: str
    dep_local: str
    dep_timezone: str
    arr_airport: str
    arr_local: str
    arr_timezone: str
    duration_min: int


class EvaluationOut(BaseModel):
    """Usable time at the destination. Airport↔stay minutes are approximations ("근사")."""

    arrival_airport: str
    arrival_local: str
    ready_local: str | None
    departure_airport: str
    departure_local: str
    leave_by_local: str | None
    access_in_min: int | None
    access_out_min: int | None
    immigration_buffer_min: int
    departure_buffer_min: int
    usable_min: int | None
    reference_label: str | None
    reference_kind: RefKind
    total_krw: int | None
    krw_per_usable_hour: int | None
    warnings: list[str]


class FlightOut(BaseModel):
    """A flight option with its legs, problems and evaluation."""

    id: int
    label: str
    total_amount: int | None
    currency: str
    baggage_note: str | None
    booking_url: str | None
    note: str | None
    status: str
    legs: list[LegOut]
    problems: list[str]
    evaluation: EvaluationOut | None


def _airports(settings: SettingsDep) -> dict[str, AirportInfo]:
    return load_airports(settings.airports_file)


def _to_utc(local: datetime, info: AirportInfo) -> datetime:
    return local.replace(tzinfo=None, second=0, microsecond=0).replace(tzinfo=info.tz).astimezone(UTC)


def _local(at: datetime, tz: ZoneInfo) -> str:
    return at.astimezone(tz).strftime(LOCAL_FMT)


def _reference(session: Session, trip: Trip, score: ScoreOut | None) -> Reference:
    """Pick the stay to measure airport access from: the booked stay, the top-ranked origin, else the first area.

    The first configured area is a stand-in while no must/want pins exist to rank areas.
    """
    if score is None:
        return None, "none", {}
    booked = {
        f"stay:{s.id}"
        for s in session.scalars(select(Stay).where(Stay.trip_id == trip.id, Stay.status == "booked")).all()
    }
    for o in score.origins:
        if o.id in booked and o.airport_min:
            return o.label, "booked_stay", o.airport_min
    for o in score.origins:
        if o.rank is not None and o.airport_min:
            return o.label, "top_area", o.airport_min
    for o in score.origins:
        if o.kind == "area" and o.airport_min:
            return o.label, "first_area", o.airport_min
    return None, "none", {}


def _out(
    option: FlightOption,
    airports: dict[str, AirportInfo],
    trip_tz: ZoneInfo,
    profile: ProfileDep,
    reference: Reference,
    krw_rate: float | None,
) -> FlightOut:
    def tz_of(code: str) -> ZoneInfo:
        info = airports.get(code)
        return info.tz if info else ZoneInfo("UTC")

    legs = sorted(option.legs, key=lambda leg: leg.dep_at)
    times = [LegTimes(leg.direction, leg.dep_airport, leg.dep_at, leg.arr_airport, leg.arr_at) for leg in legs]
    label, kind, access = reference
    ev = evaluate(times, profile.buffers_min, access)
    total_krw = round(option.total_amount * krw_rate) if option.total_amount is not None and krw_rate else None
    evaluation = None
    if ev is not None:
        evaluation = EvaluationOut(
            arrival_airport=ev.arrival_airport,
            arrival_local=_local(ev.arrival_at, tz_of(ev.arrival_airport)),
            ready_local=_local(ev.ready_at, trip_tz) if ev.ready_at else None,
            departure_airport=ev.departure_airport,
            departure_local=_local(ev.departure_at, tz_of(ev.departure_airport)),
            leave_by_local=_local(ev.leave_by, trip_tz) if ev.leave_by else None,
            access_in_min=ev.access_in_min,
            access_out_min=ev.access_out_min,
            immigration_buffer_min=profile.buffers_min.arrival_immigration,
            departure_buffer_min=profile.buffers_min.departure_airport,
            usable_min=ev.usable_min,
            reference_label=label,
            reference_kind=kind,
            total_krw=total_krw,
            krw_per_usable_hour=(
                round(total_krw / (ev.usable_min / 60)) if total_krw is not None and ev.usable_min else None
            ),
            warnings=ev.warnings,
        )
    return FlightOut(
        id=option.id,
        label=option.label,
        total_amount=option.total_amount,
        currency=option.currency,
        baggage_note=option.baggage_note,
        booking_url=option.booking_url,
        note=option.note,
        status=option.status,
        legs=[
            LegOut(
                direction=leg.direction,
                carrier=leg.carrier,
                flight_no=leg.flight_no,
                dep_airport=leg.dep_airport,
                dep_local=_local(leg.dep_at, tz_of(leg.dep_airport)),
                dep_timezone=str(tz_of(leg.dep_airport)),
                arr_airport=leg.arr_airport,
                arr_local=_local(leg.arr_at, tz_of(leg.arr_airport)),
                arr_timezone=str(tz_of(leg.arr_airport)),
                duration_min=round((leg.arr_at - leg.dep_at).total_seconds() / 60),
            )
            for leg in legs
        ],
        problems=check_legs(times),
        evaluation=evaluation,
    )


def _apply(option: FlightOption, body: FlightIn, airports: dict[str, AirportInfo]) -> None:
    for code in {code for leg in body.legs for code in (leg.dep_airport, leg.arr_airport)}:
        if code not in airports:
            raise HTTPException(status_code=422, detail=f"공항 목록(config/airports.yaml)에 없는 공항입니다: {code}")
    option.label = body.label.strip()
    option.total_amount = body.total_amount
    option.currency = body.currency
    option.baggage_note = body.baggage_note
    option.booking_url = body.booking_url
    option.note = body.note
    option.status = body.status
    option.legs.clear()
    for i, leg in enumerate(body.legs):
        option.legs.append(
            FlightLeg(
                direction=leg.direction,
                seq=i,
                carrier=leg.carrier,
                flight_no=leg.flight_no,
                dep_airport=leg.dep_airport,
                dep_at=_to_utc(leg.dep_local, airports[leg.dep_airport]),
                arr_airport=leg.arr_airport,
                arr_at=_to_utc(leg.arr_local, airports[leg.arr_airport]),
            )
        )


def _only_one_booked(session: Session, trip: Trip, keep: FlightOption) -> None:
    if keep.status != "booked":
        return
    for other in session.scalars(select(FlightOption).where(FlightOption.trip_id == trip.id)).all():
        if other.id != keep.id and other.status == "booked":
            other.status = "candidate"


def _list(
    trip: Trip,
    session: Session,
    settings: SettingsDep,
    profile: ProfileDep,
    http: HttpDep,
    client: OptionalPlacesDep,
    only: int | None = None,
) -> list[FlightOut]:
    airports = _airports(settings)
    options = session.scalars(
        select(FlightOption).where(FlightOption.trip_id == trip.id).order_by(FlightOption.id)
    ).all()
    if only is not None:
        options = [o for o in options if o.id == only]
    if not options:
        return []
    try:
        score = build_score(trip, session, settings, profile, http, client)
    except HTTPException:
        score = None
    reference = _reference(session, trip, score)
    rates = {c: get_rate(session, http, c) for c in {o.currency for o in options}}
    tz = ZoneInfo(trip.timezone)
    return [
        _out(o, airports, tz, profile, reference, (r.rate if (r := rates.get(o.currency)) else None)) for o in options
    ]


@router.get("/airports", response_model=list[AirportOut])
def airports(settings: SettingsDep) -> list[AirportOut]:
    """List airports usable in flight legs."""
    return [AirportOut(code=a.code, name=a.name, timezone=a.timezone) for a in _airports(settings).values()]


@router.get("/trips/{trip_id}/flights", response_model=list[FlightOut])
def list_flights(
    trip_id: int,
    session: SessionDep,
    settings: SettingsDep,
    profile: ProfileDep,
    http: HttpDep,
    client: OptionalPlacesDep,
) -> list[FlightOut]:
    """List flight options with their usable local time."""
    return _list(get_trip_or_404(session, trip_id), session, settings, profile, http, client)


@router.post("/trips/{trip_id}/flights", response_model=FlightOut, status_code=201)
def create_flight(
    trip_id: int,
    body: FlightIn,
    session: SessionDep,
    settings: SettingsDep,
    profile: ProfileDep,
    http: HttpDep,
    client: OptionalPlacesDep,
) -> FlightOut:
    """Add a flight option."""
    trip = get_trip_or_404(session, trip_id)
    option = FlightOption(trip_id=trip.id, label="", currency=body.currency, created_at=datetime.now(UTC))
    _apply(option, body, _airports(settings))
    session.add(option)
    session.flush()
    _only_one_booked(session, trip, option)
    session.flush()
    return _list(trip, session, settings, profile, http, client, only=option.id)[0]


@router.put("/trips/{trip_id}/flights/{flight_id}", response_model=FlightOut)
def replace_flight(
    trip_id: int,
    flight_id: int,
    body: FlightIn,
    session: SessionDep,
    settings: SettingsDep,
    profile: ProfileDep,
    http: HttpDep,
    client: OptionalPlacesDep,
) -> FlightOut:
    """Replace a flight option and its legs."""
    trip = get_trip_or_404(session, trip_id)
    option = session.get(FlightOption, flight_id)
    if option is None or option.trip_id != trip.id:
        raise HTTPException(status_code=404, detail="항공 후보를 찾을 수 없습니다")
    _apply(option, body, _airports(settings))
    session.flush()
    _only_one_booked(session, trip, option)
    session.flush()
    return _list(trip, session, settings, profile, http, client, only=option.id)[0]


@router.delete("/trips/{trip_id}/flights/{flight_id}", status_code=204)
def delete_flight(trip_id: int, flight_id: int, session: SessionDep) -> None:
    """Remove a flight option."""
    option = session.get(FlightOption, flight_id)
    if option is None or option.trip_id != trip_id:
        raise HTTPException(status_code=404, detail="항공 후보를 찾을 수 없습니다")
    session.delete(option)
