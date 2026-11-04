"""Live prices: Ignav fares ranked by cost per usable local hour, Rakuten Travel vacancies per top area."""

import json
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from dongseon.api.deps import HttpDep, ProfileDep, SessionDep, SettingsDep
from dongseon.api.routes.flights import _reference
from dongseon.api.routes.places import OptionalPlacesDep
from dongseon.api.routes.stays import build_score
from dongseon.api.routes.trips import get_trip_or_404
from dongseon.core.airports import load_airports
from dongseon.core.cities import load_city
from dongseon.db.models import FareOffer, FlightLeg, FlightOption, HotelVacancy, PriceSnapshot, Stay
from dongseon.flights.evaluate import LegTimes, evaluate
from dongseon.sources.fx import get_rate
from dongseon.sources.ignav import IgnavClient, IgnavError
from dongseon.sources.rakuten import CREDIT_TEXT, CREDIT_URL

router = APIRouter(tags=["prices"])

LOCAL_FMT = "%Y-%m-%dT%H:%M"
SHOW_FARES = 12


class FareLegOut(BaseModel):
    """One flight of a fare, in local time."""

    direction: str
    flight: str
    carrier: str | None
    dep_airport: str
    dep_local: str
    arr_airport: str
    arr_local: str


class FareOut(BaseModel):
    """A fare with its usable local time (airport↔stay minutes are approximations)."""

    id: int
    route: str
    amount: int
    currency: str
    total_krw: int | None
    legs: list[FareLegOut]
    usable_min: int | None
    krw_per_usable_hour: int | None
    best_value: bool
    cheapest: bool


class FaresOut(BaseModel):
    """Latest fares for a trip."""

    fetched_at: datetime | None
    reference_label: str | None
    reference_kind: str
    items: list[FareOut]


class VacancyOut(BaseModel):
    """A hotel with vacancies (Rakuten Travel)."""

    id: int
    name: str
    nearest_station: str | None
    review_average: float | None
    review_count: int | None
    thumbnail_url: str | None
    info_url: str | None
    room_name: str | None
    nightly_jpy: int | None
    nightly_krw: int | None
    bath_hint: bool
    reserve_url: str | None


class AreaVacanciesOut(BaseModel):
    """Vacancies around one area's main station."""

    area: str
    emoji: str | None
    items: list[VacancyOut]


class HotelsOut(BaseModel):
    """Latest vacancies for a trip, with the required Rakuten credit."""

    fetched_at: datetime | None
    check_in: date | None
    check_out: date | None
    credit_text: str
    credit_url: str
    areas: list[AreaVacanciesOut]


class HistoryPoint(BaseModel):
    """Lowest price on one day."""

    kind: str
    key: str
    day: date
    min_amount: int
    currency: str


class AddedOut(BaseModel):
    """What was created from an offer."""

    flight_id: int | None
    stay_id: int | None


def _legs(offer: FareOffer) -> list[dict]:
    return json.loads(offer.legs_json)


@router.get("/trips/{trip_id}/fares", response_model=FaresOut)
def fares(
    trip_id: int,
    session: SessionDep,
    settings: SettingsDep,
    profile: ProfileDep,
    http: HttpDep,
    client: OptionalPlacesDep,
) -> FaresOut:
    """Latest fares, best value (KRW per usable hour) first, plus the cheapest."""
    trip = get_trip_or_404(session, trip_id)
    offers = session.scalars(select(FareOffer).where(FareOffer.trip_id == trip.id)).all()
    if not offers:
        return FaresOut(fetched_at=None, reference_label=None, reference_kind="none", items=[])
    airports = load_airports(settings.airports_file)
    try:
        score = build_score(trip, session, settings, profile, http, client)
    except HTTPException:
        score = None
    ref_label, ref_kind, access = _reference(session, trip, score)
    rates = {c: get_rate(session, http, c) for c in {o.currency for o in offers}}

    def tz(code: str) -> ZoneInfo:
        info = airports.get(code)
        return info.tz if info else ZoneInfo("UTC")

    rows: list[FareOut] = []
    for o in offers:
        legs = _legs(o)
        times = [
            LegTimes(
                leg["direction"],
                leg["dep_airport"],
                datetime.fromisoformat(leg["dep_at"]),
                leg["arr_airport"],
                datetime.fromisoformat(leg["arr_at"]),
            )
            for leg in legs
        ]
        ev = evaluate(times, profile.buffers_min, access)
        rate = rates.get(o.currency)
        krw = round(o.amount * rate.rate) if rate else None
        usable = ev.usable_min if ev else None
        rows.append(
            FareOut(
                id=o.id,
                route=o.route,
                amount=o.amount,
                currency=o.currency,
                total_krw=krw,
                legs=[
                    FareLegOut(
                        direction=leg["direction"],
                        flight=f"{leg['carrier_code']}{leg['flight_number']}",
                        carrier=leg.get("carrier_name"),
                        dep_airport=leg["dep_airport"],
                        dep_local=datetime.fromisoformat(leg["dep_at"])
                        .astimezone(tz(leg["dep_airport"]))
                        .strftime(LOCAL_FMT),
                        arr_airport=leg["arr_airport"],
                        arr_local=datetime.fromisoformat(leg["arr_at"])
                        .astimezone(tz(leg["arr_airport"]))
                        .strftime(LOCAL_FMT),
                    )
                    for leg in legs
                ],
                usable_min=usable,
                krw_per_usable_hour=round(krw / (usable / 60)) if krw is not None and usable and usable > 0 else None,
                best_value=False,
                cheapest=False,
            )
        )
    by_value = sorted(rows, key=lambda r: (r.krw_per_usable_hour is None, r.krw_per_usable_hour or 0, r.amount))
    cheapest = min(rows, key=lambda r: r.total_krw if r.total_krw is not None else r.amount)
    cheapest.cheapest = True
    if by_value and by_value[0].krw_per_usable_hour is not None:
        by_value[0].best_value = True
    shown = by_value[:SHOW_FARES]
    if cheapest not in shown:
        shown.append(cheapest)
    return FaresOut(
        fetched_at=max(o.fetched_at for o in offers), reference_label=ref_label, reference_kind=ref_kind, items=shown
    )


@router.post("/trips/{trip_id}/fares/{fare_id}/add", response_model=AddedOut, status_code=201)
def add_fare(trip_id: int, fare_id: int, session: SessionDep, settings: SettingsDep, http: HttpDep) -> AddedOut:
    """Copy a fare into the trip's flight options, with a booking link when Ignav has one."""
    trip = get_trip_or_404(session, trip_id)
    offer = session.get(FareOffer, fare_id)
    if offer is None or offer.trip_id != trip.id:
        raise HTTPException(status_code=404, detail="운임을 찾을 수 없습니다")
    booking_url = None
    if settings.ignav_api_key:
        try:
            booking_url = IgnavClient(http, settings.ignav_api_key).booking_url(offer.ignav_id)
        except IgnavError:
            booking_url = None
    legs = _legs(offer)
    flights = " / ".join(f"{leg['carrier_code']}{leg['flight_number']}" for leg in legs)
    option = FlightOption(
        trip_id=trip.id,
        label=f"{offer.out_carrier or ''} {flights}".strip(),
        total_amount=offer.amount,
        currency=offer.currency,
        booking_url=booking_url,
        note=f"Ignav 운임 ({offer.fetched_at:%Y-%m-%d %H:%M} UTC 조회). 예약 전 가격 확인 필요",
        created_at=datetime.now(UTC),
    )
    for i, leg in enumerate(legs):
        option.legs.append(
            FlightLeg(
                direction=leg["direction"],
                seq=i,
                carrier=leg.get("carrier_name"),
                flight_no=f"{leg['carrier_code']}{leg['flight_number']}",
                dep_airport=leg["dep_airport"],
                dep_at=datetime.fromisoformat(leg["dep_at"]),
                arr_airport=leg["arr_airport"],
                arr_at=datetime.fromisoformat(leg["arr_at"]),
            )
        )
    session.add(option)
    session.flush()
    return AddedOut(flight_id=option.id, stay_id=None)


@router.get("/trips/{trip_id}/hotels", response_model=HotelsOut)
def hotels(trip_id: int, session: SessionDep, settings: SettingsDep, http: HttpDep) -> HotelsOut:
    """Latest vacancies per area, cheapest first."""
    trip = get_trip_or_404(session, trip_id)
    rows = session.scalars(
        select(HotelVacancy).where(HotelVacancy.trip_id == trip.id).order_by(HotelVacancy.first_night_total)
    ).all()
    city = load_city(settings.cities_path, trip.city_key)
    emojis = {a.label: a.emoji for a in city.stay_areas}
    order = [a.label for a in city.stay_areas]
    rate = get_rate(session, http, "JPY") if rows else None
    areas: dict[str, list[VacancyOut]] = {}
    for r in rows:
        areas.setdefault(r.area, []).append(
            VacancyOut(
                id=r.id,
                name=r.name,
                nearest_station=r.nearest_station,
                review_average=r.review_average,
                review_count=r.review_count,
                thumbnail_url=r.thumbnail_url,
                info_url=r.info_url,
                room_name=r.room_name,
                nightly_jpy=r.first_night_total,
                nightly_krw=round(r.first_night_total * rate.rate) if r.first_night_total and rate else None,
                bath_hint=r.bath_hint,
                reserve_url=r.reserve_url,
            )
        )
    return HotelsOut(
        fetched_at=max((r.fetched_at for r in rows), default=None),
        check_in=rows[0].check_in if rows else None,
        check_out=rows[0].check_out if rows else None,
        credit_text=CREDIT_TEXT,
        credit_url=CREDIT_URL,
        areas=[
            AreaVacanciesOut(area=a, emoji=emojis.get(a), items=items)
            for a, items in sorted(areas.items(), key=lambda kv: order.index(kv[0]) if kv[0] in order else 99)
        ],
    )


@router.post("/trips/{trip_id}/hotels/{vacancy_id}/add", response_model=AddedOut, status_code=201)
def add_hotel(trip_id: int, vacancy_id: int, session: SessionDep) -> AddedOut:
    """Copy a vacancy into the trip's stay candidates (total estimated from the first night's rate)."""
    trip = get_trip_or_404(session, trip_id)
    v = session.get(HotelVacancy, vacancy_id)
    if v is None or v.trip_id != trip.id:
        raise HTTPException(status_code=404, detail="숙소를 찾을 수 없습니다")
    nights = (v.check_out - v.check_in).days
    stay = Stay(
        trip_id=trip.id,
        label=v.name,
        user_lat=v.lat,
        user_lng=v.lng,
        check_in=v.check_in,
        check_out=v.check_out,
        total_amount=v.first_night_total * nights if v.first_night_total is not None else None,
        currency="JPY",
        booking_url=v.reserve_url or v.info_url,
        note=f"楽天トラベル {v.room_name or ''} · 총액은 첫날 요금 × {nights}박 추정 ({v.fetched_at:%Y-%m-%d} 조회)",
        created_at=datetime.now(UTC),
    )
    session.add(stay)
    session.flush()
    return AddedOut(flight_id=None, stay_id=stay.id)


@router.get("/trips/{trip_id}/price-history", response_model=list[HistoryPoint])
def price_history(trip_id: int, session: SessionDep) -> list[HistoryPoint]:
    """Daily lowest prices per route and area."""
    get_trip_or_404(session, trip_id)
    rows = session.scalars(
        select(PriceSnapshot).where(PriceSnapshot.trip_id == trip_id).order_by(PriceSnapshot.day)
    ).all()
    return [
        HistoryPoint(kind=r.kind, key=r.key, day=r.day, min_amount=r.min_amount, currency=r.currency) for r in rows
    ]
