"""Stay candidates and the neighborhood score (approximate travel time to must/want pins)."""

from datetime import UTC, date, datetime
from typing import Literal

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

from dongseon.api.deps import DefaultsDep, HttpDep, ProfileDep, SessionDep, SettingsDep
from dongseon.api.routes.places import OptionalPlacesDep
from dongseon.api.routes.trips import get_trip_or_404
from dongseon.core.cities import CityNotFoundError, load_city
from dongseon.core.config import Settings
from dongseon.core.profile import Profile
from dongseon.db.models import GeoCache, Place, Stay, Trip
from dongseon.places.service import coords_for, get_or_create_place, store_geo
from dongseon.sources.fx import SOURCE_LABEL, Rate, get_rate
from dongseon.sources.google_places import GooglePlacesClient, LatLng, PlaceNotFoundError
from dongseon.stays.areas import ensure_area_places
from dongseon.stays.score import AirportAccess, Target, score_origin

router = APIRouter(tags=["stays"])

Status = Literal["candidate", "booked"]


class StayIn(BaseModel):
    """A stay candidate: a Google place, or a point picked on the map (e.g. an Airbnb's rough location)."""

    label: str = Field(min_length=1, max_length=100)
    google_place_id: str | None = None
    session_token: str | None = Field(default=None, max_length=100)
    user_lat: float | None = Field(default=None, ge=-90, le=90)
    user_lng: float | None = Field(default=None, ge=-180, le=180)
    check_in: date | None = None
    check_out: date | None = None
    total_amount: int | None = Field(default=None, ge=0)
    currency: str = Field(default="JPY", pattern=r"^[A-Z]{3}$")
    booking_url: str | None = Field(default=None, max_length=2000)
    note: str | None = Field(default=None, max_length=2000)
    status: Status = "candidate"

    @model_validator(mode="after")
    def _check(self) -> "StayIn":
        if not self.google_place_id and (self.user_lat is None or self.user_lng is None):
            raise ValueError("a google_place_id or a picked point is required")
        if self.check_in and self.check_out and self.check_out <= self.check_in:
            raise ValueError("check_out must be after check_in")
        return self


class StayPatch(BaseModel):
    """Editable stay fields."""

    label: str | None = Field(default=None, min_length=1, max_length=100)
    user_lat: float | None = Field(default=None, ge=-90, le=90)
    user_lng: float | None = Field(default=None, ge=-180, le=180)
    check_in: date | None = None
    check_out: date | None = None
    total_amount: int | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    booking_url: str | None = Field(default=None, max_length=2000)
    note: str | None = Field(default=None, max_length=2000)
    status: Status | None = None


class FxOut(BaseModel):
    """``1 base = rate quote`` published on ``date``."""

    base: str
    quote: str
    rate: float
    date: date
    source: str


class StayOut(BaseModel):
    """A stay with its location and nightly price."""

    id: int
    label: str
    google_place_id: str | None
    lat: float | None
    lng: float | None
    location_source: Literal["google", "user"]
    check_in: date | None
    check_out: date | None
    nights: int | None
    total_amount: int | None
    currency: str
    nightly_amount: int | None
    nightly_krw: int | None
    booking_url: str | None
    note: str | None
    status: str


class OriginOut(BaseModel):
    """Approximate travel summary from one area or stay (minutes; lower is better)."""

    kind: Literal["area", "stay"]
    id: str
    label: str
    emoji: str | None
    lat: float | None
    lng: float | None
    weighted_avg_min: int | None
    max_min: int | None
    farthest_label: str | None
    airport_min: dict[str, int]
    rank: int | None
    nightly_krw: int | None


class ScoreOut(BaseModel):
    """Neighborhood ranking for a trip. Every minute here is an approximation ("근사")."""

    targets: int
    targets_without_coords: int
    weights: dict[str, int]
    approx_as_of: date | None
    approx_source_url: str | None
    airport_notes: dict[str, str]
    fx: list[FxOut]
    origins: list[OriginOut]


def fx_out(rate: Rate | None) -> FxOut | None:
    """Serialize a stored rate with its source label."""
    if rate is None:
        return None
    return FxOut(base=rate.base, quote=rate.quote, rate=rate.rate, date=rate.date, source=SOURCE_LABEL)


def _location(stay: Stay, coords: dict[str, LatLng]) -> tuple[LatLng | None, Literal["google", "user"]]:
    if stay.user_lat is not None and stay.user_lng is not None:
        return LatLng(stay.user_lat, stay.user_lng), "user"
    gid = stay.place.google_place_id if stay.place else None
    return (coords.get(gid) if gid else None), "google"


def _stay_out(stay: Stay, coords: dict[str, LatLng], rates: dict[str, Rate | None]) -> StayOut:
    point, source = _location(stay, coords)
    nights = (stay.check_out - stay.check_in).days if stay.check_in and stay.check_out else None
    nightly = round(stay.total_amount / nights) if stay.total_amount is not None and nights else None
    rate = rates.get(stay.currency)
    return StayOut(
        id=stay.id,
        label=stay.label,
        google_place_id=stay.place.google_place_id if stay.place else None,
        lat=point.lat if point else None,
        lng=point.lng if point else None,
        location_source=source,
        check_in=stay.check_in,
        check_out=stay.check_out,
        nights=nights,
        total_amount=stay.total_amount,
        currency=stay.currency,
        nightly_amount=nightly,
        nightly_krw=round(nightly * rate.rate) if nightly is not None and rate else None,
        booking_url=stay.booking_url,
        note=stay.note,
        status=stay.status,
    )


def _stays(session: Session, trip: Trip) -> list[Stay]:
    return sorted(session.query(Stay).filter(Stay.trip_id == trip.id).all(), key=lambda s: s.id)


def _rates(session: Session, http: httpx.Client | None, stays: list[Stay]) -> dict[str, Rate | None]:
    return {c: get_rate(session, http, c) for c in {s.currency for s in stays}}


def _stay_coords(session: Session, client: OptionalPlacesDep, stays: list[Stay]) -> dict[str, LatLng]:
    ids = [s.place.google_place_id for s in stays if s.place and s.place.google_place_id]
    return coords_for(session, client, ids)


def _get_stay(session: Session, trip_id: int, stay_id: int) -> Stay:
    stay = session.get(Stay, stay_id)
    if stay is None or stay.trip_id != trip_id:
        raise HTTPException(status_code=404, detail="숙소를 찾을 수 없습니다")
    return stay


@router.get("/fx", response_model=FxOut | None)
def fx(session: SessionDep, http: HttpDep, base: str = "JPY", quote: str = "KRW") -> FxOut | None:
    """Latest reference rate (fetched at most once a day)."""
    return fx_out(get_rate(session, http, base.upper(), quote.upper()))


@router.get("/trips/{trip_id}/stays", response_model=list[StayOut])
def list_stays(trip_id: int, session: SessionDep, http: HttpDep, client: OptionalPlacesDep) -> list[StayOut]:
    """List a trip's stay candidates and bookings."""
    stays = _stays(session, get_trip_or_404(session, trip_id))
    coords = _stay_coords(session, client, stays)
    rates = _rates(session, http, stays)
    return [_stay_out(s, coords, rates) for s in stays]


@router.post("/trips/{trip_id}/stays", response_model=StayOut, status_code=201)
def create_stay(
    trip_id: int,
    body: StayIn,
    session: SessionDep,
    defaults: DefaultsDep,
    http: HttpDep,
    client: OptionalPlacesDep,
) -> StayOut:
    """Add a stay candidate."""
    trip = get_trip_or_404(session, trip_id)
    place: Place | None = None
    if body.google_place_id:
        if client is None:
            raise HTTPException(status_code=503, detail="GOOGLE_MAPS_SERVER_KEY가 설정되지 않았습니다")
        if session.get(GeoCache, body.google_place_id) is None:
            try:
                store_geo(session, client.details_geo(body.google_place_id, session_token=body.session_token))
            except PlaceNotFoundError as e:
                raise HTTPException(status_code=404, detail="Google에서 장소를 찾지 못했습니다") from e
        place = get_or_create_place(
            session,
            google_place_id=body.google_place_id,
            label=body.label,
            category=defaults.categories.fallback,
            source="search",
            source_ref=None,
        )
    stay = Stay(
        trip_id=trip.id,
        place_id=place.id if place else None,
        label=body.label.strip(),
        user_lat=None if place else body.user_lat,
        user_lng=None if place else body.user_lng,
        check_in=body.check_in,
        check_out=body.check_out,
        total_amount=body.total_amount,
        currency=body.currency,
        booking_url=body.booking_url,
        note=body.note,
        status=body.status,
        created_at=datetime.now(UTC),
    )
    session.add(stay)
    session.flush()
    session.refresh(stay)
    return _stay_out(stay, _stay_coords(session, None, [stay]), _rates(session, http, [stay]))


@router.patch("/trips/{trip_id}/stays/{stay_id}", response_model=StayOut)
def patch_stay(
    trip_id: int, stay_id: int, body: StayPatch, session: SessionDep, http: HttpDep, client: OptionalPlacesDep
) -> StayOut:
    """Edit a stay."""
    stay = _get_stay(session, trip_id, stay_id)
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(stay, key, value.strip() if key == "label" and isinstance(value, str) else value)
    if stay.check_in and stay.check_out and stay.check_out <= stay.check_in:
        raise HTTPException(status_code=422, detail="체크아웃이 체크인보다 늦어야 합니다")
    session.flush()
    return _stay_out(stay, _stay_coords(session, client, [stay]), _rates(session, http, [stay]))


@router.delete("/trips/{trip_id}/stays/{stay_id}", status_code=204)
def delete_stay(trip_id: int, stay_id: int, session: SessionDep) -> None:
    """Remove a stay."""
    session.delete(_get_stay(session, trip_id, stay_id))


@router.get("/trips/{trip_id}/stays/score", response_model=ScoreOut)
def score(
    trip_id: int,
    session: SessionDep,
    settings: SettingsDep,
    profile: ProfileDep,
    http: HttpDep,
    client: OptionalPlacesDep,
) -> ScoreOut:
    """Rank configured neighborhoods and stay candidates by approximate travel time to must/want pins."""
    return build_score(get_trip_or_404(session, trip_id), session, settings, profile, http, client)


def build_score(
    trip: Trip,
    session: Session,
    settings: Settings,
    profile: Profile,
    http: httpx.Client | None,
    client: GooglePlacesClient | None,
) -> ScoreOut:
    """Score a trip's areas and stays (shared by the stays screen and flight evaluation)."""
    try:
        city = load_city(settings.cities_path, trip.city_key)
    except CityNotFoundError as e:
        raise HTTPException(status_code=422, detail="설정에 없는 도시입니다") from e
    if city.approx is None:
        raise HTTPException(status_code=422, detail="이 도시에는 이동시간 근사 설정(approx)이 없습니다")
    weights = {k: v for k, v in profile.priority_weights.items() if k in ("must", "want")}
    pins = [p for p in trip.pins if p.priority in weights and p.place.google_place_id]
    areas = ensure_area_places(session, client, city)
    stays = _stays(session, trip)
    ids = [p.place.google_place_id for p in pins if p.place.google_place_id]
    ids += [a.google_place_id for a in areas if a.google_place_id]
    ids += [s.place.google_place_id for s in stays if s.place and s.place.google_place_id]
    coords = coords_for(session, client, [i for i in ids if i])
    targets = [
        Target(label=p.place.label, point=coords[gid], weight=weights[p.priority])
        for p in pins
        if (gid := p.place.google_place_id) and gid in coords
    ]
    hubs = {a.key: coords[a.google_place_id] for a in areas if a.kind == "hub" and a.google_place_id in coords}
    airports: dict[str, AirportAccess] = {}
    for cfg in city.airports:
        ref = next((a for a in areas if a.kind == "airport" and a.key == cfg.code), None)
        if ref is None or ref.google_place_id not in coords:
            continue
        express = [
            (hubs[f"{cfg.code}:{x.hub_label}"], x.ride_min) for x in cfg.express if f"{cfg.code}:{x.hub_label}" in hubs
        ]
        airports[cfg.code] = AirportAccess(point=coords[ref.google_place_id], express=express)
    emojis = {a.label: a.emoji for a in city.stay_areas}
    origins: list[OriginOut] = []
    for a in areas:
        if a.kind != "stay_area":
            continue
        point = coords.get(a.google_place_id) if a.google_place_id else None
        s = score_origin(point, targets, airports, city.approx) if point else None
        origins.append(
            OriginOut(
                kind="area",
                id=f"area:{a.key}",
                label=a.label,
                emoji=emojis.get(a.key),
                lat=point.lat if point else None,
                lng=point.lng if point else None,
                weighted_avg_min=s.weighted_avg_min if s else None,
                max_min=s.max_min if s else None,
                farthest_label=s.farthest_label if s else None,
                airport_min=s.airport_min if s else {},
                rank=None,
                nightly_krw=None,
            )
        )
    rates = _rates(session, http, stays)
    for st in stays:
        out = _stay_out(st, coords, rates)
        point = LatLng(out.lat, out.lng) if out.lat is not None and out.lng is not None else None
        s = score_origin(point, targets, airports, city.approx) if point else None
        origins.append(
            OriginOut(
                kind="stay",
                id=f"stay:{st.id}",
                label=st.label,
                emoji=None,
                lat=out.lat,
                lng=out.lng,
                weighted_avg_min=s.weighted_avg_min if s else None,
                max_min=s.max_min if s else None,
                farthest_label=s.farthest_label if s else None,
                airport_min=s.airport_min if s else {},
                rank=None,
                nightly_krw=out.nightly_krw,
            )
        )
    ranked = sorted((o for o in origins if o.weighted_avg_min is not None), key=lambda o: o.weighted_avg_min or 0)
    for i, o in enumerate(ranked, start=1):
        o.rank = i
    origins.sort(key=lambda o: (o.rank is None, o.rank or 0))
    return ScoreOut(
        targets=len(targets),
        targets_without_coords=len(pins) - len(targets),
        weights=weights,
        approx_as_of=city.approx.as_of,
        approx_source_url=city.approx.rail_speed_source_url,
        airport_notes={
            a.code: ", ".join(f"{x.name} ({x.hub_label}에서 최단 {x.ride_min}분)" for x in a.express)
            for a in city.airports
            if a.express
        },
        fx=[f for f in (fx_out(r) for r in rates.values()) if f is not None and f.base != f.quote],
        origins=origins,
    )
