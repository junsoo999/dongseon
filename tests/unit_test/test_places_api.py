from datetime import UTC, datetime, timedelta

import respx
from sqlalchemy import select

from dongseon.api.routes import jobs
from dongseon.core.lock import job_lock
from dongseon.db.models import ApiUsage, GeoCache, Place
from dongseon.db.session import get_engine, session_scope
from dongseon.sources.google_places import BASE_URL

from .conftest import ApiHarness, places_fixture

PID = "ChIJY4HWjseLGGARIBjdW6fAwYs"


def _mock_details(pid: str = PID, lat: float = 35.6000001, lng: float = 139.7000001, types: list | None = None):
    data = places_fixture("details_essentials") | {"id": pid, "location": {"latitude": lat, "longitude": lng}}
    if types is not None:
        data["types"] = types
    return respx.get(f"{BASE_URL}/places/{pid}").respond(json=data)


def test_trip_crud_and_cities(api: ApiHarness) -> None:
    assert [c["key"] for c in api.client.get("/api/cities").json()] == ["tokyo"]
    trip = api.create_trip()
    assert trip["timezone"] == "Asia/Tokyo"
    assert trip["city_name"] == "도쿄"
    assert api.client.post("/api/trips", json={**trip, "city_key": "atlantis"}).status_code == 422
    bad = {"title": "x", "city_key": "tokyo", "start_date": "2030-12-28", "end_date": "2030-12-01"}
    assert api.client.post("/api/trips", json=bad).status_code == 422
    resp = api.client.patch(f"/api/trips/{trip['id']}", json={"pace": "relaxed"})
    assert resp.json()["pace"] == "relaxed"
    assert len(api.client.get("/api/trips").json()) == 1
    assert api.client.get("/api/trips/999").status_code == 404


@respx.mock
def test_add_search_pin_sets_category_dwell_and_coords(api: ApiHarness) -> None:
    trip = api.create_trip()
    details = _mock_details(types=["restaurant", "food"])
    body = {
        "google_place_id": PID,
        "label": "  초밥집 ",
        "source": "search",
        "source_ref": "초밥",
        "session_token": "tok-12345678",
    }
    resp = api.client.post(f"/api/trips/{trip['id']}/pins", json=body)
    assert resp.status_code == 201, resp.text
    pin = resp.json()
    assert pin["label"] == "초밥집"
    assert pin["category"] == "food"
    assert pin["dwell_min"] == 75
    assert (pin["lat"], pin["lng"]) == (35.6000001, 139.7000001)
    assert details.calls.last.request.url.params["sessionToken"] == "tok-12345678"
    assert api.client.post(f"/api/trips/{trip['id']}/pins", json=body).status_code == 409
    with session_scope(get_engine(api.db)) as s:
        assert s.scalar(select(ApiUsage.count).where(ApiUsage.sku == "places_details_essentials")) == 1
        geo = s.get(GeoCache, PID)
        assert geo is not None
        assert geo.expires_at - geo.fetched_at == timedelta(days=30)


@respx.mock
def test_same_place_in_second_trip_reuses_place_without_google_call(api: ApiHarness) -> None:
    t1, t2 = api.create_trip(), api.create_trip(title="두 번째")
    details = _mock_details()
    body = {"google_place_id": PID, "label": "시장", "source": "search"}
    api.client.post(f"/api/trips/{t1['id']}/pins", json=body)
    api.client.post(f"/api/trips/{t2['id']}/pins", json=body)
    assert details.call_count == 1


@respx.mock
def test_expired_coordinates_are_deleted_and_refetched(api: ApiHarness) -> None:
    trip = api.create_trip()
    details = _mock_details()
    api.client.post(
        f"/api/trips/{trip['id']}/pins", json={"google_place_id": PID, "label": "시장", "source": "search"}
    )
    with session_scope(get_engine(api.db)) as s:
        row = s.get(GeoCache, PID)
        assert row is not None
        row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    pins = api.client.get(f"/api/trips/{trip['id']}/pins").json()
    assert pins[0]["lat"] == 35.6000001
    assert details.call_count == 2


def test_pending_pin_without_google_id_and_patch(api: ApiHarness) -> None:
    trip = api.create_trip()
    resp = api.client.post(
        f"/api/trips/{trip['id']}/pins",
        json={"label": "어딘가", "source": "url", "source_ref": "https://maps.app.goo.gl/x"},
    )
    pin = resp.json()
    assert pin["resolve_status"] == "pending"
    assert pin["category"] == "other"
    assert pin["lat"] is None
    url = f"/api/trips/{trip['id']}/pins/{pin['id']}"
    patched = api.client.patch(
        url, json={"priority": "must", "dwell_min": 30, "meal": "lunch", "label": "점심", "category": "food"}
    ).json()
    assert (patched["priority"], patched["dwell_min"], patched["meal"], patched["label"], patched["category"]) == (
        "must",
        30,
        "lunch",
        "점심",
        "food",
    )
    assert api.client.patch(url, json={"clear_meal": True}).json()["meal"] is None
    assert api.client.patch(url, json={"category": "nope"}).status_code == 422
    assert api.client.patch(url, json={"dwell_min": 1}).status_code == 422
    assert api.client.delete(url).status_code == 204
    assert api.client.get(f"/api/trips/{trip['id']}/pins").json() == []


@respx.mock
def test_manual_match_of_pending_place(api: ApiHarness) -> None:
    trip = api.create_trip()
    pin = api.client.post(f"/api/trips/{trip['id']}/pins", json={"label": "어딘가", "source": "url"}).json()
    _mock_details()
    resp = api.client.patch(f"/api/trips/{trip['id']}/pins/{pin['id']}", json={"google_place_id": PID})
    assert resp.json()["resolve_status"] == "ok"
    assert resp.json()["lat"] == 35.6000001


@respx.mock
def test_autocomplete_endpoint(api: ApiHarness) -> None:
    trip = api.create_trip()
    respx.post(f"{BASE_URL}/places:autocomplete").respond(json=places_fixture("autocomplete"))
    out = api.client.get(
        "/api/places/autocomplete", params={"trip_id": trip["id"], "q": "가짜", "session_token": "tok-12345678"}
    )
    assert out.status_code == 200
    assert out.json()[0] == {"google_place_id": PID, "main_text": "가짜 장소 1", "secondary_text": "가짜구 가짜동 1"}


@respx.mock
def test_resolve_url_matches_name_near_coordinates(api: ApiHarness) -> None:
    trip = api.create_trip()
    respx.post(f"{BASE_URL}/places:searchText").respond(json={"places": [{"id": "far"}, {"id": PID}]})
    _mock_details("far", lat=35.7, lng=139.8)  # ~14 km away: rejected
    _mock_details(PID, lat=35.6000001, lng=139.7000001)
    url = "https://www.google.com/maps/place/Fake+Market/@35.6,139.7,17z"
    out = api.client.post("/api/places/resolve-url", json={"trip_id": trip["id"], "url": url}).json()
    assert out == {"google_place_id": PID, "label_hint": "Fake Market", "reason": None}


def test_resolve_url_rejects_non_google(api: ApiHarness) -> None:
    trip = api.create_trip()
    out = api.client.post(
        "/api/places/resolve-url", json={"trip_id": trip["id"], "url": "https://example.com/x"}
    ).json()
    assert out["google_place_id"] is None
    assert out["reason"] == "Google 지도 링크가 아닙니다"


def test_missing_key_gives_503_for_google_calls_but_lists_still_work(api: ApiHarness) -> None:
    trip = api.create_trip()
    api.settings.google_maps_server_key = ""
    q = {"trip_id": trip["id"], "q": "ab", "session_token": "tok-12345678"}
    assert api.client.get("/api/places/autocomplete", params=q).status_code == 503
    assert api.client.get(f"/api/trips/{trip['id']}/pins").status_code == 200


@respx.mock
def test_free_tier_stop_returns_429_without_calling_google(api: ApiHarness) -> None:
    trip = api.create_trip()
    route = respx.post(f"{BASE_URL}/places:autocomplete").respond(json={})
    api.settings.google_free_tier_stop_ratio = 0.0
    q = {"trip_id": trip["id"], "q": "ab", "session_token": "tok-12345678"}
    resp = api.client.get("/api/places/autocomplete", params=q)
    assert resp.status_code == 429
    assert "무료 한도" in resp.json()["detail"]
    assert not route.called


@respx.mock
def test_rejected_key_returns_502(api: ApiHarness) -> None:
    trip = api.create_trip()
    respx.post(f"{BASE_URL}/places:autocomplete").respond(400, json=places_fixture("bad_key"))
    q = {"trip_id": trip["id"], "q": "ab", "session_token": "tok-12345678"}
    assert api.client.get("/api/places/autocomplete", params=q).status_code == 502


def test_categories_endpoint(api: ApiHarness) -> None:
    cats = {c["key"]: c["dwell_min"] for c in api.client.get("/api/categories").json()}
    assert cats["museum"] == 120


def test_jobs_start_and_lock(api: ApiHarness, monkeypatch) -> None:
    started: list[list[str]] = []
    monkeypatch.setattr(jobs, "spawn_cli", started.append)
    resp = api.client.post("/api/jobs/places-resolve")
    assert resp.status_code == 202
    assert started == [["places", "resolve"]]
    with job_lock(api.settings.lock_path, "places-resolve"):
        assert api.client.post("/api/jobs/places-resolve").status_code == 409
        assert api.client.get("/api/jobs/places-resolve").json()["running"] is True
    assert api.client.post("/api/jobs/unknown").status_code == 422


@respx.mock
def test_resolve_pending_job(api: ApiHarness) -> None:
    import httpx

    from dongseon.core.defaults import load_defaults
    from dongseon.places.service import resolve_pending
    from dongseon.sources.google_places import GooglePlacesClient

    trip = api.create_trip()
    api.client.post(
        f"/api/trips/{trip['id']}/pins",
        json={
            "label": "시장",
            "source": "url",
            "source_ref": "https://www.google.com/maps/place/Fake/@35.6,139.7,17z",
        },
    )
    api.client.post(
        f"/api/trips/{trip['id']}/pins",
        json={"label": "없는곳", "source": "url", "source_ref": "https://example.com/x"},
    )
    respx.post(f"{BASE_URL}/places:searchText").respond(json={"places": [{"id": PID}]})
    _mock_details(types=["museum"])
    cats = load_defaults(api.settings.defaults_file).categories
    with session_scope(get_engine(api.db)) as s, httpx.Client() as http:
        summary = resolve_pending(s, http, GooglePlacesClient(http, "k", lambda _sku: None), cats, region_code="JP")
    assert (summary.resolved, summary.failed) == (1, 1)
    with session_scope(get_engine(api.db)) as s:
        places = {p.label: p for p in s.scalars(select(Place))}
        assert places["시장"].google_place_id == PID
        assert places["시장"].category == "museum"
        assert places["없는곳"].resolve_status == "failed"
