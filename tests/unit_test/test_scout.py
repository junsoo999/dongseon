import json
import re
from datetime import date

import httpx
import respx
from sqlalchemy import select

from dongseon.core.cities import load_city
from dongseon.core.profile import load_profile
from dongseon.db.models import AiSuggestion, LlmRun, Stay, Trip, TripPin
from dongseon.db.session import get_engine, session_scope
from dongseon.links import flight_links, stay_links
from dongseon.llm.claude_cli import ClaudeCli
from dongseon.llm.payloads import places_research_payload
from dongseon.llm.research import input_hash, normalize_name
from dongseon.scout import scout_trip
from dongseon.sources.fx import FRANKFURTER_URL
from dongseon.sources.google_places import BASE_URL, GooglePlacesClient

from .conftest import CITIES, EXAMPLE_PROFILE, ApiHarness
from .test_stays import FX, _mock_area_lookups

SOURCE = [{"title": "가이드", "url": "https://example.com/guide"}]
PLACES = {
    "items": [
        {
            "name": "스시 가짜",
            "name_local": "鮨偽",
            "area": "긴자",
            "category": "food",
            "meal": "dinner",
            "why": "스시를 좋아하는 일행에게",
            "reservation": "required",
            "price_range": "¥20,000~",
            "sources": SOURCE,
        },
        {"name": "출처 없음", "area": "긴자", "category": "food", "why": "x", "sources": []},
        {
            "name": "Fake Tower",
            "name_local": None,
            "area": "아사쿠사",
            "category": "sight",
            "why": "전망",
            "sources": SOURCE,
        },
        {"name": "먼 곳", "area": "오사카", "category": "sight", "why": "x", "sources": SOURCE},
    ]
}
STAYS = {
    "items": [
        {
            "name": "가짜 호텔 긴자",
            "area": "긴자",
            "type": "hotel",
            "has_bathtub": True,
            "nightly_low": 25000,
            "nightly_high": 40000,
            "currency": "JPY",
            "why": "욕조가 있는 방",
            "sources": SOURCE,
        },
    ]
}


def _runner(argv: list[str], stdin: str, timeout: int) -> str:
    assert "--tools" in argv and "WebSearch,WebFetch" in argv
    data = PLACES if "places_research" in json.dumps(argv) or '"want"' in stdin else STAYS
    return json.dumps({"structured_output": data, "usage": {"input_tokens": 10, "output_tokens": 5}})


def _mock_matches() -> None:
    def search(request: httpx.Request) -> httpx.Response:
        q = json.loads(request.content)["textQuery"]
        pid = {
            "鮨偽 긴자": "sushi",
            "Fake Tower 아사쿠사 도쿄": "tower",
            "먼 곳 오사카 도쿄": "far",
            "가짜 호텔 긴자 긴자 도쿄": "hotel",
        }.get(q)
        return httpx.Response(200, json={"places": [{"id": pid}]} if pid else {})

    respx.post(f"{BASE_URL}/places:searchText").mock(side_effect=search)
    for pid, lat in (("sushi", 35.67), ("tower", 35.71), ("far", 34.69), ("hotel", 35.671)):
        respx.get(f"{BASE_URL}/places/{pid}").respond(
            json={"id": pid, "types": ["restaurant"], "location": {"latitude": lat, "longitude": 139.77}}
        )


def test_normalize_and_hash_ignore_noise() -> None:
    assert normalize_name(" 스시 가짜! ") == normalize_name("스시가짜")
    trip = Trip(
        title="t",
        city_key="tokyo",
        timezone="Asia/Tokyo",
        pace="normal",
        start_date=date(2030, 12, 28),
        end_date=date(2031, 1, 1),
    )
    city = load_city(CITIES, "tokyo")
    prof = load_profile(EXAMPLE_PROFILE)
    a = places_research_payload(trip, city, prof, existing_labels=[], rejected=[], areas=["긴자"], want={"food": 1})
    b = {**a, "today": "1999-01-01"}
    assert input_hash("v1", a) == input_hash("v1", b)
    assert input_hash("v1", a) != input_hash("v2", a)
    assert set(a) >= {"food_likes", "existing", "rejected", "areas", "want"}


@respx.mock
def test_scout_stores_validated_matched_suggestions_and_accept_flow(api: ApiHarness) -> None:
    trip = api.create_trip()
    respx.get(FRANKFURTER_URL).respond(json=FX)
    _mock_area_lookups()
    _mock_matches()
    eng = get_engine(api.db)
    llm = ClaudeCli(eng, model="", daily_token_limit=10_000, runner=_runner)
    with session_scope(eng) as s, httpx.Client() as http:
        t = s.get(Trip, trip["id"])
        assert t is not None
        client = GooglePlacesClient(http, "k", lambda _sku: None)
        summary = scout_trip(
            s,
            trip=t,
            city=load_city(CITIES, "tokyo"),
            profile=load_profile(EXAMPLE_PROFILE),
            settings=api.settings,
            llm=llm,
            client=client,
            http=http,
        )
    place_r, stay_r = summary.results
    assert (place_r.proposed, place_r.stored, place_r.unmatched) == (
        3,
        3,
        1,
    )  # source-less item dropped, far = unmatched
    assert (stay_r.stored, stay_r.unmatched) == (1, 0)
    with session_scope(eng) as s:
        assert s.scalar(select(LlmRun.ok)) is True
        far = s.scalar(select(AiSuggestion).where(AiSuggestion.key == normalize_name("먼 곳")))
        assert far is not None and far.google_place_id is None

    # The same input within 7 days is skipped.
    with session_scope(eng) as s, httpx.Client() as http:
        t = s.get(Trip, trip["id"])
        assert t is not None
        again = scout_trip(
            s,
            trip=t,
            city=load_city(CITIES, "tokyo"),
            profile=load_profile(EXAMPLE_PROFILE),
            settings=api.settings,
            llm=llm,
            client=GooglePlacesClient(http, "k", lambda _sku: None),
            http=http,
        )
    assert all(r.skipped for r in again.results)

    places = api.client.get(f"/api/trips/{trip['id']}/suggestions", params={"kind": "place"}).json()
    sushi = next(p for p in places if p["place"]["name"] == "스시 가짜")
    assert sushi["lat"] == 35.67
    assert api.client.post(f"/api/suggestions/{sushi['id']}/accept").json()["pin_id"]
    assert api.client.post(f"/api/suggestions/{sushi['id']}/accept").status_code == 409
    tower = next(p for p in places if p["place"]["name"] == "Fake Tower")
    assert api.client.post(f"/api/suggestions/{tower['id']}/reject").status_code == 204
    with session_scope(eng) as s:
        pin = s.scalar(select(TripPin).where(TripPin.trip_id == trip["id"]))
        assert pin is not None
        assert pin.place.local_name == "鮨偽"  # kept for the My Maps export
        assert (pin.priority, pin.added_by, pin.meal, pin.place.label, pin.place.category) == (
            "maybe",
            "ai",
            "dinner",
            "스시 가짜",
            "food",
        )
    assert len(api.client.get(f"/api/trips/{trip['id']}/suggestions", params={"kind": "place"}).json()) == 1

    stay = api.client.get(f"/api/trips/{trip['id']}/suggestions", params={"kind": "stay"}).json()[0]
    assert stay["stay"]["has_bathtub"] is True
    stay_id = api.client.post(f"/api/suggestions/{stay['id']}/accept").json()["stay_id"]
    with session_scope(eng) as s:
        st = s.get(Stay, stay_id)
        assert st is not None
        assert st.note and "1박 25,000~40,000 JPY" in st.note and st.note.startswith("AI 제안")


def test_search_links(api: ApiHarness) -> None:
    trip = api.create_trip()
    api.settings.google_maps_server_key = ""
    out = api.client.get(f"/api/trips/{trip['id']}/search-links").json()
    assert {f["site"] for f in out["flights"]} == {"google_flights", "naver"}
    naver = next(f for f in out["flights"] if f["site"] == "naver")["url"]
    assert "ICN-TYO-20301228/TYO-ICN-20310101" in naver and "adult=2" in naver
    ginza = next(a for a in out["stays"] if a["area"] == "긴자")
    airbnb = next(lk for lk in ginza["links"] if lk["site"] == "airbnb")["url"]
    assert "Ginza--Tokyo" in airbnb and "checkin=2030-12-28" in airbnb


def test_link_builders() -> None:
    g = flight_links("ICN", "TYO", date(2030, 12, 28), date(2031, 1, 1), 2)[0].url
    assert "q=Flights+from+ICN+to+TYO+on+2030-12-28+through+2031-01-01" in g
    b = stay_links("Ginza", "Tokyo", date(2030, 12, 28), date(2031, 1, 1), 2)[1].url
    assert "ss=Ginza%2C+Tokyo" in b and "group_adults=2" in b


def test_research_schemas_resolve_every_reference() -> None:
    from dongseon.llm.research import PLACES_SCHEMA, STAYS_SCHEMA

    for schema in (PLACES_SCHEMA, STAYS_SCHEMA):
        refs = set(re.findall(r'"\$ref": "#/\$defs/(\w+)"', json.dumps(schema)))
        assert refs <= set(schema.get("$defs", {})), refs
