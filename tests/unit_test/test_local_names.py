import json

import httpx
import respx

from dongseon.core.cities import load_city
from dongseon.db.models import Trip
from dongseon.db.session import get_engine, session_scope
from dongseon.llm.local_names import run_local_names
from dongseon.sources.google_places import BASE_URL, GooglePlacesClient

from .conftest import CITIES, ApiHarness
from .test_ai_research import _llm
from .test_itinerary import MARKET, MUSEUM, SUSHI, _mock_places, _pin

SRC = [{"title": "공식", "url": "https://example.com/official"}]


def _mock_search(found: dict[str, str]) -> list[str]:
    queries: list[str] = []

    def search(request: httpx.Request) -> httpx.Response:
        q = json.loads(request.content)["textQuery"]
        queries.append(q)
        pid = found.get(q)
        return httpx.Response(200, json={"places": [{"id": "ChIJother"}, {"id": pid}]} if pid else {})

    respx.post(f"{BASE_URL}/places:searchText").mock(side_effect=search)
    return queries


def _run(api: ApiHarness, tid: int, answer: dict, seen: list, *, force: bool = False):
    with session_scope(get_engine(api.db)) as s, httpx.Client() as http:
        t = s.get(Trip, tid)
        assert t is not None
        client = GooglePlacesClient(http, "k", lambda _sku: None)
        return run_local_names(s, _llm(api, answer, seen), client, t, load_city(CITIES, "tokyo"), force=force)


@respx.mock
def test_local_names_are_researched_verified_and_applied(api: ApiHarness) -> None:
    _mock_places()
    tid = api.create_trip()["id"]
    museum = _pin(api, tid, MUSEUM, "박물관", note="우에노 쪽")
    market = _pin(api, tid, MARKET, "시장")
    sushi = _pin(api, tid, SUSHI, "스시", local_name="鮨偽")  # typed by the user: not researched
    queries = _mock_search({"テスト博物館": MUSEUM})
    answer = {
        "items": [
            {"pin_id": museum["id"], "name_local": " テスト博物館 ", "sources": SRC, "confidence": "high"},
            {"pin_id": market["id"], "name_local": "テスト市場", "sources": SRC},
            {"pin_id": sushi["id"], "name_local": "別の鮨", "sources": SRC},  # not asked for
            {"pin_id": market["id"], "name_local": "あやしい", "sources": SRC, "confidence": "low"},
            {"pin_id": museum["id"], "name_local": "出典なし", "sources": []},
        ]
    }
    seen: list = []
    r = _run(api, tid, answer, seen)
    assert (r.pins, r.stored, r.verified) == (2, 2, 1)
    argv, stdin = seen[0]
    assert "WebSearch,WebFetch" in argv and '"label": "박물관"' in stdin and "우에노 쪽" in stdin
    assert "ChIJ" not in stdin and "鮨偽" not in stdin and "35.7" not in stdin  # no Google content
    assert queries == ["テスト博物館", "テスト市場"]

    out = api.client.get(f"/api/trips/{tid}/local-names").json()
    assert (out["total"], out["filled"]) == (3, 1)
    assert [(x["label"], x["name_local"], x["verified"]) for x in out["suggestions"]] == [
        ("박물관", "テスト博物館", True),
        ("시장", "テスト市場", False),
    ]
    assert api.client.post(f"/api/trips/{tid}/local-names/accept-verified").json() == {"applied": 1}
    pins = {p["id"]: p for p in api.client.get(f"/api/trips/{tid}/pins").json()}
    assert pins[museum["id"]]["local_name"] == "テスト博物館" and pins[market["id"]]["local_name"] is None

    # Rejected names are sent back and not stored again.
    [unverified] = api.client.get(f"/api/trips/{tid}/local-names").json()["suggestions"]
    assert api.client.post(f"/api/local-names/{unverified['id']}/reject").status_code == 204
    assert api.client.post(f"/api/local-names/{unverified['id']}/accept").status_code == 409
    seen = []
    again = _run(api, tid, {"items": [{"pin_id": market["id"], "name_local": "テスト市場", "sources": SRC}]}, seen)
    assert (again.pins, again.stored) == (1, 0) and "テスト市場" in seen[0][1]

    # A name accepted one by one fills the pin; the same input is not researched again within a week.
    seen = []
    third = _run(api, tid, {"items": [{"pin_id": market["id"], "name_local": "築地テスト", "sources": SRC}]}, seen)
    assert third.stored == 1
    [s] = api.client.get(f"/api/trips/{tid}/local-names").json()["suggestions"]
    assert api.client.post(f"/api/local-names/{s['id']}/accept").status_code == 204
    out = api.client.get(f"/api/trips/{tid}/local-names").json()
    assert (out["filled"], out["suggestions"]) == (3, [])
    assert _run(api, tid, {"items": []}, []).pins == 0


def test_local_name_actions_need_a_pending_local_name_suggestion(api: ApiHarness) -> None:
    assert api.client.post("/api/local-names/9999/accept").status_code == 404
    assert api.client.post("/api/local-names/9999/reject").status_code == 404
    assert api.client.post("/api/trips/9999/local-names/accept-verified").status_code == 404
