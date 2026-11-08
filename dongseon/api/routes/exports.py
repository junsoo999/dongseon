"""Plan exports (ICS, print HTML, My Maps zip) and the offline bundle the phone keeps for the trip."""

from datetime import UTC, date, datetime
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from dongseon.api.deps import SessionDep, SettingsDep
from dongseon.api.routes.prep import BookingsOut, ChecklistItemOut, bookings_for, checklist_rows
from dongseon.api.routes.trips import get_trip_or_404
from dongseon.core.cities import load_city
from dongseon.core.config import Settings
from dongseon.db.models import Itinerary, Trip
from dongseon.export.ics import build_ics
from dongseon.export.mymaps import build_zip
from dongseon.export.plan import PlanExport, build_export, day_route_urls, directions_url
from dongseon.export.print_html import build_print_html

router = APIRouter(tags=["exports"])


class OfflineStopOut(BaseModel):
    """A visit as kept offline: the plan's own times and the user's text, plus a Maps deep link."""

    seq: int
    start: str  # local HH:MM
    end: str
    label: str
    local_name: str | None
    area: str | None
    note: str | None
    google_place_id: str | None
    directions_url: str
    warnings: list[str]


class OfflineDayOut(BaseModel):
    """A day as kept offline."""

    date: date
    depot: str
    stops: list[OfflineStopOut]
    route_urls: list[str]


class OfflineTripOut(BaseModel):
    """The trip fields the offline screens need."""

    id: int
    title: str
    timezone: str
    start_date: date
    end_date: date


class OfflineOut(BaseModel):
    """What the phone stores for reading without a connection. No Google hours, travel times or coordinates."""

    trip: OfflineTripOut
    generated_at: datetime
    itinerary_id: int | None
    version: int | None
    days: list[OfflineDayOut]
    checklist: list[ChecklistItemOut]
    bookings: BookingsOut


def _itinerary(session: Session, itinerary_id: int) -> Itinerary:
    it = session.get(Itinerary, itinerary_id)
    if it is None:
        raise HTTPException(status_code=404, detail="일정을 찾을 수 없습니다")
    return it


def _plan(session: Session, settings: Settings, it: Itinerary) -> PlanExport:
    trip = get_trip_or_404(session, it.trip_id)
    return build_export(session, it, trip, load_city(settings.cities_path, trip.city_key))


def _attachment(name: str) -> dict[str, str]:
    return {"Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}"}


def _file_stem(trip: Trip, version: int) -> str:
    return f"dongseon-{trip.start_date:%Y%m%d}-v{version}"


@router.get("/itineraries/{itinerary_id}/export.ics", response_class=Response)
def export_ics(itinerary_id: int, session: SessionDep, settings: SettingsDep) -> Response:
    """Planned visits as calendar events."""
    plan = _plan(session, settings, _itinerary(session, itinerary_id))
    return Response(
        build_ics(plan),
        media_type="text/calendar; charset=utf-8",
        headers=_attachment(f"{_file_stem(plan.trip, plan.version)}.ics"),
    )


@router.get("/itineraries/{itinerary_id}/print", response_class=HTMLResponse)
def export_print(itinerary_id: int, session: SessionDep, settings: SettingsDep) -> HTMLResponse:
    """A print-friendly page of the plan."""
    return HTMLResponse(build_print_html(_plan(session, settings, _itinerary(session, itinerary_id))))


@router.get("/itineraries/{itinerary_id}/mymaps.zip", response_class=Response)
def export_mymaps(itinerary_id: int, session: SessionDep, settings: SettingsDep) -> Response:
    """One Google My Maps import CSV per day, zipped (no coordinates)."""
    plan = _plan(session, settings, _itinerary(session, itinerary_id))
    return Response(
        build_zip(plan),
        media_type="application/zip",
        headers=_attachment(f"{_file_stem(plan.trip, plan.version)}-mymaps.zip"),
    )


@router.get("/trips/{trip_id}/offline", response_model=OfflineOut)
def offline_bundle(trip_id: int, session: SessionDep, settings: SettingsDep) -> OfflineOut:
    """The active plan, checklist and bookings for the phone to keep in IndexedDB."""
    trip = get_trip_or_404(session, trip_id)
    active = session.scalar(select(Itinerary).where(Itinerary.trip_id == trip_id, Itinerary.status == "active"))
    days: list[OfflineDayOut] = []
    if active is not None:
        plan = _plan(session, settings, active)
        days = [
            OfflineDayOut(
                date=d.day,
                depot=d.depot,
                route_urls=day_route_urls(d.stops),
                stops=[
                    OfflineStopOut(
                        seq=s.seq,
                        start=f"{s.start:%H:%M}",
                        end=f"{s.end:%H:%M}",
                        label=s.label,
                        local_name=s.local_name,
                        area=s.area,
                        note=s.note,
                        google_place_id=s.google_place_id,
                        directions_url=directions_url(s.label, s.google_place_id),
                        warnings=s.warnings,
                    )
                    for s in d.stops
                ],
            )
            for d in plan.days
        ]
    return OfflineOut(
        trip=OfflineTripOut(
            id=trip.id, title=trip.title, timezone=trip.timezone, start_date=trip.start_date, end_date=trip.end_date
        ),
        generated_at=datetime.now(UTC),
        itinerary_id=active.id if active else None,
        version=active.version if active else None,
        days=days,
        checklist=[
            ChecklistItemOut(id=r.id, section=r.section, text=r.text, url=r.url, done=r.done, sort=r.sort)
            for r in checklist_rows(session, trip_id)
        ],
        bookings=bookings_for(session, settings, trip),
    )
