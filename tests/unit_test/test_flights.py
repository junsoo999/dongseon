from datetime import UTC, datetime

import respx

from dongseon.api.routes.flights import _to_utc
from dongseon.core.airports import AirportInfo, load_airports
from dongseon.core.profile import Buffers
from dongseon.flights.evaluate import LegTimes, check_legs, evaluate
from dongseon.sources.fx import FRANKFURTER_URL
from dongseon.sources.google_places import BASE_URL

from .conftest import REPO_ROOT, ApiHarness
from .test_stays import FX, _mock_area_lookups


def _utc(*args: int) -> datetime:
    return datetime(*args, tzinfo=UTC)


OUT = LegTimes("out", "ICN", _utc(2030, 12, 28, 0, 0), "NRT", _utc(2030, 12, 28, 2, 20))
BACK = LegTimes("back", "HND", _utc(2031, 1, 1, 9, 0), "GMP", _utc(2031, 1, 1, 11, 10))
BUFFERS = Buffers(departure_airport=120, arrival_immigration=60, transfer=10)


def test_usable_time_subtracts_buffers_and_airport_access() -> None:
    ev = evaluate([OUT, BACK], BUFFERS, {"NRT": 60, "HND": 45})
    assert ev is not None
    assert ev.ready_at == _utc(2030, 12, 28, 4, 20)  # 02:20 + 60 immigration + 60 access
    assert ev.leave_by == _utc(2031, 1, 1, 6, 15)  # 09:00 - 120 buffer - 45 access
    assert ev.usable_min == 4 * 24 * 60 + 115
    assert ev.warnings == []


def test_missing_access_or_direction() -> None:
    ev = evaluate([OUT, BACK], BUFFERS, {"HND": 45})
    assert ev is not None
    assert ev.usable_min is None
    assert any("NRT" in w for w in ev.warnings)
    assert evaluate([OUT], BUFFERS, {}) is None


def test_leg_checks() -> None:
    assert check_legs([OUT, BACK]) == []
    bad = LegTimes("out", "NRT", _utc(2030, 12, 28, 3, 0), "ICN", _utc(2030, 12, 28, 2, 0))
    assert any("도착이 출발보다" in p for p in check_legs([bad]))
    connect = LegTimes("out", "KIX", _utc(2030, 12, 28, 3, 0), "HND", _utc(2030, 12, 28, 4, 0))
    assert any("NRT에 도착한 뒤 KIX" in p for p in check_legs([OUT, connect]))
    early_back = LegTimes("back", "NRT", _utc(2030, 12, 28, 1, 0), "ICN", _utc(2030, 12, 28, 3, 0))
    assert any("귀국편 출발이" in p for p in check_legs([OUT, early_back]))


def test_local_times_convert_per_airport_timezone() -> None:
    hnl = AirportInfo(code="HNL", name="호놀룰루", timezone="Pacific/Honolulu")
    icn = AirportInfo(code="ICN", name="인천", timezone="Asia/Seoul")
    local = datetime(2030, 12, 28, 9, 0)  # noqa: DTZ001 - typed as airport-local wall time
    assert _to_utc(local, hnl) == _utc(2030, 12, 28, 19, 0)
    assert _to_utc(local, icn) == _utc(2030, 12, 28, 0, 0)


def test_airport_config_parses() -> None:
    airports = load_airports(REPO_ROOT / "config" / "airports.yaml")
    assert {"ICN", "GMP", "HND", "NRT"} <= set(airports)
    assert airports["NRT"].timezone == "Asia/Tokyo"


def _leg(direction: str, dep: str, dep_local: str, arr: str, arr_local: str) -> dict:
    return {
        "direction": direction,
        "carrier": "KE",
        "flight_no": "KE1",
        "dep_airport": dep,
        "dep_local": dep_local,
        "arr_airport": arr,
        "arr_local": arr_local,
    }


@respx.mock
def test_flight_api_evaluates_against_top_area(api: ApiHarness) -> None:
    trip = api.create_trip()
    respx.get(FRANKFURTER_URL).respond(json=FX)
    _mock_area_lookups()
    pin_id = "ChIJpin"
    respx.get(f"{BASE_URL}/places/{pin_id}").respond(
        json={"id": pin_id, "types": ["museum"], "location": {"latitude": 35.6, "longitude": 139.7}}
    )
    pin = api.client.post(
        f"/api/trips/{trip['id']}/pins", json={"google_place_id": pin_id, "label": "꼭", "source": "search"}
    ).json()
    api.client.patch(f"/api/trips/{trip['id']}/pins/{pin['id']}", json={"priority": "must"})
    body = {
        "label": "대한항공 아침",
        "total_amount": 700000,
        "currency": "KRW",
        "baggage_note": "23kg 1개",
        "legs": [
            _leg("out", "ICN", "2030-12-28T09:00", "NRT", "2030-12-28T11:20"),
            _leg("back", "HND", "2031-01-01T18:00", "GMP", "2031-01-01T20:10"),
        ],
    }
    resp = api.client.post(f"/api/trips/{trip['id']}/flights", json=body)
    assert resp.status_code == 201, resp.text
    f = resp.json()
    assert f["legs"][0]["dep_local"] == "2030-12-28T09:00"
    assert f["legs"][0]["duration_min"] == 140
    assert f["problems"] == []
    ev = f["evaluation"]
    assert ev["arrival_local"] == "2030-12-28T11:20"
    assert ev["reference_kind"] == "top_area"
    assert ev["access_in_min"] > 0 and ev["access_out_min"] > 0
    assert ev["usable_min"] > 0
    assert ev["total_krw"] == 700000
    assert ev["krw_per_usable_hour"] == round(700000 / (ev["usable_min"] / 60))

    second = api.client.post(
        f"/api/trips/{trip['id']}/flights", json={**body, "label": "확정", "status": "booked"}
    ).json()
    replaced = api.client.put(
        f"/api/trips/{trip['id']}/flights/{f['id']}", json={**body, "label": "바꿈", "status": "booked"}
    ).json()
    assert replaced["label"] == "바꿈"
    listed = {x["id"]: x["status"] for x in api.client.get(f"/api/trips/{trip['id']}/flights").json()}
    assert listed == {f["id"]: "booked", second["id"]: "candidate"}  # only one booked option
    assert api.client.delete(f"/api/trips/{trip['id']}/flights/{second['id']}").status_code == 204


def test_flight_api_rejects_unknown_airport(api: ApiHarness) -> None:
    trip = api.create_trip()
    body = {"label": "x", "legs": [_leg("out", "XXX", "2030-12-28T09:00", "NRT", "2030-12-28T11:20")]}
    resp = api.client.post(f"/api/trips/{trip['id']}/flights", json=body)
    assert resp.status_code == 422
    assert "XXX" in resp.json()["detail"]
    assert {a["code"] for a in api.client.get("/api/airports").json()} >= {"ICN", "NRT"}


def test_flight_without_pins_has_no_reference(api: ApiHarness) -> None:
    trip = api.create_trip()
    api.settings.google_maps_server_key = ""
    body = {
        "label": "x",
        "legs": [
            _leg("out", "ICN", "2030-12-28T09:00", "NRT", "2030-12-28T11:20"),
            _leg("back", "HND", "2031-01-01T18:00", "GMP", "2031-01-01T20:10"),
        ],
    }
    ev = api.client.post(f"/api/trips/{trip['id']}/flights", json=body).json()["evaluation"]
    assert ev["reference_kind"] == "none"
    assert ev["usable_min"] is None
