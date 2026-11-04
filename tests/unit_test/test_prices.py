import json
from datetime import date

import httpx
import respx
from sqlalchemy import select

from dongseon.core.cities import load_city
from dongseon.core.profile import load_profile
from dongseon.db.models import FlightOption, PriceSnapshot, Stay, Trip
from dongseon.db.session import get_engine, session_scope
from dongseon.prices import refresh_prices
from dongseon.sources.fx import FRANKFURTER_URL
from dongseon.sources.ignav import BASE_URL as IGNAV
from dongseon.sources.ignav import IgnavClient, parse_round_trip
from dongseon.sources.rakuten import URL as RAKUTEN
from dongseon.sources.rakuten import RakutenClient, parse_vacant

from .conftest import CITIES, EXAMPLE_PROFILE, FIXTURES, ApiHarness
from .test_stays import FX

FARES = json.loads((FIXTURES / "ignav" / "round_trip_icn_nrt.json").read_text())
VACANT = json.loads((FIXTURES / "rakuten" / "vacant_ginza.json").read_text())


def test_parse_round_trip_dedupes_and_reads_utc() -> None:
    fares = parse_round_trip(FARES)
    assert len(fares) == 3  # the fixture repeats one itinerary
    f = fares[0]
    assert (f.amount, f.currency) == (775004, "KRW")
    assert f.outbound[0].dep_airport == "ICN" and f.outbound[0].dep_at.isoformat() == "2026-12-27T23:10:00+00:00"
    assert f.inbound[0].arr_airport == "ICN"


def test_parse_vacant_picks_cheapest_plan_and_bath_hint() -> None:
    offers = parse_vacant(VACANT)
    assert len(offers) == 3
    o = offers[0]
    assert o.first_night_total == 40150 and o.reserve_url and o.bath_hint
    assert "　" not in o.name


def test_rakuten_sends_referer_origin_and_paces_requests() -> None:
    sleeps: list[float] = []
    clock = iter([0.0, 0.1, 0.2, 0.3])
    with respx.mock:
        route = respx.get(RAKUTEN).respond(json=VACANT)
        client = RakutenClient(
            httpx.Client(),
            app_id="a",
            access_key="k",
            referer="https://example.com/",
            sleep=sleeps.append,
            clock=lambda: next(clock),
        )
        client.vacant(35.67, 139.76, date(2030, 12, 28), date(2031, 1, 1), adults=2)
        client.vacant(35.67, 139.76, date(2030, 12, 28), date(2031, 1, 1), adults=2)
        req = route.calls.last.request
        assert req.headers["Referer"] == "https://example.com/" and req.headers["Origin"] == "https://example.com"
        assert req.url.params["datumType"] == "1" and req.url.params["accessKey"] == "k"
    assert sleeps and sleeps[-1] > 1.0


def test_rakuten_not_found_means_no_vacancies() -> None:
    with respx.mock:
        respx.get(RAKUTEN).respond(404, json={"error": "not_found"})
        client = RakutenClient(httpx.Client(), app_id="a", access_key="k", referer="https://e/", sleep=lambda _s: None)
        assert client.vacant(35.0, 139.0, date(2030, 12, 28), date(2031, 1, 1), adults=2) == []


@respx.mock
def test_refresh_and_add_flow(api: ApiHarness) -> None:
    trip = api.create_trip()
    respx.get(FRANKFURTER_URL).respond(json=FX)
    ignav_route = respx.post(f"{IGNAV}/fares/round-trip").respond(json=FARES)
    respx.post(f"{IGNAV}/fares/booking-links").respond(
        json={"booking_options": [{"links": [{"url": "https://book.example.com/x"}]}]}
    )
    respx.get(RAKUTEN).respond(json=VACANT)
    api.settings.google_maps_server_key = ""  # no ranking: falls back to the configured area order
    api.settings.ignav_api_key = "k"
    eng = get_engine(api.db)
    with session_scope(eng) as s, httpx.Client() as http:
        t = s.get(Trip, trip["id"])
        assert t is not None
        summary = refresh_prices(
            s,
            trip=t,
            city=load_city(CITIES, "tokyo"),
            profile=load_profile(EXAMPLE_PROFILE),
            settings=api.settings,
            http=http,
            places=None,
            ignav=IgnavClient(http, "k"),
            rakuten=RakutenClient(http, app_id="a", access_key="k", referer="https://e/", sleep=lambda _s: None),
        )
    # example profile: ICN and GMP x HND and NRT = 4 routes; 3 areas
    assert summary.fares == {"ICN-HND": 3, "ICN-NRT": 3, "GMP-HND": 3, "GMP-NRT": 3}
    assert list(summary.hotels.values()) == [3, 3, 3]
    body = json.loads(ignav_route.calls.last.request.content)
    assert body["adults"] == 2 and body["market"] == "KR" and body["max_stops"] == 0

    fares = api.client.get(f"/api/trips/{trip['id']}/fares").json()
    assert fares["fetched_at"]
    cheapest = next(f for f in fares["items"] if f["cheapest"])
    assert cheapest["amount"] == 775004
    assert cheapest["legs"][0]["dep_local"] == "2026-12-28T08:10"
    added = api.client.post(f"/api/trips/{trip['id']}/fares/{cheapest['id']}/add").json()
    with session_scope(eng) as s:
        opt = s.get(FlightOption, added["flight_id"])
        assert opt is not None
        assert opt.booking_url == "https://book.example.com/x"
        assert [leg.direction for leg in opt.legs] == ["out", "back"]

    hotels = api.client.get(f"/api/trips/{trip['id']}/hotels").json()
    assert hotels["credit_text"] == "Supported by Rakuten Developers"
    first = hotels["areas"][0]
    assert first["area"] == "신주쿠" and first["emoji"]
    v = first["items"][0]
    assert v["nightly_jpy"] == 35900 and v["nightly_krw"] == round(35900 * 8.4587)
    stay_id = api.client.post(f"/api/trips/{trip['id']}/hotels/{v['id']}/add").json()["stay_id"]
    with session_scope(eng) as s:
        st = s.get(Stay, stay_id)
        assert st is not None
        assert (st.total_amount, st.currency) == (35900 * 4, "JPY")
        assert st.user_lat is not None and st.booking_url
        snaps = s.scalars(select(PriceSnapshot).where(PriceSnapshot.trip_id == trip["id"])).all()
        assert {(p.kind, p.key) for p in snaps} >= {("flight", "ICN-NRT"), ("hotel", "신주쿠")}
    history = api.client.get(f"/api/trips/{trip['id']}/price-history").json()
    assert any(h["key"] == "ICN-NRT" and h["min_amount"] == 775004 for h in history)
