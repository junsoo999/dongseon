"""Store Open-Meteo forecasts and past-years climate for a trip's dates, and read them back per date."""

import json
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from dongseon.core.cities import CityConfig
from dongseon.core.defaults import TripMode
from dongseon.db.models import Trip, Weather
from dongseon.sources.open_meteo import FORECAST_DAYS, DailyWeather, fetch_archive, fetch_forecast
from dongseon.tripmode import trip_clock

CLIMATE_MAX_AGE_DAYS = 30
RAIN_MM = 1.0  # a past day with at least this much precipitation counts as a rainy day


@dataclass(frozen=True)
class WeatherRefresh:
    """What a refresh stored."""

    forecast: int
    climate: int


@dataclass(frozen=True)
class DayWeather:
    """Weather for one trip date: the latest forecast if there is one, else the climate figure."""

    day: date
    kind: str  # forecast | climate
    code: int | None
    tmax: float | None
    tmin: float | None
    precip_mm: float | None
    precip_prob: int | None  # forecast: max probability; climate: share of past years with rain
    rainy: bool  # forecast probability at or above the configured threshold (climate never counts)
    fetched_at: datetime
    years: int | None = None  # climate only


def _dates(trip: Trip) -> list[date]:
    return [trip.start_date + timedelta(days=i) for i in range((trip.end_date - trip.start_date).days + 1)]


def _shift_year(d: date, years: int) -> date:
    try:
        return d.replace(year=d.year - years)
    except ValueError:  # Feb 29
        return d.replace(year=d.year - years, day=28)


def _upsert(session: Session, city_key: str, day: date, kind: str, payload: dict, now: datetime) -> None:
    row = session.scalar(select(Weather).where(Weather.city_key == city_key, Weather.day == day, Weather.kind == kind))
    if row is None:
        row = Weather(city_key=city_key, day=day, kind=kind, payload_json="{}", fetched_at=now)
        session.add(row)
    row.payload_json, row.fetched_at = json.dumps(payload), now


def _mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 1) if values else None


def climate_of(dates: list[date], years: list[list[DailyWeather]]) -> dict[date, dict]:
    """Average each trip date over past years (``years[k][i]`` is year k's value for ``dates[i]``)."""
    out: dict[date, dict] = {}
    for i, d in enumerate(dates):
        days = [y[i] for y in years if i < len(y)]
        tmax = [x.tmax for x in days if x.tmax is not None]
        tmin = [x.tmin for x in days if x.tmin is not None]
        rain = [x.precip_mm for x in days if x.precip_mm is not None]
        codes = Counter(x.code for x in days if x.code is not None)
        out[d] = {
            "code": codes.most_common(1)[0][0] if codes else None,
            "tmax": _mean(tmax),
            "tmin": _mean(tmin),
            "precip_mm": _mean(rain),
            "rain_days_pct": round(100 * sum(1 for r in rain if r >= RAIN_MM) / len(rain)) if rain else None,
            "years": len(days),
        }
    return out


def refresh_weather(
    session: Session, http: httpx.Client, trip: Trip, city: CityConfig, cfg: TripMode, now: datetime | None = None
) -> WeatherRefresh:
    """Store the forecast for trip dates within reach and the climate for dates that lack a recent one.

    Raises:
        httpx.HTTPError: A request failed (rows stored before it stay).
    """
    clock = trip_clock(trip, now)
    stamp = datetime.now(UTC)
    dates = [d for d in _dates(trip) if d >= clock.today]
    if city.center is None or not dates:
        return WeatherRefresh(0, 0)
    lat, lng = city.center.lat, city.center.lng
    forecast = 0
    horizon = clock.today + timedelta(days=FORECAST_DAYS - 1)
    if dates[0] <= horizon:
        wanted = set(dates)
        for w in fetch_forecast(http, lat, lng, trip.timezone):
            if w.day in wanted:
                payload = {
                    "code": w.code,
                    "tmax": w.tmax,
                    "tmin": w.tmin,
                    "precip_mm": w.precip_mm,
                    "precip_prob": w.precip_prob,
                }
                _upsert(session, city.key, w.day, "forecast", payload, stamp)
                forecast += 1
    since = stamp - timedelta(days=CLIMATE_MAX_AGE_DAYS)
    fresh = set(
        session.scalars(
            select(Weather.day).where(
                Weather.city_key == city.key,
                Weather.kind == "climate",
                Weather.day.in_(dates),
                Weather.fetched_at >= since,
            )
        )
    )
    climate = 0
    missing = [d for d in dates if d not in fresh]
    if missing:
        span = (missing[-1] - missing[0]).days
        years: list[list[DailyWeather]] = []
        for k in range(1, cfg.climate_years + 1):
            start = _shift_year(missing[0], k)
            got = {w.day: w for w in fetch_archive(http, lat, lng, trip.timezone, start, start + timedelta(span))}
            years.append(
                [
                    got.get(start + timedelta((d - missing[0]).days)) or DailyWeather(d, None, None, None, None)
                    for d in missing
                ]
            )
        for d, payload in climate_of(missing, years).items():
            _upsert(session, city.key, d, "climate", payload, stamp)
            climate += 1
    session.flush()
    return WeatherRefresh(forecast, climate)


def weather_days(session: Session, trip: Trip, cfg: TripMode, now: datetime | None = None) -> dict[date, DayWeather]:
    """The best weather row for each trip date (forecast over climate; past forecasts are kept for past days)."""
    dates = _dates(trip)
    rows = list(session.scalars(select(Weather).where(Weather.city_key == trip.city_key, Weather.day.in_(dates))))
    by_day: dict[date, dict[str, Weather]] = {}
    for r in rows:
        by_day.setdefault(r.day, {})[r.kind] = r
    out: dict[date, DayWeather] = {}
    for d, kinds in by_day.items():
        row = kinds.get("forecast") or kinds.get("climate")
        if row is None:
            continue
        p = json.loads(row.payload_json)
        if row.kind == "forecast":
            prob = p.get("precip_prob")
            rainy = prob is not None and prob >= cfg.rain_probability_pct
            out[d] = DayWeather(
                d,
                "forecast",
                p.get("code"),
                p.get("tmax"),
                p.get("tmin"),
                p.get("precip_mm"),
                prob,
                rainy,
                row.fetched_at,
            )
        else:
            out[d] = DayWeather(
                d,
                "climate",
                p.get("code"),
                p.get("tmax"),
                p.get("tmin"),
                p.get("precip_mm"),
                p.get("rain_days_pct"),
                False,
                row.fetched_at,
                p.get("years"),
            )
    return out
