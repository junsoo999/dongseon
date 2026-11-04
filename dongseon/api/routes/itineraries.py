"""Itineraries: solve a draft (new version), read the active one, list versions."""

import json
from datetime import date, datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from dongseon.api.deps import HttpDep, ProfileDep, SessionDep, SettingsDep
from dongseon.api.routes.places import OptionalPlacesDep
from dongseon.api.routes.trips import get_trip_or_404
from dongseon.core.cities import load_city
from dongseon.db.models import Itinerary, Trip, TripPin
from dongseon.places.service import coords_for
from dongseon.planner.build import build_itinerary

router = APIRouter(tags=["itineraries"])


class ItemOut(BaseModel):
    """A planned visit. Times are estimates; ``hours`` names the opening-hours source."""

    id: int
    pin_id: int | None
    label: str
    kind: str
    category: str | None
    priority: str | None
    google_place_id: str | None
    lat: float | None
    lng: float | None
    start: str  # local HH:MM
    end: str
    move_min: int | None
    move_mode: str | None
    hours: str | None
    warnings: list[str]


class DayOut(BaseModel):
    """One day of the plan."""

    date: date
    start: str
    end: str
    depot: str
    back_at: str | None
    back_move_min: int | None
    warnings: list[str]
    items: list[ItemOut]


class DroppedOut(BaseModel):
    """A pin the solver left out, and why."""

    pin_id: int
    label: str
    priority: str
    reason: str


class ItineraryOut(BaseModel):
    """An itinerary version."""

    id: int
    version: int
    origin: str
    status: str
    created_at: datetime
    approx: bool
    days: list[DayOut]
    dropped: list[DroppedOut]


class VersionOut(BaseModel):
    """A version in the history."""

    id: int
    version: int
    origin: str
    status: str
    created_at: datetime
    visits: int


def _hhmm(minutes: int) -> str:
    return f"{(minutes // 60) % 24:02d}:{minutes % 60:02d}"


def itinerary_out(it: Itinerary, trip: Trip, session: SessionDep) -> ItineraryOut:
    """Serialize an itinerary with local times and cached coordinates."""
    tz = ZoneInfo(trip.timezone)
    stats = json.loads(it.solver_stats_json or "{}")
    pins = {p.id: p for p in session.scalars(select(TripPin).where(TripPin.trip_id == trip.id))}
    coords = coords_for(session, None, [p.place.google_place_id for p in pins.values() if p.place.google_place_id])
    days: list[DayOut] = []
    for day_iso, info in (stats.get("days") or {}).items():
        d = date.fromisoformat(day_iso)
        items = []
        for item in (x for x in it.items if x.day == d):
            pin = pins.get(item.pin_id) if item.pin_id else None
            gid = pin.place.google_place_id if pin else None
            ll = coords.get(gid) if gid else None
            extra = json.loads(item.warnings_json or "{}")
            items.append(
                ItemOut(
                    id=item.id,
                    pin_id=item.pin_id,
                    label=item.label,
                    kind=item.kind,
                    category=pin.place.category if pin else None,
                    priority=pin.priority if pin else None,
                    google_place_id=gid,
                    lat=ll.lat if ll else None,
                    lng=ll.lng if ll else None,
                    start=item.start_at.astimezone(tz).strftime("%H:%M"),
                    end=item.end_at.astimezone(tz).strftime("%H:%M"),
                    move_min=item.move_min,
                    move_mode=item.move_mode,
                    hours=extra.get("hours"),
                    warnings=extra.get("warnings") or [],
                )
            )
        back = info.get("return_min")
        days.append(
            DayOut(
                date=d,
                start=_hhmm(info["start_min"]),
                end=_hhmm(info["end_min"]),
                depot=info["depot"],
                back_at=_hhmm(back) if back is not None else None,
                back_move_min=info.get("return_move_min"),
                warnings=info.get("warnings") or [],
                items=items,
            )
        )
    return ItineraryOut(
        id=it.id,
        version=it.version,
        origin=it.origin,
        status=it.status,
        created_at=it.created_at,
        approx=bool(stats.get("approx", True)),
        days=days,
        dropped=[DroppedOut(**x) for x in stats.get("dropped") or []],
    )


@router.post("/trips/{trip_id}/itineraries/solve", response_model=ItineraryOut, status_code=201)
def solve_itinerary(
    trip_id: int,
    session: SessionDep,
    settings: SettingsDep,
    profile: ProfileDep,
    http: HttpDep,
    client: OptionalPlacesDep,
) -> ItineraryOut:
    """Make a new draft from the trip's pins, stays, flight and opening hours."""
    trip = get_trip_or_404(session, trip_id)
    city = load_city(settings.cities_path, trip.city_key)
    it = build_itinerary(session, trip=trip, city=city, profile=profile, settings=settings, http=http, client=client)
    session.refresh(it)
    return itinerary_out(it, trip, session)


@router.get("/trips/{trip_id}/itineraries/active", response_model=ItineraryOut | None)
def active_itinerary(trip_id: int, session: SessionDep) -> ItineraryOut | None:
    """The current version, or null before the first draft."""
    trip = get_trip_or_404(session, trip_id)
    it = session.scalar(select(Itinerary).where(Itinerary.trip_id == trip.id, Itinerary.status == "active"))
    return itinerary_out(it, trip, session) if it else None


@router.get("/trips/{trip_id}/itineraries", response_model=list[VersionOut])
def list_versions(trip_id: int, session: SessionDep) -> list[VersionOut]:
    """Every version, newest first."""
    get_trip_or_404(session, trip_id)
    rows = session.scalars(select(Itinerary).where(Itinerary.trip_id == trip_id).order_by(Itinerary.version.desc()))
    return [
        VersionOut(
            id=r.id, version=r.version, origin=r.origin, status=r.status, created_at=r.created_at, visits=len(r.items)
        )
        for r in rows
    ]


@router.get("/itineraries/{itinerary_id}", response_model=ItineraryOut)
def get_itinerary(itinerary_id: int, session: SessionDep) -> ItineraryOut:
    """One version by id."""
    it = session.get(Itinerary, itinerary_id)
    if it is None:
        raise HTTPException(status_code=404, detail="일정을 찾을 수 없습니다")
    return itinerary_out(it, get_trip_or_404(session, it.trip_id), session)
