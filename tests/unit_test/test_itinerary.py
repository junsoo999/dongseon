from datetime import date

import httpx
import respx

from dongseon.planner.hours import HOURS_CACHE
from dongseon.sources.fx import FRANKFURTER_URL
from dongseon.sources.google_places import BASE_URL

from .conftest import ApiHarness, places_fixture
from .test_stays import FX, _mock_area_lookups

MUSEUM, MARKET, SUSHI = "ChIJmuseum", "ChIJmarket", "ChIJsushi"


def _mock_places() -> None:
    coords = {MUSEUM: (35.718, 139.776), MARKET: (35.665, 139.770), SUSHI: (35.671, 139.765)}
    hours = {MUSEUM: places_fixture("details_hours"), MARKET: places_fixture("details_hours_missing")}

    def details(request: httpx.Request) -> httpx.Response:
        pid = request.url.path.rsplit("/", 1)[-1]
        mask = request.headers.get("X-Goog-FieldMask", "")
        if "regularOpeningHours" in mask:
            return httpx.Response(200, json=hours.get(pid, {"id": pid}))
        lat, lng = coords[pid]
        return httpx.Response(
            200, json={"id": pid, "types": ["restaurant"], "location": {"latitude": lat, "longitude": lng}}
        )

    for pid in coords:
        respx.get(f"{BASE_URL}/places/{pid}").mock(side_effect=details)


def _pin(api: ApiHarness, trip_id: int, pid: str, label: str, **patch: object) -> dict:
    pin = api.client.post(
        f"/api/trips/{trip_id}/pins", json={"google_place_id": pid, "label": label, "source": "search"}
    ).json()
    return api.client.patch(f"/api/trips/{trip_id}/pins/{pin['id']}", json=patch).json()


@respx.mock
def test_solve_respects_hours_meals_and_flight(api: ApiHarness) -> None:
    HOURS_CACHE._rows.clear()
    trip = api.create_trip()  # 2030-12-28 (Sat) ~ 2031-01-01 (Wed)
    respx.get(FRANKFURTER_URL).respond(json=FX)
    _mock_area_lookups()
    _mock_places()
    tid = trip["id"]
    museum = _pin(api, tid, MUSEUM, "박물관", priority="must", dwell_min=120)
    _pin(api, tid, MARKET, "시장", priority="must", dwell_min=60)
    sushi = _pin(api, tid, SUSHI, "스시", priority="want", meal="dinner", dwell_min=90)
    api.client.post(
        f"/api/trips/{tid}/stays",
        json={
            "label": "숙소",
            "user_lat": 35.68,
            "user_lng": 139.77,
            "check_in": "2030-12-28",
            "check_out": "2031-01-01",
            "status": "booked",
        },
    )

    def leg(d, a, dl, b, al):
        return {
            "direction": d,
            "dep_airport": a,
            "dep_local": dl,
            "arr_airport": b,
            "arr_local": al,
        }

    api.client.post(
        f"/api/trips/{tid}/flights",
        json={
            "label": "확정",
            "status": "booked",
            "legs": [
                leg("out", "ICN", "2030-12-28T08:00", "HND", "2030-12-28T10:30"),
                leg("back", "HND", "2031-01-01T18:00", "ICN", "2031-01-01T20:30"),
            ],
        },
    )
    resp = api.client.post(f"/api/trips/{tid}/itineraries/solve")
    assert resp.status_code == 201, resp.text
    it = resp.json()
    assert it["version"] == 1 and it["approx"] is True and len(it["days"]) == 5
    first, last = it["days"][0], it["days"][-1]
    assert first["start"] > "09:00"  # arrival + immigration + airport access
    assert last["end"] < "18:00"  # leave for the airport before the flight
    assert first["depot"] == "숙소"
    visits = {i["pin_id"]: (d["date"], i) for d in it["days"] for i in d["items"]}
    assert museum["id"] in visits and sushi["id"] in visits
    m_day, m_item = visits[museum["id"]]
    assert date.fromisoformat(m_day).weekday() != 0  # closed on Mondays
    assert m_item["start"] >= "10:00" and m_item["end"] <= "18:00"
    _s_day, s_item = visits[sushi["id"]]
    assert s_item["start"] >= "18:00" and s_item["end"] <= "20:30" and s_item["kind"] == "meal"
    market_item = next(i for d in it["days"] for i in d["items"] if i["label"] == "시장")
    assert market_item["hours"] == "영업시간 정보 없음"
    assert "연휴 기간 영업 미확인" in market_item["warnings"]
    assert any("연휴" in w for d in it["days"] for w in d["warnings"])  # 12-29 ~ 01-04 year-end period
    assert m_item["hours"].endswith("Google")

    again = api.client.post(f"/api/trips/{tid}/itineraries/solve").json()
    versions = api.client.get(f"/api/trips/{tid}/itineraries").json()
    assert [v["version"] for v in versions] == [2, 1] and versions[1]["status"] == "archived"
    assert api.client.get(f"/api/trips/{tid}/itineraries/active").json()["id"] == again["id"]


def test_active_is_null_before_first_draft(api: ApiHarness) -> None:
    trip = api.create_trip()
    assert api.client.get(f"/api/trips/{trip['id']}/itineraries/active").json() is None


def _layout(it: dict) -> dict[str, list[int]]:
    return {d["date"]: [i["pin_id"] for i in d["items"]] for d in it["days"]}


@respx.mock
def test_edit_lock_resolve_restore_and_user_hours(api: ApiHarness) -> None:
    HOURS_CACHE._rows.clear()
    trip = api.create_trip()  # 2030-12-28 (Sat) ~ 2031-01-01 (Wed); 12-30 is a Monday
    respx.get(FRANKFURTER_URL).respond(json=FX)
    _mock_area_lookups()
    _mock_places()
    tid = trip["id"]
    museum = _pin(api, tid, MUSEUM, "박물관", priority="must", dwell_min=120)
    market = _pin(api, tid, MARKET, "시장", priority="must", dwell_min=60)
    v1 = api.client.post(f"/api/trips/{tid}/itineraries/solve").json()

    # Put the museum alone on Monday (closed), locked, and take the market out.
    days = [{"date": d, "pin_ids": []} for d in _layout(v1)]
    days[2]["pin_ids"] = [museum["id"]]
    resp = api.client.post(
        f"/api/itineraries/{v1['id']}/edit",
        json={"days": days, "locked": [museum["id"]], "excluded": [market["id"]]},
    )
    assert resp.status_code == 201, resp.text
    v2 = resp.json()
    assert v2["origin"] == "user" and v2["version"] == 2
    monday = v2["days"][2]
    assert [i["pin_id"] for i in monday["items"]] == [museum["id"]]
    item = monday["items"][0]
    assert item["locked"] and "이 날은 휴무입니다" in item["warnings"]
    out = next(x for x in v2["dropped"] if x["pin_id"] == market["id"])
    assert out["excluded"] and out["reason"] == "직접 뺐습니다"

    # Editing an archived version is refused.
    stale = api.client.post(f"/api/itineraries/{v1['id']}/edit", json={"days": days})
    assert stale.status_code == 409

    # Re-solve keeps the locked museum on Monday and the market out.
    v3 = api.client.post(f"/api/itineraries/{v2['id']}/resolve").json()
    assert v3["origin"] == "solver"
    assert museum["id"] in _layout(v3)[days[2]["date"]]
    assert all(market["id"] not in pins for pins in _layout(v3).values())

    # User hours win over Google: the museum is open on that Monday after all.
    resp = api.client.put(
        f"/api/trips/{tid}/pins/{museum['id']}/hours/{days[2]['date']}",
        json={"status": "open", "open": "09:30", "close": "17:00"},
    )
    assert resp.status_code == 200 and resp.json()["open_min"] == 570
    v4 = api.client.post(f"/api/itineraries/{v3['id']}/edit", json={"days": days, "locked": [museum["id"]]}).json()
    item = v4["days"][2]["items"][0]
    assert item["hours"] == "09:30~17:00 · 직접 입력" and item["hours_source"] == "user"
    assert "이 날은 휴무입니다" not in item["warnings"] and item["start"] >= "09:30"
    assert api.client.delete(f"/api/trips/{tid}/pins/{museum['id']}/hours/{days[2]['date']}").status_code == 204

    # Restoring v1 gives a new version with v1's layout.
    v5 = api.client.post(f"/api/itineraries/{v1['id']}/restore").json()
    assert v5["version"] == 5 and v5["status"] == "active" and _layout(v5) == _layout(v1)
    assert api.client.get(f"/api/trips/{tid}/itineraries/active").json()["id"] == v5["id"]


def test_edit_rejects_unknown_dates_and_duplicates(api: ApiHarness) -> None:
    trip = api.create_trip()
    tid = trip["id"]
    with respx.mock:
        respx.get(FRANKFURTER_URL).respond(json=FX)
        _mock_area_lookups()
        _mock_places()
        museum = _pin(api, tid, MUSEUM, "박물관", priority="want")
        v1 = api.client.post(f"/api/trips/{tid}/itineraries/solve").json()
        bad_date = api.client.post(
            f"/api/itineraries/{v1['id']}/edit", json={"days": [{"date": "2030-01-01", "pin_ids": []}]}
        )
        assert bad_date.status_code == 422
        dup = api.client.post(
            f"/api/itineraries/{v1['id']}/edit",
            json={"days": [{"date": "2030-12-28", "pin_ids": [museum["id"], museum["id"]]}]},
        )
        assert dup.status_code == 422
