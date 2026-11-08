"""The exportable view of a plan: app data only (order, planned times, the user's labels and notes)."""

import json
from dataclasses import dataclass
from datetime import date, datetime
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from dongseon.core.cities import CityConfig
from dongseon.db.models import Itinerary, Trip, TripPin
from dongseon.matrix.approx import distance_km
from dongseon.places.service import coords_for
from dongseon.sources.google_places import LatLng

AREA_RADIUS_KM = 2.5  # a stop counts as "in" a configured stay area within this distance of its main station
ROUTE_STOPS = 5  # Google Maps URLs take at most 3 waypoints on mobile: origin + 3 + destination


@dataclass(frozen=True)
class Stop:
    """One planned visit. ``area`` is the nearest configured stay area (our config), never Google data."""

    item_id: int
    day: date
    seq: int
    start: datetime  # aware, trip timezone
    end: datetime
    label: str
    local_name: str | None
    area: str | None
    note: str | None
    google_place_id: str | None
    warnings: list[str]


@dataclass(frozen=True)
class PlanDay:
    """A day of the plan and its start point."""

    day: date
    depot: str
    stops: list[Stop]


@dataclass(frozen=True)
class PlanExport:
    """Everything an export needs."""

    trip: Trip
    city: CityConfig
    version: int
    itinerary_id: int
    days: list[PlanDay]


def directions_url(label: str, google_place_id: str | None, mode: str | None = "transit") -> str:
    """A Google Maps URLs directions link from the current location to one stop."""
    q = {"api": "1", "destination": label}
    if google_place_id:
        q["destination_place_id"] = google_place_id
    if mode:
        q["travelmode"] = mode
    return "https://www.google.com/maps/dir/?" + urlencode(q)


def day_route_urls(stops: list[Stop]) -> list[str]:
    """Google Maps URLs routes through a day's stops, split into overlapping legs of ``ROUTE_STOPS`` stops.

    Waypoints are not used with transit, so the links leave the mode to the Maps app.
    """
    if not stops:
        return []
    urls = []
    i = 0
    while True:
        chunk = stops[i : i + ROUTE_STOPS]
        first, last, mid = chunk[0], chunk[-1], chunk[1:-1]
        q = {"api": "1", "destination": last.label}
        if len(chunk) > 1:
            q["origin"] = first.label
            if first.google_place_id:
                q["origin_place_id"] = first.google_place_id
        if last.google_place_id:
            q["destination_place_id"] = last.google_place_id
        if mid:
            q["waypoints"] = "|".join(s.label for s in mid)
            if all(s.google_place_id for s in mid):
                q["waypoint_place_ids"] = "|".join(s.google_place_id or "" for s in mid)
        urls.append("https://www.google.com/maps/dir/?" + urlencode(q))
        if i + ROUTE_STOPS >= len(stops):
            return urls
        i += ROUTE_STOPS - 1  # the next leg starts where this one ended


def _note(*parts: str | None) -> str | None:
    text = " / ".join(p.strip() for p in parts if p and p.strip())
    return text or None


def build_export(session: Session, it: Itinerary, trip: Trip, city: CityConfig) -> PlanExport:
    """Collect a version's visits with the user's labels, notes and local names.

    Opening hours and travel minutes are left out on purpose: Google hours may not leave the app, and every time
    here is the plan's own estimate.
    """
    tz = ZoneInfo(trip.timezone)
    stats = json.loads(it.solver_stats_json or "{}")
    pins = {p.id: p for p in session.scalars(select(TripPin).where(TripPin.trip_id == trip.id))}
    gids = [p.place.google_place_id for p in pins.values() if p.place.google_place_id]
    coords = coords_for(session, None, gids)
    areas = [a for a in city.stay_areas if a.lat is not None and a.lng is not None]

    def area_of(gid: str | None) -> str | None:
        ll = coords.get(gid) if gid else None
        if ll is None or not areas:
            return None
        best = min(areas, key=lambda a: distance_km(ll, LatLng(a.lat or 0.0, a.lng or 0.0)))
        km = distance_km(ll, LatLng(best.lat or 0.0, best.lng or 0.0))
        return best.label if km <= AREA_RADIUS_KM else None

    days = []
    for day_iso, info in (stats.get("days") or {}).items():
        d = date.fromisoformat(day_iso)
        stops = []
        for item in (x for x in it.items if x.day == d and x.kind in ("visit", "meal")):
            pin = pins.get(item.pin_id) if item.pin_id else None
            place = pin.place if pin else None
            gid = place.google_place_id if place else None
            extra = json.loads(item.warnings_json or "{}")
            stops.append(
                Stop(
                    item_id=item.id,
                    day=d,
                    seq=len(stops) + 1,
                    start=item.start_at.astimezone(tz),
                    end=item.end_at.astimezone(tz),
                    label=item.label,
                    local_name=place.local_name if place else None,
                    area=area_of(gid),
                    note=_note(place.user_note if place else None, pin.note if pin else None),
                    google_place_id=gid,
                    warnings=list(extra.get("warnings") or []),
                )
            )
        days.append(PlanDay(day=d, depot=info.get("depot") or "", stops=stops))
    days.sort(key=lambda x: x.day)
    return PlanExport(trip=trip, city=city, version=it.version, itinerary_id=it.id, days=days)
