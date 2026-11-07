import json

import respx
from sqlalchemy import select

from dongseon.api.deps import get_llm
from dongseon.core.cities import load_city
from dongseon.core.profile import load_profile
from dongseon.db.models import HoursOverride, Trip
from dongseon.db.session import get_engine, session_scope
from dongseon.llm.area_notes import run_area_notes
from dongseon.llm.booking import mask
from dongseon.llm.claude_cli import ClaudeCli
from dongseon.llm.hours_research import run_hours_research
from dongseon.main import app
from dongseon.planner.hours import HOURS_CACHE
from dongseon.sources.fx import FRANKFURTER_URL

from .conftest import CITIES, EXAMPLE_PROFILE, ApiHarness
from .test_itinerary import MARKET, MUSEUM, _mock_places, _pin
from .test_stays import FX, _mock_area_lookups

URL = "https://example.com/holiday-hours"


def _llm(api: ApiHarness, answer: dict, seen: list[tuple[list[str], str]]) -> ClaudeCli:
    def runner(argv: list[str], stdin: str, timeout: int) -> str:
        seen.append((argv, stdin))
        return json.dumps({"structured_output": answer, "usage": {"input_tokens": 10, "output_tokens": 5}})

    return ClaudeCli(get_engine(api.db), model="", daily_token_limit=10_000, runner=runner)


def test_mask_hides_personal_details_and_keeps_booking_facts() -> None:
    text = "\n".join(
        [
            "예약번호 ABC123 / 편명 KE703 2030-12-28 10:30 ICN → NRT",
            "결제 카드 4111 1111 1111 1111, 금액 512,000원",
            "여권번호: M12345678",
            "생년월일: 1990-01-02",
            "Date of birth 02 JAN 1990",
            "연락처 010-1234-5678 / guest@example.com",
            "Passport no. X1234567 expires 2031-05-01",
        ]
    )
    m = mask(text)
    for gone in ("4111", "M12345678", "1990-01-02", "02 JAN 1990", "010-1234-5678", "guest@example.com", "X1234567"):
        assert gone not in m.text, gone
    for kept in ("ABC123", "KE703", "2030-12-28 10:30", "512,000원", "ICN → NRT"):
        assert kept in m.text, kept
    assert m.counts["카드번호"] == 1 and m.counts["생년월일"] == 2 and m.counts["여권번호"] == 2
    assert "카드번호" not in mask("주문 1234 5678 9012 3456").counts  # fails the Luhn check


@respx.mock
def test_hours_research_stores_cited_holiday_dates_and_the_solver_uses_them(api: ApiHarness) -> None:
    HOURS_CACHE._rows.clear()
    trip = api.create_trip()  # 2030-12-28 ~ 2031-01-01; holidays from 12-29
    respx.get(FRANKFURTER_URL).respond(json=FX)
    _mock_area_lookups()
    _mock_places()
    tid = trip["id"]
    museum = _pin(api, tid, MUSEUM, "박물관", priority="must", dwell_min=120)
    _pin(api, tid, MARKET, "시장", priority="maybe", dwell_min=60)
    answer = {
        "items": [
            {
                "pin_id": museum["id"],
                "place_name": "Fake Museum",
                "days": [
                    {"date": "2030-12-28", "status": "closed", "source_url": URL, "confidence": "high"},
                    {"date": "2030-12-29", "status": "unknown"},
                    {"date": "2030-12-30", "status": "closed", "source_url": URL, "confidence": "low"},
                    {"date": "2030-12-31", "status": "closed", "source_url": URL, "confidence": "high"},
                    {
                        "date": "2031-01-01",
                        "status": "open",
                        "open": "10:00",
                        "close": "16:00",
                        "source_url": URL,
                        "confidence": "medium",
                    },
                ],
                "sources": [{"title": "공식", "url": URL}],
            },
            {"pin_id": 999, "place_name": "x", "days": [], "sources": [{"title": "x", "url": URL}]},
            {"pin_id": museum["id"], "place_name": "출처 없음", "days": [], "sources": []},
        ]
    }
    seen: list[tuple[list[str], str]] = []
    with session_scope(get_engine(api.db)) as s:
        t = s.get(Trip, tid)
        assert t is not None
        r = run_hours_research(s, _llm(api, answer, seen), t, load_city(CITIES, "tokyo"))
    assert (r.pins, r.stored) == (1, 2)  # maybe pins skipped; non-holiday, unknown and low-confidence dates dropped
    argv, stdin = seen[0]
    assert "WebSearch,WebFetch" in argv and '"label": "박물관"' in stdin
    assert '"2030-12-28"' not in stdin and "ChIJ" not in stdin

    out = api.client.get(f"/api/trips/{tid}/hours-research").json()
    assert out["dates"][0] == "2030-12-29" and out["holiday_note"]
    [place] = out["places"]
    assert [(d["date"], d["status"], d["open"], d["close"]) for d in place["days"]] == [
        ("2030-12-31", "closed", None, None),
        ("2031-01-01", "open", "10:00", "16:00"),
    ]

    it = api.client.post(f"/api/trips/{tid}/itineraries/solve").json()
    day_of = {i["pin_id"]: (d["date"], i) for d in it["days"] for i in d["items"]}
    d, item = day_of[museum["id"]]
    assert d not in ("2030-12-30", "2030-12-31")  # Monday (Google) and the researched closure
    if d == "2031-01-01":
        assert item["hours"] == "10:00~16:00 · AI 조사" and item["hours_url"] == URL
        assert "AI 조사 기준 영업시간" in item["warnings"]

    # A user entry still wins over AI research.
    api.client.put(
        f"/api/trips/{tid}/pins/{museum['id']}/hours/2030-12-31",
        json={"status": "open", "open": "09:00", "close": "17:00"},
    )
    with session_scope(get_engine(api.db)) as s:
        assert s.scalar(select(HoursOverride).where(HoursOverride.source == "user")) is not None


@respx.mock
def test_area_notes_keep_known_areas_with_sources(api: ApiHarness) -> None:
    trip = api.create_trip()
    note = {
        "summary": "역 주변이 붐빕니다",
        "pros": ["교통"],
        "cons": ["밤에 시끄러움"],
        "sources": [{"title": "가이드", "url": URL}],
    }
    answer = {
        "items": [
            {"area": "신주쿠", **note},
            {"area": "긴자", **note, "summary": "조용합니다"},
            {"area": "오사카", **note},
            {"area": "우에노", **note, "sources": []},
        ]
    }
    seen: list[tuple[list[str], str]] = []
    llm = _llm(api, answer, seen)
    with session_scope(get_engine(api.db)) as s:
        t = s.get(Trip, trip["id"])
        assert t is not None
        args = (s, llm, t, load_city(CITIES, "tokyo"), load_profile(EXAMPLE_PROFILE))
        assert run_area_notes(*args).stored == 2
        assert run_area_notes(*args).skipped is True
        assert run_area_notes(*args, force=True).stored == 2
    assert '"name_en": "Shinjuku"' in seen[0][1]
    notes = api.client.get(f"/api/trips/{trip['id']}/area-notes").json()
    assert sorted(n["area"] for n in notes) == ["긴자", "신주쿠"]
    assert next(n for n in notes if n["area"] == "긴자")["summary"] == "조용합니다"


def test_parse_booking_masks_text_and_returns_a_draft(api: ApiHarness) -> None:
    trip = api.create_trip()
    seen: list[tuple[list[str], str]] = []
    answer = {
        "kind": "flight",
        "flight": {
            "label": "대한항공",
            "total_amount": 512000,
            "currency": "KRW",
            "baggage_note": "23kg 1개",
            "legs": [
                {
                    "direction": "out",
                    "carrier": "대한항공",
                    "flight_no": "KE703",
                    "dep_airport": "ICN",
                    "dep_local": "2030-12-28T09:00",
                    "arr_airport": "NRT",
                    "arr_local": "2030-12-28T11:30",
                }
            ],
        },
        "note": "오는 편이 없습니다",
    }
    app.dependency_overrides[get_llm] = lambda: _llm(api, answer, seen)
    text = "대한항공 예약 확인\nKE703 2030-12-28 09:00 ICN-NRT\n카드 4111-1111-1111-1111\n생년월일 1990.01.02"
    resp = api.client.post(f"/api/trips/{trip['id']}/parse-booking", json={"text": text})
    assert resp.status_code == 200, resp.text
    out = resp.json()
    assert out["kind"] == "flight" and out["flight"]["legs"][0]["flight_no"] == "KE703"
    assert out["masked"] == {"카드번호": 1, "생년월일": 1}
    argv, stdin = seen[0]
    assert argv[argv.index("--tools") + 1] == ""
    assert "4111" not in stdin and "1990.01.02" not in stdin and "KE703" in stdin

    app.dependency_overrides[get_llm] = lambda: _llm(api, {"kind": "stay", "stay": None}, seen)
    assert api.client.post(f"/api/trips/{trip['id']}/parse-booking", json={"text": text}).json()["kind"] == "none"
    app.dependency_overrides[get_llm] = lambda: _llm(api, {"kind": "flight", "flight": {"legs": []}}, seen)
    assert api.client.post(f"/api/trips/{trip['id']}/parse-booking", json={"text": text}).status_code == 502
    assert api.client.post(f"/api/trips/{trip['id']}/parse-booking", json={"text": "짧음"}).status_code == 422
