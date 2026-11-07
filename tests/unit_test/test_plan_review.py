import json
from datetime import date

import httpx
import respx
from sqlalchemy import select

from dongseon.api.routes import jobs
from dongseon.core.cities import load_city
from dongseon.core.profile import load_profile
from dongseon.db.models import AiSuggestion, Itinerary, Trip
from dongseon.db.session import get_engine, session_scope
from dongseon.llm.claude_cli import ClaudeCli
from dongseon.llm.payloads import plan_review_payload
from dongseon.llm.plan_review import run_review
from dongseon.planner.build import edit_of, prepare
from dongseon.planner.hours import HOURS_CACHE
from dongseon.planner.suggest import EditNotApplicableError, PlanEdit, apply_edit
from dongseon.sources.fx import FRANKFURTER_URL
from dongseon.sources.google_places import GooglePlacesClient

from .conftest import CITIES, EXAMPLE_PROFILE, ApiHarness
from .test_itinerary import MARKET, MUSEUM, SUSHI, _mock_places, _pin
from .test_stays import FX, _mock_area_lookups

MONDAY = "2030-12-30"  # the fixture museum is closed on Mondays


def _setup(api: ApiHarness) -> tuple[int, dict[str, int], dict]:
    HOURS_CACHE._rows.clear()
    trip = api.create_trip()
    respx.get(FRANKFURTER_URL).respond(json=FX)
    _mock_area_lookups()
    _mock_places()
    tid = trip["id"]
    pins = {
        "museum": _pin(api, tid, MUSEUM, "박물관", priority="must", dwell_min=120)["id"],
        "market": _pin(api, tid, MARKET, "시장", priority="must", dwell_min=60)["id"],
        "sushi": _pin(api, tid, SUSHI, "스시", priority="want", meal="dinner", dwell_min=90)["id"],
    }
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
    v1 = api.client.post(f"/api/trips/{tid}/itineraries/solve").json()
    return tid, pins, v1


def _answer(pins: dict[str, int]) -> dict:
    return {
        "day_titles": [{"date": "2030-12-28", "title": "도착과 시장"}, {"date": "2099-01-01", "title": "x"}],
        "notes": ["연말에는 붐빕니다"],
        "edits": [
            {"op": "move", "pin_id": pins["museum"], "date": MONDAY, "after_pin_id": None, "reason": "월요일로"},
            {"op": "drop", "pin_id": pins["sushi"], "reason": "저녁을 가볍게"},
            {"op": "set_dwell", "pin_id": pins["market"], "dwell_min": 90, "reason": "시장은 오래 걸립니다"},
            {"op": "move", "pin_id": 9999, "date": MONDAY, "reason": "없는 장소"},
            {"op": "teleport", "pin_id": pins["market"], "reason": "잘못된 형식"},
        ],
    }


def _llm(api: ApiHarness, answer: dict, seen: list[str]) -> ClaudeCli:
    def runner(argv: list[str], stdin: str, timeout: int) -> str:
        assert argv[argv.index("--tools") + 1] == ""  # no tools for plan review
        seen.append(stdin)
        return json.dumps({"structured_output": answer, "usage": {"input_tokens": 10, "output_tokens": 5}})

    return ClaudeCli(get_engine(api.db), model="", daily_token_limit=10_000, runner=runner)


def _run(api: ApiHarness, tid: int, llm: ClaudeCli, **kw: object):
    with session_scope(get_engine(api.db)) as s, httpx.Client() as http:
        trip = s.get(Trip, tid)
        assert trip is not None
        it = s.scalar(select(Itinerary).where(Itinerary.trip_id == tid, Itinerary.status == "active"))
        assert it is not None
        profile = load_profile(EXAMPLE_PROFILE)
        ctx = prepare(
            s,
            trip=trip,
            city=load_city(CITIES, "tokyo"),
            profile=profile,
            settings=api.settings,
            http=http,
            client=GooglePlacesClient(http, "k", lambda _sku: None),
        )
        return run_review(s, llm, ctx, it, profile, indoor={"food", "museum"}, **kw)  # type: ignore[arg-type]


@respx.mock
def test_review_checks_edits_and_accept_makes_a_version(api: ApiHarness) -> None:
    tid, pins, v1 = _setup(api)
    seen: list[str] = []
    llm = _llm(api, _answer(pins), seen)
    result = _run(api, tid, llm)
    assert (result.skipped, result.proposed, result.stored) == (False, 4, 3)  # bad op dropped, unknown pin skipped
    # The payload carries app data only: no opening-hours labels or coordinates.
    sent = seen[0]
    assert "Google" not in sent and "35.6" not in sent and '"pin_id"' in sent

    listed = api.client.get(f"/api/trips/{tid}/plan-suggestions").json()
    assert listed["reviews"][0]["day_titles"] == [{"date": "2030-12-28", "title": "도착과 시장"}]
    assert listed["reviews"][0]["notes"] == ["연말에는 붐빕니다"]
    by_op = {e["op"]: e for e in listed["edits"]}
    assert by_op["move"]["applicable"] is False
    assert any("휴무" in p for p in by_op["move"]["problems"])
    assert by_op["move"]["title"].startswith("박물관 → 3일차(12/30)")
    assert by_op["drop"]["applicable"] is True and by_op["drop"]["title"] == "스시 빼기"
    assert by_op["set_dwell"]["applicable"] is True

    # The same input is not sent again while its suggestions are pending.
    assert _run(api, tid, llm).skipped is True

    # Suggestions for place/stay scouting stay separate.
    assert api.client.get(f"/api/trips/{tid}/suggestions").json() == []
    assert api.client.post(f"/api/suggestions/{by_op['drop']['id']}/accept").status_code == 404

    preview = api.client.get(f"/api/plan-suggestions/{by_op['drop']['id']}/preview").json()
    assert preview["applicable"] is True
    planned = {i["pin_id"] for d in preview["itinerary"]["days"] for i in d["items"]}
    assert pins["sushi"] not in planned and preview["itinerary"]["id"] == 0
    assert api.client.get(f"/api/trips/{tid}/itineraries").json()[0]["version"] == 1  # nothing saved

    resp = api.client.post(f"/api/plan-suggestions/{by_op['move']['id']}/accept")
    assert resp.status_code == 409 and "휴무" in resp.json()["detail"]

    resp = api.client.post(f"/api/plan-suggestions/{by_op['drop']['id']}/accept")
    assert resp.status_code == 201, resp.text
    v2 = resp.json()
    assert (v2["version"], v2["origin"]) == (2, "ai")
    sushi = next(x for x in v2["dropped"] if x["pin_id"] == pins["sushi"])
    assert sushi["excluded"] is True

    # Checked again against the new version: set_dwell still applies and updates the pin.
    resp = api.client.post(f"/api/plan-suggestions/{by_op['set_dwell']['id']}/accept")
    assert resp.status_code == 201, resp.text
    market = next(p for p in api.client.get(f"/api/trips/{tid}/pins").json() if p["id"] == pins["market"])
    assert market["dwell_min"] == 90
    item = next(i for d in resp.json()["days"] for i in d["items"] if i["pin_id"] == pins["market"])
    h0, m0 = map(int, item["start"].split(":"))
    h1, m1 = map(int, item["end"].split(":"))
    assert (h1 * 60 + m1) - (h0 * 60 + m0) == 90

    assert api.client.post(f"/api/plan-suggestions/{by_op['move']['id']}/reject").status_code == 204
    assert api.client.post(f"/api/plan-suggestions/{by_op['move']['id']}/reject").status_code == 409
    assert v1["version"] == 1


@respx.mock
def test_rain_plan_keeps_only_edits_for_that_day_and_expires_older(api: ApiHarness) -> None:
    tid, pins, v1 = _setup(api)
    seen: list[str] = []
    first = _run(api, tid, _llm(api, _answer(pins), seen))
    assert first.stored == 3
    layout = {d["date"]: [i["pin_id"] for i in d["items"]] for d in v1["days"]}
    rainy = next(d for d, p in layout.items() if pins["market"] in p)
    other_day = next(d for d in layout if d != rainy)
    answer = {
        "day_titles": [{"date": rainy, "title": "비 오는 날"}, {"date": other_day, "title": "다른 날"}],
        "notes": [],
        "edits": [
            {"op": "move", "pin_id": pins["market"], "date": other_day, "reason": "실외 시장은 다른 날로"},
            {"op": "set_dwell", "pin_id": 0, "dwell_min": 30, "reason": "x"},
        ],
    }
    if pins["museum"] not in layout[rainy]:
        answer["edits"].append({"op": "set_dwell", "pin_id": pins["museum"], "dwell_min": 60, "reason": "그날과 무관"})
    result = _run(api, tid, _llm(api, answer, seen), rain_date=date.fromisoformat(rainy))
    assert result.stored == 1
    assert f'"rain_date": "{rainy}"' in seen[-1] and "indoor_candidates" in seen[-1]
    listed = api.client.get(f"/api/trips/{tid}/plan-suggestions").json()
    rain = [e for e in listed["edits"] if e["source"] == "rain"]
    assert len(rain) == 1 and rain[0]["date"] == rainy
    titles = next(r for r in listed["reviews"] if r["source"] == "rain")["day_titles"]
    assert [t["date"] for t in titles] == [rainy]
    # The whole-trip review is untouched by a rain plan; a new review expires the old one.
    assert any(e["source"] == "review" for e in listed["edits"])
    _run(api, tid, _llm(api, _answer(pins), seen), force=True)
    with session_scope(get_engine(api.db)) as s:
        statuses = [r.status for r in s.scalars(select(AiSuggestion).where(AiSuggestion.kind == "plan_review"))]
    assert sorted(statuses) == ["expired", "pending", "pending"]


@respx.mock
def test_start_review_spawns_the_job(api: ApiHarness, monkeypatch) -> None:
    tid, _pins, v1 = _setup(api)
    started: list[list[str]] = []
    monkeypatch.setattr(jobs, "spawn_cli", started.append)
    resp = api.client.post(f"/api/itineraries/{v1['id']}/review", json={"rain_date": "2030-12-29"})
    assert resp.status_code == 202 and resp.json()["running"] is True
    assert started == [["review", "--itinerary", str(v1["id"]), "--rain", "2030-12-29"]]
    resp = api.client.post(f"/api/itineraries/{v1['id']}/review", json={"rain_date": "2031-02-01"})
    assert resp.status_code == 422
    v2 = api.client.post(f"/api/trips/{tid}/itineraries/solve").json()
    assert api.client.post(f"/api/itineraries/{v1['id']}/review", json={}).status_code == 409
    assert api.client.post(f"/api/itineraries/{v2['id']}/review", json={}).status_code == 202


def test_apply_edit_rules() -> None:
    from dongseon.planner.build import Edit

    d1, d2 = date(2030, 12, 28), date(2030, 12, 29)
    base = Edit(layout={d1: [1, 2], d2: [3]}, excluded=frozenset({4}))
    known = {1, 2, 3, 4}
    moved = apply_edit(base, PlanEdit(op="move", pin_id=2, date=d2, after_pin_id=3, reason="r"), known)
    assert moved.edit.layout == {d1: [1], d2: [3, 2]} and 2 in moved.edit.locked
    assert moved.days == {d1, d2}
    swapped = apply_edit(base, PlanEdit(op="swap", pin_id=1, other_pin_id=3, reason="r"), known)
    assert swapped.edit.layout == {d1: [3, 2], d2: [1]}
    added = apply_edit(base, PlanEdit(op="add_from_pool", pin_id=4, date=d1, reason="r"), known)
    assert added.edit.layout[d1] == [4, 1, 2] and 4 not in added.edit.excluded
    dropped = apply_edit(base, PlanEdit(op="drop", pin_id=3, reason="r"), known)
    assert dropped.edit.layout[d2] == [] and 3 in dropped.edit.excluded
    for bad in (
        PlanEdit(op="move", pin_id=4, date=d1, reason="r"),  # not planned
        PlanEdit(op="add_from_pool", pin_id=1, date=d2, reason="r"),  # already planned
        PlanEdit(op="move", pin_id=1, date=date(2031, 5, 1), reason="r"),  # outside the trip
        PlanEdit(op="move", pin_id=1, date=d2, after_pin_id=2, reason="r"),  # anchor on another date
        PlanEdit(op="swap", pin_id=1, other_pin_id=None, reason="r"),
        PlanEdit(op="move", pin_id=99, date=d1, reason="r"),
    ):
        try:
            apply_edit(base, bad, known)
        except EditNotApplicableError:
            continue
        raise AssertionError(f"accepted {bad}")


@respx.mock
def test_payload_has_no_google_content(api: ApiHarness) -> None:
    tid, _pins, _v1 = _setup(api)
    with session_scope(get_engine(api.db)) as s, httpx.Client() as http:
        trip = s.get(Trip, tid)
        assert trip is not None
        it = s.scalar(select(Itinerary).where(Itinerary.trip_id == tid, Itinerary.status == "active"))
        assert it is not None
        profile = load_profile(EXAMPLE_PROFILE)
        ctx = prepare(
            s,
            trip=trip,
            city=load_city(CITIES, "tokyo"),
            profile=profile,
            settings=api.settings,
            http=http,
            client=GooglePlacesClient(http, "k", lambda _sku: None),
        )
        payload = plan_review_payload(trip, ctx.city, profile, itinerary=it, pins=ctx.pins, indoor=set(), rejected=[])
        assert edit_of(it).layout  # sanity
    text = json.dumps(payload, ensure_ascii=False)
    for banned in ("hours", "lat", "lng", "place_id", "move_min", "ChIJ"):
        assert f'"{banned}"' not in text and "ChIJ" not in text
    assert payload["days"][0]["items"] is not None and payload["holidays"]
