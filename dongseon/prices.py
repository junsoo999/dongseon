"""Refresh live prices for a trip: Ignav round-trip fares and Rakuten Travel vacancies around the top areas."""

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx
from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from dongseon.api.routes.stays import build_score
from dongseon.core.cities import CityConfig, StayArea
from dongseon.core.config import Settings
from dongseon.core.profile import Profile
from dongseon.db.models import FareOffer, HotelVacancy, PriceSnapshot, Trip
from dongseon.sources.google_places import GooglePlacesClient
from dongseon.sources.ignav import Fare, IgnavClient, IgnavError
from dongseon.sources.rakuten import RakutenClient, RakutenError

logger = logging.getLogger(__name__)

TOP_AREAS = 3
KEEP_FARES_PER_ROUTE = 40  # cheapest first; enough to find good times without storing hundreds


@dataclass(frozen=True)
class PriceSummary:
    """What one refresh fetched."""

    fares: dict[str, int]  # route -> offers kept
    hotels: dict[str, int]  # area -> hotels found
    errors: list[str]


def _legs(fare: Fare) -> str:
    rows = [
        {
            "direction": direction,
            "carrier_code": s.carrier_code,
            "carrier_name": s.carrier_name,
            "flight_number": s.flight_number,
            "dep_airport": s.dep_airport,
            "dep_at": s.dep_at.isoformat(),
            "arr_airport": s.arr_airport,
            "arr_at": s.arr_at.isoformat(),
        }
        for direction, segs in (("out", fare.outbound), ("back", fare.inbound))
        for s in segs
    ]
    return json.dumps(rows, ensure_ascii=False)


def _snapshot(session: Session, trip_id: int, kind: str, key: str, amount: int, currency: str) -> None:
    today = datetime.now(UTC).date()
    row = session.scalar(
        select(PriceSnapshot).where(
            PriceSnapshot.trip_id == trip_id,
            PriceSnapshot.kind == kind,
            PriceSnapshot.key == key,
            PriceSnapshot.day == today,
        )
    )
    if row is None:
        session.add(
            PriceSnapshot(trip_id=trip_id, kind=kind, key=key, day=today, min_amount=amount, currency=currency)
        )
    else:
        row.min_amount = min(row.min_amount, amount)


def top_areas(
    session: Session,
    trip: Trip,
    city: CityConfig,
    settings: Settings,
    profile: Profile,
    http: httpx.Client | None,
    client: GooglePlacesClient | None,
) -> list[StayArea]:
    """The best-ranked configured areas that have station coordinates (config order when nothing is ranked)."""
    with_coords = [a for a in city.stay_areas if a.lat is not None and a.lng is not None]
    try:
        score = build_score(trip, session, settings, profile, http, client)
        ranks = {o.label: o.rank for o in score.origins if o.kind == "area" and o.rank is not None}
    except HTTPException:  # no ranking yet (e.g. city without approx settings)
        ranks = {}
    ordered = sorted(with_coords, key=lambda a: (a.label not in ranks, ranks.get(a.label, 0)))
    return ordered[:TOP_AREAS]


def refresh_prices(
    session: Session,
    *,
    trip: Trip,
    city: CityConfig,
    profile: Profile,
    settings: Settings,
    http: httpx.Client,
    places: GooglePlacesClient | None,
    ignav: IgnavClient | None,
    rakuten: RakutenClient | None,
    max_stops: int | None = 0,
) -> PriceSummary:
    """Fetch fares for every home airport × city airport and vacancies around the top areas, replacing old results."""
    adults = max(1, len(profile.travelers))
    now = datetime.now(UTC)
    fares: dict[str, int] = {}
    hotels: dict[str, int] = {}
    errors: list[str] = []
    if ignav is not None:
        for origin in profile.home_airports:
            for airport in city.airports:
                route = f"{origin}-{airport.code}"
                try:
                    found = ignav.round_trip(
                        origin, airport.code, trip.start_date, trip.end_date, adults=adults, max_stops=max_stops
                    )
                except (IgnavError, httpx.HTTPError, KeyError, ValueError) as e:  # keep going with other routes
                    errors.append(f"{route}: {e}")
                    continue
                found.sort(key=lambda f: f.amount)
                session.execute(delete(FareOffer).where(FareOffer.trip_id == trip.id, FareOffer.route == route))
                for f in found[:KEEP_FARES_PER_ROUTE]:
                    session.add(
                        FareOffer(
                            trip_id=trip.id,
                            route=route,
                            ignav_id=f.ignav_id,
                            amount=f.amount,
                            currency=f.currency,
                            out_carrier=f.out_carrier,
                            in_carrier=f.in_carrier,
                            legs_json=_legs(f),
                            fetched_at=now,
                        )
                    )
                if found:
                    _snapshot(session, trip.id, "flight", route, found[0].amount, found[0].currency)
                fares[route] = min(len(found), KEEP_FARES_PER_ROUTE)
    if rakuten is not None:
        for area in top_areas(session, trip, city, settings, profile, http, places):
            assert area.lat is not None and area.lng is not None
            try:
                offers = rakuten.vacant(area.lat, area.lng, trip.start_date, trip.end_date, adults=adults)
            except (RakutenError, httpx.HTTPError, KeyError, ValueError) as e:  # keep going with other areas
                errors.append(f"{area.label}: {e}")
                continue
            session.execute(
                delete(HotelVacancy).where(HotelVacancy.trip_id == trip.id, HotelVacancy.area == area.label)
            )
            for o in offers:
                session.add(
                    HotelVacancy(
                        trip_id=trip.id,
                        area=area.label,
                        hotel_no=o.hotel_no,
                        name=o.name,
                        lat=o.lat,
                        lng=o.lng,
                        nearest_station=o.nearest_station,
                        access=o.access,
                        review_average=o.review_average,
                        review_count=o.review_count,
                        thumbnail_url=o.thumbnail_url,
                        info_url=o.info_url,
                        plan_name=o.plan_name,
                        room_name=o.room_name,
                        first_night_total=o.first_night_total,
                        reserve_url=o.reserve_url,
                        bath_hint=o.bath_hint,
                        check_in=trip.start_date,
                        check_out=trip.end_date,
                        fetched_at=now,
                    )
                )
            priced = [o.first_night_total for o in offers if o.first_night_total is not None]
            if priced:
                _snapshot(session, trip.id, "hotel", area.label, min(priced), "JPY")
            hotels[area.label] = len(offers)
    session.flush()
    return PriceSummary(fares=fares, hotels=hotels, errors=errors)
