"""AI suggestions (accept / reject) and search deep links for flights and stays."""

import json
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from dongseon.api.deps import DefaultsDep, HttpDep, ProfileDep, SessionDep, SettingsDep
from dongseon.api.routes.places import OptionalPlacesDep
from dongseon.api.routes.stays import build_score
from dongseon.api.routes.trips import get_trip_or_404
from dongseon.core.cities import CityNotFoundError, load_city
from dongseon.db.models import AiSuggestion, GeoCache, Stay, TripPin
from dongseon.links import flight_links, stay_links
from dongseon.llm.research import PlaceItem, StayItem
from dongseon.places.service import DuplicatePinError, get_or_create_place, pin_place

router = APIRouter(tags=["scout"])


class AiSuggestionOut(BaseModel):
    """A pending or decided AI suggestion. Everything in it is AI-generated ("AI 제안") with sources."""

    id: int
    kind: Literal["place", "stay"]
    status: str
    google_place_id: str | None
    lat: float | None
    lng: float | None
    created_at: datetime
    place: PlaceItem | None
    stay: StayItem | None


class AcceptOut(BaseModel):
    """What accepting created."""

    pin_id: int | None
    stay_id: int | None


class LinkOut(BaseModel):
    """An outbound search link."""

    site: str
    label: str
    url: str


class AreaLinksOut(BaseModel):
    """Booking-site searches for one area."""

    area: str
    emoji: str | None
    rank: int | None
    links: list[LinkOut]


class SearchLinksOut(BaseModel):
    """Search links with the trip's route, dates and travelers filled in."""

    flights: list[LinkOut]
    stays: list[AreaLinksOut]


def _out(s: AiSuggestion, session: SessionDep) -> AiSuggestionOut:
    data = json.loads(s.payload_json)
    geo = session.get(GeoCache, s.google_place_id) if s.google_place_id else None
    return AiSuggestionOut(
        id=s.id,
        kind="place" if s.kind == "place" else "stay",
        status=s.status,
        google_place_id=s.google_place_id,
        lat=geo.lat if geo else None,
        lng=geo.lng if geo else None,
        created_at=s.created_at,
        place=PlaceItem.model_validate(data) if s.kind == "place" else None,
        stay=StayItem.model_validate(data) if s.kind == "stay" else None,
    )


def _get(session: SessionDep, suggestion_id: int) -> AiSuggestion:
    s = session.get(AiSuggestion, suggestion_id)
    if s is None:
        raise HTTPException(status_code=404, detail="추천을 찾을 수 없습니다")
    if s.status != "pending":
        raise HTTPException(status_code=409, detail="이미 처리한 추천입니다")
    return s


@router.get("/trips/{trip_id}/suggestions", response_model=list[AiSuggestionOut])
def list_suggestions(
    trip_id: int,
    session: SessionDep,
    kind: Literal["place", "stay"] | None = None,
    status: Literal["pending", "accepted", "rejected"] = "pending",
) -> list[AiSuggestionOut]:
    """List AI suggestions for a trip, newest first."""
    get_trip_or_404(session, trip_id)
    stmt = select(AiSuggestion).where(AiSuggestion.trip_id == trip_id, AiSuggestion.status == status)
    if kind:
        stmt = stmt.where(AiSuggestion.kind == kind)
    return [_out(s, session) for s in session.scalars(stmt.order_by(AiSuggestion.created_at.desc(), AiSuggestion.id))]


@router.post("/suggestions/{suggestion_id}/accept", response_model=AcceptOut)
def accept(suggestion_id: int, session: SessionDep, defaults: DefaultsDep) -> AcceptOut:
    """Turn a place suggestion into a "maybe" pin, or a stay suggestion into a stay candidate."""
    s = _get(session, suggestion_id)
    trip = get_trip_or_404(session, s.trip_id)
    data = json.loads(s.payload_json)
    source_url = data["sources"][0]["url"]
    if s.kind == "place":
        item = PlaceItem.model_validate(data)
        place = get_or_create_place(
            session,
            google_place_id=s.google_place_id,
            label=item.name,
            category=item.category,
            source="ai",
            source_ref=source_url,
            note=item.why,
        )
        try:
            pin = pin_place(session, trip, place, defaults.categories, added_by="ai")
        except DuplicatePinError:
            pin = session.scalar(select(TripPin).where(TripPin.trip_id == trip.id, TripPin.place_id == place.id))
        assert pin is not None
        pin.priority = "maybe"
        pin.meal = item.meal
        s.status = "accepted"
        session.flush()
        return AcceptOut(pin_id=pin.id, stay_id=None)
    item = StayItem.model_validate(data)
    place = None
    if s.google_place_id:
        place = get_or_create_place(
            session,
            google_place_id=s.google_place_id,
            label=item.name,
            category=defaults.categories.fallback,
            source="ai",
            source_ref=source_url,
        )
    price = (
        f"1박 {item.nightly_low:,}~{item.nightly_high:,} {item.currency}"
        if item.nightly_low is not None and item.nightly_high is not None
        else None
    )
    note = " / ".join(x for x in (item.why, price, item.price_note) if x)
    if place is None:
        raise HTTPException(status_code=422, detail="Google 장소를 찾지 못한 숙소는 직접 추가해 주세요")
    stay = Stay(
        trip_id=trip.id,
        place_id=place.id,
        label=item.name,
        check_in=trip.start_date,
        check_out=trip.end_date,
        currency=item.currency,
        booking_url=source_url,
        note=f"AI 제안: {note}",
        created_at=datetime.now(UTC),
    )
    session.add(stay)
    s.status = "accepted"
    session.flush()
    return AcceptOut(pin_id=None, stay_id=stay.id)


@router.post("/suggestions/{suggestion_id}/reject", status_code=204)
def reject(suggestion_id: int, session: SessionDep) -> None:
    """Reject a suggestion; later research skips it."""
    _get(session, suggestion_id).status = "rejected"


@router.get("/trips/{trip_id}/search-links", response_model=SearchLinksOut)
def search_links(
    trip_id: int,
    session: SessionDep,
    settings: SettingsDep,
    profile: ProfileDep,
    http: HttpDep,
    client: OptionalPlacesDep,
) -> SearchLinksOut:
    """Flight searches from the home airports and Airbnb/Booking searches for the top areas."""
    trip = get_trip_or_404(session, trip_id)
    try:
        city = load_city(settings.cities_path, trip.city_key)
    except CityNotFoundError as e:
        raise HTTPException(status_code=422, detail="설정에 없는 도시입니다") from e
    adults = max(1, len(profile.travelers))
    flights = [
        LinkOut(site=lk.site, label=lk.label, url=lk.url)
        for origin in profile.home_airports
        if city.iata_city
        for lk in flight_links(origin, city.iata_city, trip.start_date, trip.end_date, adults)
    ]
    try:
        score = build_score(trip, session, settings, profile, http, client)
        ranks = {o.label: o.rank for o in score.origins if o.kind == "area"}
    except HTTPException:
        ranks = {}
    areas = sorted(city.stay_areas, key=lambda a: (ranks.get(a.label) is None, ranks.get(a.label) or 0))
    stays = [
        AreaLinksOut(
            area=a.label,
            emoji=a.emoji,
            rank=ranks.get(a.label),
            links=[
                LinkOut(site=lk.site, label=lk.label, url=lk.url)
                for lk in stay_links(
                    a.search_name or a.label, city.name_en or city.name, trip.start_date, trip.end_date, adults
                )
            ],
        )
        for a in areas
        if a.search_name
    ]
    return SearchLinksOut(flights=flights, stays=stays)
