import json
from datetime import UTC, date, datetime, timedelta

import httpx
import respx
from sqlalchemy import select

from dongseon.core.cities import Approx, load_city
from dongseon.db.models import FxRate
from dongseon.db.session import session_scope
from dongseon.matrix.approx import approx_leg, distance_km
from dongseon.sources.fx import FRANKFURTER_URL, get_rate
from dongseon.sources.google_places import BASE_URL, LatLng
from dongseon.stays.score import AirportAccess, Target, airport_minutes, score_origin

from .conftest import CITIES, FIXTURES, ApiHarness, places_fixture

_approx = load_city(CITIES, "tokyo").approx
assert _approx is not None
PARAMS: Approx = _approx
FX = json.loads((FIXTURES / "frankfurter" / "latest_jpy_krw.json").read_text())


def _offset(p: LatLng, km_north: float) -> LatLng:
    return LatLng(p.lat + km_north / 111.2, p.lng)


ORIGIN = LatLng(35.0, 139.0)


def test_distance_km() -> None:
    assert abs(distance_km(ORIGIN, _offset(ORIGIN, 10)) - 10) < 0.05


def test_short_legs_walk_and_long_legs_take_rail() -> None:
    short = approx_leg(ORIGIN, _offset(ORIGIN, 0.5), PARAMS)
    assert short.mode == "walk"
    assert short.minutes == round(0.5 * 1.3 * 1000 / 80)  # 8
    far = approx_leg(ORIGIN, _offset(ORIGIN, 10), PARAMS)
    assert far.mode == "rail"
    assert far.minutes == round(10 + 2 + 10 * 1.3 / 33 * 60)  # 36
    assert approx_leg(ORIGIN, ORIGIN, PARAMS).minutes == 1


def test_score_is_priority_weighted() -> None:
    near, far = _offset(ORIGIN, 0.5), _offset(ORIGIN, 10)
    s = score_origin(
        ORIGIN,
        [Target("가까움", near, 100), Target("멂", far, 10)],
        {"HND": AirportAccess(_offset(ORIGIN, 20), [])},
        PARAMS,
    )
    assert s.weighted_avg_min == round((100 * 8 + 10 * 36) / 110)
    assert (s.max_min, s.farthest_label) == (36, "멂")
    assert s.airport_min["HND"] > 36
    assert score_origin(ORIGIN, [], {}, PARAMS).weighted_avg_min is None


def test_express_link_beats_direct_estimate_only_when_faster() -> None:
    airport = _offset(ORIGIN, 60)
    hub_near = _offset(ORIGIN, 1)
    direct = approx_leg(ORIGIN, airport, PARAMS).minutes
    via = approx_leg(ORIGIN, hub_near, PARAMS).minutes + 2 + 36
    assert via < direct
    assert airport_minutes(ORIGIN, AirportAccess(airport, [(hub_near, 36)]), PARAMS) == via
    assert airport_minutes(ORIGIN, AirportAccess(airport, [(_offset(ORIGIN, -50), 36)]), PARAMS) == direct


@respx.mock
def test_fx_fetches_once_a_day_and_falls_back_to_stored(engine) -> None:
    route = respx.get(FRANKFURTER_URL).respond(json=FX)
    with session_scope(engine) as s, httpx.Client() as http:
        r = get_rate(s, http, "JPY")
        assert r is not None
        assert (r.rate, r.date) == (8.4587, date(2026, 11, 4))
        get_rate(s, http, "JPY")
        assert route.call_count == 1
        row = s.scalar(select(FxRate))
        assert row is not None
        row.fetched_at = datetime.now(UTC) - timedelta(days=2)
    route.respond(404)  # not retried, so the test stays fast
    with session_scope(engine) as s, httpx.Client() as http:
        r = get_rate(s, http, "JPY")
        assert r is not None and r.rate == 8.4587
        k = get_rate(s, None, "KRW")
        assert k is not None and k.rate == 1.0


def _mock_area_lookups() -> None:
    """Every configured query resolves to its own fake ID placed 1 km apart along a line."""
    city = load_city(CITIES, "tokyo")
    queries = [a.query for a in city.stay_areas] + [a.query for a in city.airports]
    queries += [x.hub_query for a in city.airports for x in a.express]

    def search(request: httpx.Request) -> httpx.Response:
        q = json.loads(request.content)["textQuery"]
        return httpx.Response(200, json={"places": [{"id": f"area{queries.index(q)}"}]})

    respx.post(f"{BASE_URL}/places:searchText").mock(side_effect=search)
    for i in range(len(queries)):
        lat = 35.60 + i * 0.009 if i < len(city.stay_areas) else 35.40 + (i - len(city.stay_areas)) * 0.1
        respx.get(f"{BASE_URL}/places/area{i}").respond(
            json={"id": f"area{i}", "types": ["train_station"], "location": {"latitude": lat, "longitude": 139.70}}
        )


@respx.mock
def test_score_endpoint_ranks_areas_and_stays(api: ApiHarness) -> None:
    trip = api.create_trip()
    respx.get(FRANKFURTER_URL).respond(json=FX)
    _mock_area_lookups()
    pin_id = "ChIJpin"
    respx.get(f"{BASE_URL}/places/{pin_id}").respond(
        json=places_fixture("details_essentials") | {"id": pin_id, "location": {"latitude": 35.6, "longitude": 139.70}}
    )
    pin = api.client.post(
        f"/api/trips/{trip['id']}/pins", json={"google_place_id": pin_id, "label": "꼭", "source": "search"}
    ).json()
    api.client.patch(f"/api/trips/{trip['id']}/pins/{pin['id']}", json={"priority": "must"})
    maybe = api.client.post(f"/api/trips/{trip['id']}/pins", json={"label": "미연결", "source": "url"}).json()
    assert maybe["resolve_status"] == "pending"

    stay = api.client.post(
        f"/api/trips/{trip['id']}/stays",
        json={
            "label": "에어비앤비",
            "user_lat": 35.601,
            "user_lng": 139.70,
            "check_in": "2030-12-28",
            "check_out": "2031-01-01",
            "total_amount": 120000,
            "currency": "JPY",
            "booking_url": "https://www.airbnb.com/rooms/1",
        },
    )
    assert stay.status_code == 201, stay.text
    body = stay.json()
    assert (body["nights"], body["nightly_amount"], body["nightly_krw"]) == (4, 30000, round(30000 * 8.4587))
    assert body["location_source"] == "user"

    out = api.client.get(f"/api/trips/{trip['id']}/stays/score").json()
    assert out["targets"] == 1
    assert out["weights"] == {"must": 100, "want": 10}
    assert out["airport_notes"] == {"NRT": "스카이라이너 (닛포리에서 최단 36분)"}
    assert [(f["base"], f["date"]) for f in out["fx"]] == [("JPY", "2026-11-04")]
    first = out["origins"][0]
    assert first["rank"] == 1
    assert first["kind"] in ("area", "stay")
    labels = [o["label"] for o in out["origins"]]
    assert labels.index("신주쿠") < labels.index("이케부쿠로")  # areas spaced north of the pin
    assert set(first["airport_min"]) == {"HND", "NRT"}
    stay_row = next(o for o in out["origins"] if o["kind"] == "stay")
    assert stay_row["nightly_krw"] == round(30000 * 8.4587)
    # Second call reuses stored place IDs and cached coordinates.
    calls = respx.calls.call_count
    api.client.get(f"/api/trips/{trip['id']}/stays/score")
    assert respx.calls.call_count == calls


def test_stay_validation_and_crud(api: ApiHarness) -> None:
    trip = api.create_trip()
    url = f"/api/trips/{trip['id']}/stays"
    assert api.client.post(url, json={"label": "위치 없음"}).status_code == 422
    bad_dates = {
        "label": "x",
        "user_lat": 35.6,
        "user_lng": 139.7,
        "check_in": "2030-12-28",
        "check_out": "2030-12-28",
    }
    assert api.client.post(url, json=bad_dates).status_code == 422
    s = api.client.post(
        url, json={"label": "후보", "user_lat": 35.6, "user_lng": 139.7, "currency": "KRW", "total_amount": 500000}
    ).json()
    assert s["nightly_amount"] is None
    patched = api.client.patch(
        f"{url}/{s['id']}", json={"status": "booked", "check_in": "2030-12-28", "check_out": "2030-12-30"}
    ).json()
    assert (patched["status"], patched["nights"], patched["nightly_krw"]) == ("booked", 2, 250000)
    assert api.client.delete(f"{url}/{s['id']}").status_code == 204
    assert api.client.get(url).json() == []
