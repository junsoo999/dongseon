"""Place search, URL resolution, and trip pins.

Autocomplete text is Google content: it is returned for display only and never stored. Labels come from the user.
"""

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from dongseon.api.deps import DefaultsDep, HttpDep, PlacesDep, SessionDep, SettingsDep, get_places_client
from dongseon.api.routes.trips import get_trip_or_404
from dongseon.core.cities import CityNotFoundError, load_city
from dongseon.core.config import Settings
from dongseon.db.models import Place, Trip, TripPin
from dongseon.places.service import (
    DuplicatePinError,
    add_google_place_to_trip,
    coords_for,
    get_or_create_place,
    pin_place,
    resolve_url,
    store_geo,
)
from dongseon.sources.google_places import GooglePlacesClient, PlaceNotFoundError

router = APIRouter(tags=["places"])

Priority = Literal["must", "want", "maybe"]
Meal = Literal["lunch", "dinner"]


class AutocompleteOut(BaseModel):
    """One autocomplete suggestion (display only; show the Google Maps attribution next to the list)."""

    google_place_id: str
    main_text: str
    secondary_text: str


class ResolveUrlIn(BaseModel):
    """A pasted Google Maps URL."""

    trip_id: int
    url: str = Field(min_length=8, max_length=2000)


class ResolveUrlOut(BaseModel):
    """URL resolution result; ``label_hint`` comes from the URL text."""

    google_place_id: str | None
    label_hint: str | None
    reason: str | None


class PinCreate(BaseModel):
    """Add a place to a trip. Without ``google_place_id`` the place is kept as pending for manual matching."""

    google_place_id: str | None = None
    label: str = Field(min_length=1, max_length=100)
    source: Literal["search", "url"]
    source_ref: str | None = Field(default=None, max_length=2000)
    session_token: str | None = Field(default=None, max_length=100)


class PinPatch(BaseModel):
    """Editable pin and place fields (label, category and memo belong to the place)."""

    priority: Priority | None = None
    dwell_min: int | None = Field(default=None, ge=5, le=720)
    meal: Meal | None = None
    clear_meal: bool = False
    note: str | None = Field(default=None, max_length=2000)
    locked_date: date | None = None
    clear_locked_date: bool = False
    label: str | None = Field(default=None, min_length=1, max_length=100)
    local_name: str | None = Field(default=None, max_length=100, description="empty string clears it")
    category: str | None = None
    google_place_id: str | None = Field(default=None, description="manual match for a pending or failed place")


class PinOut(BaseModel):
    """A pin with its place. ``lat``/``lng`` come from the 30-day coordinate cache and may be null."""

    id: int
    place_id: int
    google_place_id: str | None
    label: str
    local_name: str | None
    category: str
    user_note: str | None
    tag: str | None
    source: str
    resolve_status: str
    priority: str
    dwell_min: int
    meal: str | None
    locked_date: date | None
    note: str | None
    added_by: str
    lat: float | None
    lng: float | None


class CategoryOut(BaseModel):
    """An app category and its default dwell minutes."""

    key: str
    dwell_min: int


def get_places_client_optional(
    session: SessionDep, settings: SettingsDep, defaults: DefaultsDep, http: HttpDep
) -> GooglePlacesClient | None:
    """Places client, or ``None`` when the key is missing (read paths degrade instead of failing)."""
    if not settings.google_maps_server_key:
        return None
    return get_places_client(session, settings, defaults, http)


OptionalPlacesDep = Annotated[GooglePlacesClient | None, Depends(get_places_client_optional)]


def _region_code(settings: Settings, trip: Trip) -> str | None:
    try:
        city = load_city(settings.cities_path, trip.city_key)
    except CityNotFoundError:
        return None
    return city.region_code or city.country


def _pin_out(pin: TripPin, coords: dict) -> PinOut:
    place = pin.place
    ll = coords.get(place.google_place_id) if place.google_place_id else None
    return PinOut(
        id=pin.id,
        place_id=place.id,
        google_place_id=place.google_place_id,
        label=place.label,
        local_name=place.local_name,
        category=place.category,
        user_note=place.user_note,
        tag=place.tag,
        source=place.source,
        resolve_status=place.resolve_status,
        priority=pin.priority,
        dwell_min=pin.dwell_min,
        meal=pin.meal,
        locked_date=pin.locked_date,
        note=pin.note,
        added_by=pin.added_by,
        lat=ll.lat if ll else None,
        lng=ll.lng if ll else None,
    )


def _get_pin(session: Session, trip_id: int, pin_id: int) -> TripPin:
    pin = session.get(TripPin, pin_id)
    if pin is None or pin.trip_id != trip_id:
        raise HTTPException(status_code=404, detail="핀을 찾을 수 없습니다")
    return pin


@router.get("/categories", response_model=list[CategoryOut])
def categories(defaults: DefaultsDep) -> list[CategoryOut]:
    """List app categories with default dwell minutes."""
    return [CategoryOut(key=k, dwell_min=v) for k, v in defaults.categories.dwell_min.items()]


@router.get("/places/autocomplete", response_model=list[AutocompleteOut])
def autocomplete(
    session: SessionDep,
    settings: SettingsDep,
    client: PlacesDep,
    trip_id: int,
    q: Annotated[str, Query(min_length=2, max_length=100)],
    session_token: Annotated[str, Query(min_length=8, max_length=100)],
) -> list[AutocompleteOut]:
    """Suggest places in the trip's country (counted against the Autocomplete free tier)."""
    trip = get_trip_or_404(session, trip_id)
    suggestions = client.autocomplete(q, session_token=session_token, region_code=_region_code(settings, trip))
    return [
        AutocompleteOut(google_place_id=s.place_id, main_text=s.main_text, secondary_text=s.secondary_text)
        for s in suggestions
    ]


@router.post("/places/resolve-url", response_model=ResolveUrlOut)
def resolve_url_route(
    body: ResolveUrlIn, session: SessionDep, settings: SettingsDep, http: HttpDep, client: PlacesDep
) -> ResolveUrlOut:
    """Resolve a pasted Google Maps URL (short links included) to a place ID."""
    trip = get_trip_or_404(session, body.trip_id)
    result = resolve_url(session, http, client, body.url, region_code=_region_code(settings, trip))
    return ResolveUrlOut(google_place_id=result.google_place_id, label_hint=result.label_hint, reason=result.reason)


@router.get("/trips/{trip_id}/pins", response_model=list[PinOut])
def list_pins(trip_id: int, session: SessionDep, client: OptionalPlacesDep) -> list[PinOut]:
    """List a trip's pins with cached coordinates (fetching expired ones when the key is set)."""
    trip = get_trip_or_404(session, trip_id)
    pins = sorted(trip.pins, key=lambda p: p.id)
    coords = coords_for(session, client, [p.place.google_place_id for p in pins if p.place.google_place_id])
    return [_pin_out(p, coords) for p in pins]


@router.post("/trips/{trip_id}/pins", response_model=PinOut, status_code=201)
def create_pin(
    trip_id: int, body: PinCreate, session: SessionDep, defaults: DefaultsDep, client: OptionalPlacesDep
) -> PinOut:
    """Add a place to a trip (one Essentials details call for a new Google place)."""
    trip = get_trip_or_404(session, trip_id)
    cats = defaults.categories
    try:
        if body.google_place_id:
            if client is None:
                raise HTTPException(status_code=503, detail="GOOGLE_MAPS_SERVER_KEY가 설정되지 않았습니다")
            pin = add_google_place_to_trip(
                session,
                client,
                trip,
                cats,
                google_place_id=body.google_place_id,
                label=body.label,
                source=body.source,
                source_ref=body.source_ref,
                session_token=body.session_token,
            )
        else:
            place = get_or_create_place(
                session,
                google_place_id=None,
                label=body.label,
                category=cats.fallback,
                source=body.source,
                source_ref=body.source_ref,
            )
            pin = pin_place(session, trip, place, cats)
    except DuplicatePinError as e:
        raise HTTPException(status_code=409, detail="이미 이 여행에 있는 장소입니다") from e
    except PlaceNotFoundError as e:
        raise HTTPException(status_code=404, detail="Google에서 장소를 찾지 못했습니다") from e
    session.refresh(pin)
    coords = coords_for(session, None, [pin.place.google_place_id] if pin.place.google_place_id else [])
    return _pin_out(pin, coords)


@router.patch("/trips/{trip_id}/pins/{pin_id}", response_model=PinOut)
def patch_pin(
    trip_id: int,
    pin_id: int,
    body: PinPatch,
    session: SessionDep,
    defaults: DefaultsDep,
    client: OptionalPlacesDep,
) -> PinOut:
    """Edit a pin, its place's label/category/memo, or manually match a pending place."""
    pin = _get_pin(session, trip_id, pin_id)
    place = pin.place
    for key in ("priority", "dwell_min", "note"):
        value = getattr(body, key)
        if value is not None:
            setattr(pin, key, value)
    if body.meal is not None or body.clear_meal:
        pin.meal = None if body.clear_meal else body.meal
    if body.locked_date is not None or body.clear_locked_date:
        pin.locked_date = None if body.clear_locked_date else body.locked_date
    if body.label is not None:
        place.label = body.label.strip()
    if body.local_name is not None:
        place.local_name = body.local_name.strip() or None
    if body.category is not None:
        if body.category not in defaults.categories.dwell_min:
            raise HTTPException(status_code=422, detail="알 수 없는 카테고리입니다")
        place.category = body.category
    if body.google_place_id is not None and body.google_place_id != place.google_place_id:
        taken = session.scalar(select(Place.id).where(Place.google_place_id == body.google_place_id))
        if taken:
            raise HTTPException(status_code=409, detail="이미 다른 장소에 연결된 Google 장소입니다")
        if client is None:
            raise HTTPException(status_code=503, detail="GOOGLE_MAPS_SERVER_KEY가 설정되지 않았습니다")
        try:
            geo = client.details_geo(body.google_place_id)
        except PlaceNotFoundError as e:
            raise HTTPException(status_code=404, detail="Google에서 장소를 찾지 못했습니다") from e
        store_geo(session, geo)
        place.google_place_id = geo.place_id
        place.resolve_status = "ok"
    session.flush()
    coords = coords_for(session, None, [place.google_place_id] if place.google_place_id else [])
    return _pin_out(pin, coords)


@router.delete("/trips/{trip_id}/pins/{pin_id}", status_code=204)
def delete_pin(trip_id: int, pin_id: int, session: SessionDep) -> None:
    """Remove a pin from a trip (the place itself is kept for other trips)."""
    session.delete(_get_pin(session, trip_id, pin_id))
