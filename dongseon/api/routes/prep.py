"""The prep tab: the trip's checklist and everything booked, in one place."""

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from dongseon.api.deps import SessionDep, SettingsDep
from dongseon.api.routes.trips import get_trip_or_404
from dongseon.core.airports import load_airports
from dongseon.core.checklist import load_checklist
from dongseon.core.config import Settings
from dongseon.db.models import ChecklistItem, FlightOption, Stay, Trip, TripPin

router = APIRouter(tags=["prep"])

LOCAL_FMT = "%Y-%m-%dT%H:%M"


class ChecklistItemOut(BaseModel):
    """One checklist entry."""

    id: int
    section: str
    text: str
    url: str | None
    done: bool
    sort: int


class ChecklistOut(BaseModel):
    """The trip's checklist, in order, with the template's check date."""

    items: list[ChecklistItemOut]
    template_as_of: date


class ChecklistIn(BaseModel):
    """A new entry written by the user."""

    text: str = Field(min_length=1, max_length=200)
    section: str = Field(default="기타", min_length=1, max_length=40)


class ChecklistPatch(BaseModel):
    """Check, uncheck or reword an entry."""

    done: bool | None = None
    text: str | None = Field(default=None, min_length=1, max_length=200)


class BookedLegOut(BaseModel):
    """A booked flight leg in each airport's local time (``YYYY-MM-DDTHH:MM``)."""

    direction: str
    carrier: str | None
    flight_no: str | None
    dep_airport: str
    dep_local: str
    arr_airport: str
    arr_local: str


class BookedFlightOut(BaseModel):
    """A booked flight option."""

    id: int
    label: str
    total_amount: int | None
    currency: str
    baggage_note: str | None
    booking_url: str | None
    note: str | None
    legs: list[BookedLegOut]


class BookedStayOut(BaseModel):
    """A booked stay."""

    id: int
    label: str
    check_in: date | None
    check_out: date | None
    total_amount: int | None
    currency: str
    booking_url: str | None
    note: str | None


class ReservationOut(BaseModel):
    """A pin with a reserved time slot (restaurant, ticket), in the trip's local time."""

    pin_id: int
    label: str
    start_local: str
    end_local: str | None
    note: str | None


class BookingsOut(BaseModel):
    """Everything booked for the trip."""

    flights: list[BookedFlightOut]
    stays: list[BookedStayOut]
    reservations: list[ReservationOut]


def _item_out(r: ChecklistItem) -> ChecklistItemOut:
    return ChecklistItemOut(id=r.id, section=r.section, text=r.text, url=r.url, done=r.done, sort=r.sort)


def checklist_rows(session: Session, trip_id: int) -> list[ChecklistItem]:
    """The trip's checklist entries in display order."""
    return list(
        session.scalars(
            select(ChecklistItem)
            .where(ChecklistItem.trip_id == trip_id)
            .order_by(ChecklistItem.sort, ChecklistItem.id)
        )
    )


def _get_item(session: Session, item_id: int) -> ChecklistItem:
    row = session.get(ChecklistItem, item_id)
    if row is None:
        raise HTTPException(status_code=404, detail="체크리스트 항목을 찾을 수 없습니다")
    return row


def _next_sort(session: Session, trip_id: int) -> int:
    return (session.scalar(select(func.max(ChecklistItem.sort)).where(ChecklistItem.trip_id == trip_id)) or 0) + 1


@router.get("/trips/{trip_id}/checklist", response_model=ChecklistOut)
def checklist(trip_id: int, session: SessionDep, settings: SettingsDep) -> ChecklistOut:
    """The trip's checklist."""
    get_trip_or_404(session, trip_id)
    return ChecklistOut(
        items=[_item_out(r) for r in checklist_rows(session, trip_id)],
        template_as_of=load_checklist(settings.checklist_file).as_of,
    )


@router.post("/trips/{trip_id}/checklist/seed", response_model=ChecklistOut)
def seed_checklist(trip_id: int, session: SessionDep, settings: SettingsDep) -> ChecklistOut:
    """Copy the template's lines the trip does not have yet (matched by text)."""
    get_trip_or_404(session, trip_id)
    template = load_checklist(settings.checklist_file)
    have = {r.text for r in checklist_rows(session, trip_id)}
    sort = _next_sort(session, trip_id)
    now = datetime.now(UTC)
    for section in template.sections:
        for it in section.items:
            if it.text in have:
                continue
            session.add(
                ChecklistItem(
                    trip_id=trip_id, section=section.name, text=it.text, url=it.url, sort=sort, created_at=now
                )
            )
            sort += 1
    session.flush()
    return checklist(trip_id, session, settings)


@router.post("/trips/{trip_id}/checklist", response_model=ChecklistItemOut, status_code=201)
def add_checklist_item(trip_id: int, body: ChecklistIn, session: SessionDep) -> ChecklistItemOut:
    """Add the user's own entry at the end."""
    get_trip_or_404(session, trip_id)
    row = ChecklistItem(
        trip_id=trip_id,
        section=body.section.strip(),
        text=body.text.strip(),
        sort=_next_sort(session, trip_id),
        created_at=datetime.now(UTC),
    )
    session.add(row)
    session.flush()
    return _item_out(row)


@router.patch("/checklist/{item_id}", response_model=ChecklistItemOut)
def update_checklist_item(item_id: int, body: ChecklistPatch, session: SessionDep) -> ChecklistItemOut:
    """Check, uncheck or reword an entry."""
    row = _get_item(session, item_id)
    if body.done is not None:
        row.done = body.done
    if body.text is not None:
        row.text = body.text.strip()
    session.flush()
    return _item_out(row)


@router.delete("/checklist/{item_id}", status_code=204)
def delete_checklist_item(item_id: int, session: SessionDep) -> Response:
    """Remove an entry."""
    session.delete(_get_item(session, item_id))
    return Response(status_code=204)


def bookings_for(session: Session, settings: Settings, trip: Trip) -> BookingsOut:
    """Collect booked flights, booked stays and reserved pins for a trip."""
    airports = load_airports(settings.airports_file)
    trip_tz = ZoneInfo(trip.timezone)

    def local(at: datetime, code: str) -> str:
        info = airports.get(code)
        return at.astimezone(info.tz if info else trip_tz).strftime(LOCAL_FMT)

    flights = session.scalars(
        select(FlightOption).where(FlightOption.trip_id == trip.id, FlightOption.status == "booked")
    )
    stays = session.scalars(
        select(Stay).where(Stay.trip_id == trip.id, Stay.status == "booked").order_by(Stay.check_in, Stay.id)
    )
    pins = session.scalars(
        select(TripPin)
        .where(TripPin.trip_id == trip.id, TripPin.reserved_start.is_not(None))
        .order_by(TripPin.reserved_start)
    )
    return BookingsOut(
        flights=[
            BookedFlightOut(
                id=f.id,
                label=f.label,
                total_amount=f.total_amount,
                currency=f.currency,
                baggage_note=f.baggage_note,
                booking_url=f.booking_url,
                note=f.note,
                legs=[
                    BookedLegOut(
                        direction=leg.direction,
                        carrier=leg.carrier,
                        flight_no=leg.flight_no,
                        dep_airport=leg.dep_airport,
                        dep_local=local(leg.dep_at, leg.dep_airport),
                        arr_airport=leg.arr_airport,
                        arr_local=local(leg.arr_at, leg.arr_airport),
                    )
                    for leg in f.legs
                ],
            )
            for f in flights
        ],
        stays=[
            BookedStayOut(
                id=s.id,
                label=s.label,
                check_in=s.check_in,
                check_out=s.check_out,
                total_amount=s.total_amount,
                currency=s.currency,
                booking_url=s.booking_url,
                note=s.note,
            )
            for s in stays
        ],
        reservations=[
            ReservationOut(
                pin_id=p.id,
                label=p.place.label,
                start_local=p.reserved_start.astimezone(trip_tz).strftime(LOCAL_FMT),
                end_local=p.reserved_end.astimezone(trip_tz).strftime(LOCAL_FMT) if p.reserved_end else None,
                note=p.note,
            )
            for p in pins
            if p.reserved_start is not None
        ],
    )


@router.get("/trips/{trip_id}/bookings", response_model=BookingsOut)
def bookings(trip_id: int, session: SessionDep, settings: SettingsDep) -> BookingsOut:
    """Booked flights, booked stays and reserved time slots."""
    return bookings_for(session, settings, get_trip_or_404(session, trip_id))
