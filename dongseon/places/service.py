"""Places and pins: add from search or URL, keep coordinates in ``geo_cache`` (≤ 30 days), resolve pending places.

Google content is used inside the request only. What is stored: ``place_id``, user labels/notes, app categories,
and coordinates in ``geo_cache`` until ``expires_at``.
"""

import math
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from dongseon.core.defaults import Categories
from dongseon.db.models import GeoCache, Place, Trip, TripPin
from dongseon.places.categories import category_for_types, dwell_for
from dongseon.places.urls import UnsupportedUrlError, expand_short_url, is_short_url, parse_maps_url
from dongseon.sources.google_places import GooglePlacesClient, LatLng, PlaceGeo, PlaceNotFoundError

GEO_TTL = timedelta(days=30)  # Service Specific Terms: cached lat/lng must be deleted within 30 days
URL_MATCH_MAX_M = 1_000.0  # a URL match farther than this from the URL's coordinates is rejected


class DuplicatePinError(ValueError):
    """Raised when the place is already pinned in the trip."""


@dataclass(frozen=True)
class UrlResolution:
    """Result of resolving a pasted URL. ``label_hint`` comes from the user's own URL text."""

    google_place_id: str | None
    label_hint: str | None
    reason: str | None = None  # why resolution failed (Korean, shown to the user)


def _now() -> datetime:
    return datetime.now(UTC)


def distance_m(a: LatLng, b: LatLng) -> float:
    """Great-circle distance in meters."""
    r = 6_371_000.0
    p1, p2 = math.radians(a.lat), math.radians(b.lat)
    dp, dl = p2 - p1, math.radians(b.lng - a.lng)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def store_geo(session: Session, geo: PlaceGeo, *, now: datetime | None = None) -> GeoCache:
    """Upsert coordinates for a place ID with a 30-day expiry."""
    now = now or _now()
    row = session.get(GeoCache, geo.place_id)
    if row is None:
        row = GeoCache(google_place_id=geo.place_id, lat=geo.lat, lng=geo.lng, fetched_at=now, expires_at=now)
        session.add(row)
    row.lat, row.lng, row.fetched_at, row.expires_at = geo.lat, geo.lng, now, now + GEO_TTL
    return row


def purge_expired_geo(session: Session, *, now: datetime | None = None) -> int:
    """Delete coordinates past their expiry. Returns the number of rows removed."""
    result = session.execute(delete(GeoCache).where(GeoCache.expires_at <= (now or _now())))
    return int(getattr(result, "rowcount", 0) or 0)


def coords_for(
    session: Session, client: GooglePlacesClient | None, place_ids: Iterable[str], *, now: datetime | None = None
) -> dict[str, LatLng]:
    """Return coordinates for place IDs, fetching missing or expired ones when a client is available.

    Places that cannot be fetched (no key, gone, free tier stop) are simply left out.
    """
    now = now or _now()
    purge_expired_geo(session, now=now)
    ids = list(dict.fromkeys(place_ids))
    rows = {r.google_place_id: r for r in session.scalars(select(GeoCache).where(GeoCache.google_place_id.in_(ids)))}
    out = {pid: LatLng(r.lat, r.lng) for pid, r in rows.items()}
    if client is None:
        return out
    for pid in ids:
        if pid in out:
            continue
        try:
            geo = client.details_geo(pid)
        except PlaceNotFoundError:
            continue
        store_geo(session, geo, now=now)
        out[pid] = LatLng(geo.lat, geo.lng)
    return out


def get_or_create_place(
    session: Session,
    *,
    google_place_id: str | None,
    label: str,
    category: str,
    source: str,
    source_ref: str | None,
    tag: str | None = None,
    note: str | None = None,
    now: datetime | None = None,
) -> Place:
    """Return the existing place for a Google ID, or create a new one."""
    now = now or _now()
    if google_place_id:
        existing = session.scalar(select(Place).where(Place.google_place_id == google_place_id))
        if existing:
            return existing
    place = Place(
        google_place_id=google_place_id,
        label=label.strip(),
        category=category,
        user_note=note,
        tag=tag,
        source=source,
        source_ref=source_ref,
        resolve_status="ok" if google_place_id else "pending",
        place_id_checked_at=now if google_place_id else None,
        created_at=now,
    )
    session.add(place)
    session.flush()
    return place


def pin_place(
    session: Session, trip: Trip, place: Place, categories: Categories, *, added_by: str = "user"
) -> TripPin:
    """Add a place to a trip with the category's default dwell time.

    Raises:
        DuplicatePinError: If the trip already has this place.
    """
    exists = session.scalar(select(TripPin).where(TripPin.trip_id == trip.id, TripPin.place_id == place.id))
    if exists:
        raise DuplicatePinError(place.id)
    pin = TripPin(
        trip_id=trip.id,
        place_id=place.id,
        priority="want",
        dwell_min=dwell_for(place.category, categories),
        added_by=added_by,
        created_at=_now(),
    )
    session.add(pin)
    session.flush()
    return pin


def add_google_place_to_trip(
    session: Session,
    client: GooglePlacesClient,
    trip: Trip,
    categories: Categories,
    *,
    google_place_id: str,
    label: str,
    source: str,
    source_ref: str | None,
    session_token: str | None = None,
) -> TripPin:
    """Add a Google place to a trip: one Essentials details call gives coordinates and the app category.

    Raises:
        PlaceNotFoundError: If the place ID is invalid.
        DuplicatePinError: If the trip already has this place.
    """
    existing = session.scalar(select(Place).where(Place.google_place_id == google_place_id))
    if existing is None:
        geo = client.details_geo(google_place_id, session_token=session_token)
        store_geo(session, geo)
        place = get_or_create_place(
            session,
            google_place_id=geo.place_id,
            label=label,
            category=category_for_types(geo.types, categories),
            source=source,
            source_ref=source_ref,
        )
    else:
        place = existing
    return pin_place(session, trip, place, categories)


def match_by_name_and_coords(
    session: Session, client: GooglePlacesClient, name: str, near: LatLng, *, region_code: str | None
) -> str | None:
    """Find the place ID named ``name`` near ``near``; ``None`` when nothing is within ``URL_MATCH_MAX_M``."""
    for pid in client.search_ids(name, region_code=region_code, near=near)[:2]:
        geo = client.details_geo(pid)
        store_geo(session, geo)
        if distance_m(near, LatLng(geo.lat, geo.lng)) <= URL_MATCH_MAX_M:
            return geo.place_id
    return None


def resolve_url(
    session: Session, http: httpx.Client, client: GooglePlacesClient, url: str, *, region_code: str | None
) -> UrlResolution:
    """Turn a pasted Google Maps URL into a place ID.

    Short links are expanded first. A URL with ``query_place_id`` is used directly; otherwise the name and
    coordinates in the URL are matched with Text Search (IDs Only) and checked by distance.
    """
    try:
        final = expand_short_url(http, url) if is_short_url(url) else url
        parsed = parse_maps_url(final)
    except UnsupportedUrlError:
        return UrlResolution(None, None, "Google 지도 링크가 아닙니다")
    except httpx.HTTPError:
        return UrlResolution(None, None, "링크를 열지 못했습니다")
    if parsed.place_id:
        try:
            geo = client.details_geo(parsed.place_id)
        except PlaceNotFoundError:
            return UrlResolution(None, parsed.name, "링크의 장소를 찾지 못했습니다")
        store_geo(session, geo)
        return UrlResolution(geo.place_id, parsed.name)
    if not parsed.name:
        return UrlResolution(None, None, "링크에서 장소 이름을 찾지 못했습니다")
    if not parsed.has_coords:
        ids = client.search_ids(parsed.name, region_code=region_code)
        return UrlResolution(ids[0] if ids else None, parsed.name, None if ids else "장소를 찾지 못했습니다")
    assert parsed.lat is not None and parsed.lng is not None
    pid = match_by_name_and_coords(
        session, client, parsed.name, LatLng(parsed.lat, parsed.lng), region_code=region_code
    )
    return UrlResolution(pid, parsed.name, None if pid else "링크 위치 근처에서 장소를 찾지 못했습니다")


@dataclass(frozen=True)
class ResolveSummary:
    """Counts from one ``places resolve`` run."""

    resolved: int
    failed: int


def resolve_pending(
    session: Session,
    http: httpx.Client,
    client: GooglePlacesClient,
    categories: Categories,
    *,
    region_code: str | None,
    retry_failed: bool = False,
    trip_id: int | None = None,
) -> ResolveSummary:
    """Resolve places that have no Google ID yet from their source URL (or label).

    A resolved ID that another place already uses is reported as failed so the user can merge by hand.
    """
    statuses = ["pending", "failed"] if retry_failed else ["pending"]
    resolved = failed = 0
    stmt = select(Place).where(Place.resolve_status.in_(statuses))
    if trip_id is not None:
        stmt = stmt.join(TripPin, TripPin.place_id == Place.id).where(TripPin.trip_id == trip_id)
    for place in session.scalars(stmt).all():
        if place.source_ref and place.source_ref.startswith("http"):
            result = resolve_url(session, http, client, place.source_ref, region_code=region_code)
            pid = result.google_place_id
        else:
            ids = client.search_ids(place.label, region_code=region_code)
            pid = ids[0] if ids else None
        taken = pid and session.scalar(select(Place.id).where(Place.google_place_id == pid, Place.id != place.id))
        if pid and not taken:
            place.google_place_id = pid
            place.resolve_status = "ok"
            place.place_id_checked_at = _now()
            if place.category == categories.fallback:
                geo = client.details_geo(pid)
                store_geo(session, geo)
                place.category = category_for_types(geo.types, categories)
            resolved += 1
        else:
            place.resolve_status = "failed"
            failed += 1
        session.flush()
    return ResolveSummary(resolved=resolved, failed=failed)
