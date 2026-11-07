"""Trip mode: the today screen, per-date weather and alerts (e.g. warnings changed by the D-7 hours re-check)."""

import json
from datetime import date, datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy import select

from dongseon.api.deps import DefaultsDep, HttpDep, SessionDep
from dongseon.api.routes.itineraries import DayOut, itinerary_out
from dongseon.api.routes.stays import FxOut, fx_out
from dongseon.api.routes.trips import get_trip_or_404
from dongseon.db.models import Itinerary, TripAlert
from dongseon.sources.fx import get_rate
from dongseon.sources.open_meteo import ATTRIBUTION, ATTRIBUTION_URL
from dongseon.tripmode import trip_clock
from dongseon.tripmode.weather import DayWeather, weather_days

router = APIRouter(tags=["today"])


class WeatherOut(BaseModel):
    """One date's weather. ``precip_prob`` is the forecast maximum, or for climate the share of past years with rain."""

    date: date
    kind: Literal["forecast", "climate"]
    code: int | None
    tmax: float | None
    tmin: float | None
    precip_mm: float | None
    precip_prob: int | None
    rainy: bool
    years: int | None
    fetched_at: datetime


class WeatherListOut(BaseModel):
    """Weather for every trip date that has it, with the attribution to show."""

    days: list[WeatherOut]
    rain_probability_pct: int
    attribution: str
    attribution_url: str


class TodayOut(BaseModel):
    """What the today tab shows: the day (today during the trip, the first day before it) and its weather."""

    phase: Literal["before", "during", "after"]
    today: date
    days_until: int
    itinerary_id: int | None
    day: DayOut | None
    weather: WeatherOut | None
    fx: FxOut | None
    weather_attribution: str


class AlertOut(BaseModel):
    """An open alert for the active version."""

    id: int
    kind: str
    itinerary_id: int | None
    added: list[str]
    resolved: list[str]
    created_at: datetime


def _weather_out(w: DayWeather) -> WeatherOut:
    return WeatherOut(
        date=w.day,
        kind="forecast" if w.kind == "forecast" else "climate",
        code=w.code,
        tmax=w.tmax,
        tmin=w.tmin,
        precip_mm=w.precip_mm,
        precip_prob=w.precip_prob,
        rainy=w.rainy,
        years=w.years,
        fetched_at=w.fetched_at,
    )


def _active(session: SessionDep, trip_id: int) -> Itinerary | None:
    return session.scalar(select(Itinerary).where(Itinerary.trip_id == trip_id, Itinerary.status == "active"))


@router.get("/trips/{trip_id}/weather", response_model=WeatherListOut)
def trip_weather(trip_id: int, session: SessionDep, defaults: DefaultsDep) -> WeatherListOut:
    """Stored weather per trip date (forecast over climate); refreshed by the ``weather`` job."""
    trip = get_trip_or_404(session, trip_id)
    days = weather_days(session, trip, defaults.trip_mode)
    return WeatherListOut(
        days=[_weather_out(days[d]) for d in sorted(days)],
        rain_probability_pct=defaults.trip_mode.rain_probability_pct,
        attribution=ATTRIBUTION,
        attribution_url=ATTRIBUTION_URL,
    )


@router.get("/trips/{trip_id}/today", response_model=TodayOut)
def today(trip_id: int, session: SessionDep, defaults: DefaultsDep, http: HttpDep) -> TodayOut:
    """The day to show now, in the trip's timezone; the phone picks the current and next stop from its clock."""
    trip = get_trip_or_404(session, trip_id)
    clock = trip_clock(trip)
    shown = clock.today if clock.phase == "during" else trip.start_date if clock.phase == "before" else None
    active = _active(session, trip_id)
    day = None
    if active is not None and shown is not None:
        day = next((x for x in itinerary_out(active, trip, session).days if x.date == shown), None)
    w = weather_days(session, trip, defaults.trip_mode).get(shown) if shown else None
    return TodayOut(
        phase=clock.phase,
        today=clock.today,
        days_until=clock.days_until,
        itinerary_id=active.id if active else None,
        day=day,
        weather=_weather_out(w) if w else None,
        fx=fx_out(get_rate(session, http, "JPY", "KRW")),
        weather_attribution=ATTRIBUTION,
    )


@router.get("/trips/{trip_id}/alerts", response_model=list[AlertOut])
def trip_alerts(trip_id: int, session: SessionDep) -> list[AlertOut]:
    """Open alerts about the active version (alerts about older versions are left out)."""
    get_trip_or_404(session, trip_id)
    active = _active(session, trip_id)
    if active is None:
        return []
    rows = session.scalars(
        select(TripAlert)
        .where(TripAlert.trip_id == trip_id, TripAlert.status == "new", TripAlert.itinerary_id == active.id)
        .order_by(TripAlert.id.desc())
    )
    out = []
    for r in rows:
        p = json.loads(r.payload_json)
        out.append(
            AlertOut(
                id=r.id,
                kind=r.kind,
                itinerary_id=r.itinerary_id,
                added=p.get("added") or [],
                resolved=p.get("resolved") or [],
                created_at=r.created_at,
            )
        )
    return out


@router.post("/alerts/{alert_id}/dismiss", status_code=204)
def dismiss_alert(alert_id: int, session: SessionDep) -> Response:
    """Hide an alert."""
    row = session.get(TripAlert, alert_id)
    if row is None:
        raise HTTPException(status_code=404, detail="알림을 찾을 수 없습니다")
    row.status = "dismissed"
    session.commit()
    return Response(status_code=204)
