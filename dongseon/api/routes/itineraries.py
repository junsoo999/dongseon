"""Itineraries: solve a draft, edit, re-solve around locks, restore a version, read and list versions."""

import json
from datetime import date, datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from dongseon.api.deps import HttpDep, ProfileDep, SessionDep, SettingsDep
from dongseon.api.routes.places import OptionalPlacesDep
from dongseon.api.routes.trips import get_trip_or_404
from dongseon.core.cities import load_city
from dongseon.db.models import Itinerary, Trip, TripPin
from dongseon.places.service import coords_for
from dongseon.planner.build import Edit, build_itinerary

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
    hours_source: str | None  # user | google_special | ai_research | google_regular | none
    locked: bool
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
    excluded: bool = False  # the user took it out (a re-solve keeps it out)


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
                    hours_source=extra.get("hours_source"),
                    locked=item.locked,
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
    dropped = [DroppedOut(**x) for x in stats.get("dropped") or [] if x["pin_id"] in pins]
    known = {x.pin_id for x in dropped} | {i.pin_id for i in it.items if i.pin_id}
    dropped += [
        DroppedOut(pin_id=p.id, label=p.place.label, priority=p.priority, reason="이 버전 이후 추가한 곳입니다")
        for p in pins.values()
        if p.id not in known
    ]
    return ItineraryOut(
        id=it.id,
        version=it.version,
        origin=it.origin,
        status=it.status,
        created_at=it.created_at,
        approx=bool(stats.get("approx", True)),
        days=days,
        dropped=dropped,
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
    it = _get_or_404(session, itinerary_id)
    return itinerary_out(it, get_trip_or_404(session, it.trip_id), session)


class DayLayoutIn(BaseModel):
    """Pins of one date in visiting order."""

    date: date
    pin_ids: list[int]


class EditIn(BaseModel):
    """A user-edited layout. ``resolve`` re-solves the unlocked pins; otherwise the layout is timed as given."""

    days: list[DayLayoutIn]
    locked: list[int] = Field(default_factory=list)
    excluded: list[int] = Field(default_factory=list)
    resolve: bool = False


def _get_or_404(session: SessionDep, itinerary_id: int) -> Itinerary:
    it = session.get(Itinerary, itinerary_id)
    if it is None:
        raise HTTPException(status_code=404, detail="일정을 찾을 수 없습니다")
    return it


def _edit_of(it: Itinerary, *, resolve: bool) -> Edit:
    """The layout, locks and exclusions of a stored version."""
    stats = json.loads(it.solver_stats_json or "{}")
    layout: dict[date, list[int]] = {date.fromisoformat(d): [] for d in stats.get("days") or {}}
    for item in sorted(it.items, key=lambda x: (x.day, x.seq)):
        if item.pin_id:
            layout.setdefault(item.day, []).append(item.pin_id)
    return Edit(
        layout=layout,
        locked=frozenset(i.pin_id for i in it.items if i.locked and i.pin_id),
        excluded=frozenset(stats.get("excluded") or []),
        resolve=resolve,
        base_dropped={x["pin_id"]: x["reason"] for x in stats.get("dropped") or []},
    )


def _new_version(
    session: SessionDep,
    settings: SettingsDep,
    profile: ProfileDep,
    http: HttpDep,
    client: OptionalPlacesDep,
    trip: Trip,
    edit: Edit,
) -> ItineraryOut:
    city = load_city(settings.cities_path, trip.city_key)
    it = build_itinerary(
        session, trip=trip, city=city, profile=profile, settings=settings, http=http, client=client, edit=edit
    )
    session.refresh(it)
    return itinerary_out(it, trip, session)


@router.post("/itineraries/{itinerary_id}/edit", response_model=ItineraryOut, status_code=201)
def edit_itinerary(
    itinerary_id: int,
    body: EditIn,
    session: SessionDep,
    settings: SettingsDep,
    profile: ProfileDep,
    http: HttpDep,
    client: OptionalPlacesDep,
) -> ItineraryOut:
    """Save the user's order, dates, locks and removals as a new version (optionally re-solving the rest)."""
    base = _get_or_404(session, itinerary_id)
    if base.status != "active":
        raise HTTPException(status_code=409, detail="최신 버전이 아닙니다. 화면을 새로 고친 뒤 다시 편집하세요")
    old = _edit_of(base, resolve=body.resolve)
    edit = Edit(
        layout={d.date: d.pin_ids for d in body.days},
        locked=frozenset(body.locked),
        excluded=frozenset(body.excluded),
        resolve=body.resolve,
        base_dropped=old.base_dropped,
    )
    return _new_version(session, settings, profile, http, client, get_trip_or_404(session, base.trip_id), edit)


@router.post("/itineraries/{itinerary_id}/resolve", response_model=ItineraryOut, status_code=201)
def resolve_itinerary(
    itinerary_id: int,
    session: SessionDep,
    settings: SettingsDep,
    profile: ProfileDep,
    http: HttpDep,
    client: OptionalPlacesDep,
) -> ItineraryOut:
    """Re-solve a version: locked visits stay on their date and in their order, removed pins stay out."""
    base = _get_or_404(session, itinerary_id)
    trip = get_trip_or_404(session, base.trip_id)
    return _new_version(session, settings, profile, http, client, trip, _edit_of(base, resolve=True))


@router.post("/itineraries/{itinerary_id}/restore", response_model=ItineraryOut, status_code=201)
def restore_itinerary(
    itinerary_id: int,
    session: SessionDep,
    settings: SettingsDep,
    profile: ProfileDep,
    http: HttpDep,
    client: OptionalPlacesDep,
) -> ItineraryOut:
    """Make a new version with an older version's layout, timed with today's hours and settings."""
    base = _get_or_404(session, itinerary_id)
    trip = get_trip_or_404(session, base.trip_id)
    edit = _edit_of(base, resolve=False)
    known = {pid for pids in edit.layout.values() for pid in pids}
    pins = set(session.scalars(select(TripPin.id).where(TripPin.trip_id == trip.id)))
    if known - pins:  # pins deleted since: drop them from the layout
        edit = Edit(
            layout={d: [p for p in pids if p in pins] for d, pids in edit.layout.items()},
            locked=edit.locked & pins,
            excluded=edit.excluded & pins,
            base_dropped=edit.base_dropped,
        )
    return _new_version(session, settings, profile, http, client, trip, edit)
