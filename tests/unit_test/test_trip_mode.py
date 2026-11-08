import json
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
import respx
from sqlalchemy import select

from dongseon import daily
from dongseon.core.cities import load_city
from dongseon.core.defaults import TripMode
from dongseon.core.profile import load_profile
from dongseon.db.models import HoursOverride, Itinerary, ItineraryItem, Trip, TripPin
from dongseon.db.session import get_engine, session_scope
from dongseon.planner.build import prepare
from dongseon.sources.google_places import GooglePlacesClient
from dongseon.sources.open_meteo import ARCHIVE_URL, FORECAST_URL
from dongseon.tripmode import in_window, trip_clock
from dongseon.tripmode.hours_refresh import refresh_hours
from dongseon.tripmode.weather import refresh_weather, weather_days

from .conftest import CITIES, EXAMPLE_PROFILE, ApiHarness
from .test_plan_review import _setup

FIXTURES = Path(__file__).parent / "fixtures" / "open_meteo"
TOKYO = ZoneInfo("Asia/Tokyo")
NOW = datetime(2026, 11, 8, 9, 0, tzinfo=TOKYO)  # the forecast fixture covers 2026-11-07 ~ 11-22


def _forecast() -> dict:
    return json.loads((FIXTURES / "forecast.json").read_text())


def _archive(request: httpx.Request) -> httpx.Response:
    """Past years: 10/2 °C, rain only in even years (so 2 of 5 years for 2021-2025)."""
    start = date.fromisoformat(request.url.params["start_date"])
    end = date.fromisoformat(request.url.params["end_date"])
    days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    rain = 5.0 if start.year % 2 == 0 else 0.0
    base = json.loads((FIXTURES / "archive.json").read_text())  # captured structure, values replaced
    base["daily"] = {
        "time": [d.isoformat() for d in days],
        "weather_code": [61 if rain else 1 for _ in days],
        "temperature_2m_max": [10.0 for _ in days],
        "temperature_2m_min": [2.0 for _ in days],
        "precipitation_sum": [rain for _ in days],
    }
    return httpx.Response(200, json=base)


def _trip(**kw: object) -> Trip:
    return Trip(
        title="t",
        city_key="tokyo",
        start_date=kw.get("start", date(2026, 11, 9)),
        end_date=kw.get("end", date(2026, 11, 24)),
        timezone="Asia/Tokyo",
        pace="normal",
        created_at=NOW,
    )


def test_trip_clock_and_window() -> None:
    t = _trip(start=date(2026, 11, 20), end=date(2026, 11, 24))
    assert trip_clock(t, NOW).phase == "before" and trip_clock(t, NOW).days_until == 12
    assert trip_clock(t, datetime(2026, 11, 20, 0, 30, tzinfo=TOKYO)).phase == "during"
    assert trip_clock(t, datetime(2026, 11, 19, 15, 30, tzinfo=ZoneInfo("UTC"))).phase == "during"  # 00:30 Tokyo
    assert trip_clock(t, datetime(2026, 11, 25, 0, 5, tzinfo=TOKYO)).phase == "after"
    assert not in_window(t, 7, NOW) and in_window(t, 14, NOW)


@respx.mock
def test_weather_forecast_climate_and_rainy_days(engine) -> None:
    respx.get(FORECAST_URL).respond(json=_forecast())
    archive = respx.get(ARCHIVE_URL).mock(side_effect=_archive)
    city = load_city(CITIES, "tokyo")
    cfg = TripMode()
    with session_scope(engine) as s, httpx.Client() as http:
        t = _trip()
        s.add(t)
        s.flush()
        r = refresh_weather(s, http, t, city, cfg, NOW)
        assert (r.forecast, r.climate) == (14, 16)  # forecast through 11-22; climate for every date as the fallback
        assert archive.call_count == cfg.climate_years
        days = weather_days(s, t, cfg)
        assert days[date(2026, 11, 9)].kind == "forecast" and days[date(2026, 11, 9)].rainy  # 92 %
        assert not days[date(2026, 11, 10)].rainy  # 51 % is below 60 %
        clim = days[date(2026, 11, 24)]
        assert clim.kind == "climate" and not clim.rainy
        assert (clim.tmax, clim.tmin, clim.precip_prob, clim.years) == (10.0, 2.0, 40, 5)
        # A second run keeps the climate (fresh for 30 days) and only refreshes the forecast.
        again = refresh_weather(s, http, t, city, cfg, NOW)
        assert again.climate == 0 and archive.call_count == cfg.climate_years


@respx.mock
def test_hours_refresh_alerts_on_changed_warnings(api: ApiHarness) -> None:
    tid, pins, v1 = _setup(api)
    engine = get_engine(api.db)
    museum_day = next(d["date"] for d in v1["days"] for i in d["items"] if i["pin_id"] == pins["museum"])

    def run():
        with session_scope(engine) as s, httpx.Client() as http:
            trip = s.get(Trip, tid)
            assert trip is not None
            active = s.scalar(select(Itinerary).where(Itinerary.trip_id == tid, Itinerary.status == "active"))
            assert active is not None
            ctx = prepare(
                s,
                trip=trip,
                city=load_city(CITIES, "tokyo"),
                profile=load_profile(EXAMPLE_PROFILE),
                settings=api.settings,
                http=http,
                client=GooglePlacesClient(http, "k", lambda _sku: None),
            )
            return refresh_hours(s, ctx, active)

    assert run().alert_id is None  # nothing changed since the solve
    with session_scope(engine) as s:
        place_id = s.get(TripPin, pins["museum"]).place_id  # type: ignore[union-attr]
        s.add(
            HoursOverride(
                place_id=place_id, day=date.fromisoformat(museum_day), status="closed", source="user", checked_at=NOW
            )
        )
    first = run()
    assert first.added == ["박물관: 이 날은 휴무입니다"] and first.alert_id is not None
    assert run().alert_id == first.alert_id  # same finding: the same alert, not a new one
    alerts = api.client.get(f"/api/trips/{tid}/alerts").json()
    assert [a["added"] for a in alerts] == [["박물관: 이 날은 휴무입니다"]]
    assert api.client.post(f"/api/alerts/{first.alert_id}/dismiss").status_code == 204
    assert api.client.get(f"/api/trips/{tid}/alerts").json() == []
    assert run().alert_id == first.alert_id  # a dismissed finding does not come back
    # A re-solve makes a new version; alerts about the old one are not shown.
    api.client.post(f"/api/trips/{tid}/itineraries/solve")
    assert api.client.get(f"/api/trips/{tid}/alerts").json() == []


@respx.mock
def test_saved_versions_hold_no_google_hours(api: ApiHarness) -> None:
    _tid, pins, v1 = _setup(api)
    museum = next(i for d in v1["days"] for i in d["items"] if i["pin_id"] == pins["museum"])
    assert museum["hours"] == "10:00~18:00 · Google"  # filled from process memory at read time
    with session_scope(get_engine(api.db)) as s:
        stored = [json.loads(i.warnings_json or "{}") for i in s.scalars(select(ItineraryItem))]
    google = [x for x in stored if (x.get("hours_source") or "").startswith("google")]
    assert google and all(x["hours"] in ("Google", "Google 특별 영업") for x in google)
    from dongseon.planner.hours import HOURS_CACHE

    HOURS_CACHE._rows.clear()  # once memory expires, only the source is shown
    again = api.client.get(f"/api/itineraries/{v1['id']}").json()
    assert next(i for d in again["days"] for i in d["items"] if i["pin_id"] == pins["museum"])["hours"] == "Google"


@respx.mock
def test_today_before_the_trip_shows_the_first_day(api: ApiHarness) -> None:
    tid, _pins, v1 = _setup(api)
    out = api.client.get(f"/api/trips/{tid}/today").json()
    assert out["phase"] == "before" and out["days_until"] > 0
    assert out["itinerary_id"] == v1["id"] and out["day"]["date"] == "2030-12-28"
    assert out["weather"] is None and out["fx"]["base"] == "JPY"
    w = api.client.get(f"/api/trips/{tid}/weather").json()
    assert w["days"] == [] and w["attribution"] == "Weather data by Open-Meteo.com"


def test_daily_runs_the_trip_mode_steps() -> None:
    names = [args[0] for _label, args in daily.STEPS]
    assert names[:2] == ["prices", "scout"]
    assert {"weather", "hours-refresh", "hours-research", "rain-plans"} <= set(names)
