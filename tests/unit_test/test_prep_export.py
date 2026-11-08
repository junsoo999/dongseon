import csv
import io
import zipfile
from datetime import UTC, date, datetime

import respx

from dongseon.core.checklist import load_checklist
from dongseon.db.models import FlightLeg, FlightOption, TripPin
from dongseon.db.session import get_engine, session_scope
from dongseon.export.ics import _fold
from dongseon.export.plan import Stop, day_route_urls

from .conftest import ApiHarness
from .test_plan_review import _setup

GOOGLE_TIMES = "10:00~18:00"  # the museum's Google hours in the fixtures; must never leave the app


def test_checklist_seed_add_check_delete(api: ApiHarness) -> None:
    tid = api.create_trip()["id"]
    template = load_checklist(api.settings.checklist_file)
    n = sum(len(s.items) for s in template.sections)
    assert api.client.get(f"/api/trips/{tid}/checklist").json()["items"] == []
    seeded = api.client.post(f"/api/trips/{tid}/checklist/seed").json()["items"]
    assert len(seeded) == n and [i["sort"] for i in seeded] == sorted(i["sort"] for i in seeded)
    assert any(i["url"] for i in seeded)  # facts that change link to the official page
    assert len(api.client.post(f"/api/trips/{tid}/checklist/seed").json()["items"]) == n  # no duplicates

    mine = api.client.post(f"/api/trips/{tid}/checklist", json={"text": "  우산  "}).json()
    assert (mine["text"], mine["section"], mine["sort"]) == ("우산", "기타", n + 1)
    done = api.client.patch(f"/api/checklist/{mine['id']}", json={"done": True}).json()
    assert done["done"] is True
    assert api.client.delete(f"/api/checklist/{seeded[0]['id']}").status_code == 204
    items = api.client.get(f"/api/trips/{tid}/checklist").json()["items"]
    assert len(items) == n and items[-1]["done"] is True
    assert api.client.patch("/api/checklist/9999", json={"done": True}).status_code == 404


@respx.mock
def test_bookings_collect_booked_flights_stays_and_reservations(api: ApiHarness) -> None:
    tid, pins, _v1 = _setup(api)
    with session_scope(get_engine(api.db)) as s:
        opt = FlightOption(
            trip_id=tid,
            label="항공",
            total_amount=500000,
            currency="KRW",
            status="booked",
            created_at=datetime.now(UTC),
        )
        opt.legs = [
            FlightLeg(
                direction="out",
                seq=1,
                carrier="KE",
                flight_no="KE001",
                dep_airport="ICN",
                dep_at=datetime(2030, 12, 28, 0, 0, tzinfo=UTC),
                arr_airport="NRT",
                arr_at=datetime(2030, 12, 28, 2, 20, tzinfo=UTC),
            )
        ]
        s.add(opt)
        s.add(FlightOption(trip_id=tid, label="후보", currency="KRW", created_at=datetime.now(UTC)))
        pin = s.get(TripPin, pins["sushi"])
        assert pin is not None
        pin.reserved_start = datetime(2030, 12, 29, 10, 0, tzinfo=UTC)  # 19:00 in Tokyo
    out = api.client.get(f"/api/trips/{tid}/bookings").json()
    assert [f["label"] for f in out["flights"]] == ["항공"]
    leg = out["flights"][0]["legs"][0]
    assert (leg["dep_local"], leg["arr_local"]) == ("2030-12-28T09:00", "2030-12-28T11:20")
    assert [s["label"] for s in out["stays"]] == ["숙소"]
    assert [(r["label"], r["start_local"]) for r in out["reservations"]] == [("스시", "2030-12-29T19:00")]


@respx.mock
def test_exports_carry_the_plan_but_no_google_content(api: ApiHarness) -> None:
    tid, pins, v1 = _setup(api)
    api.client.patch(f"/api/trips/{tid}/pins/{pins['museum']}", json={"local_name": "テスト博物館"})
    visits = [i for d in v1["days"] for i in d["items"] if i["kind"] in ("visit", "meal")]
    museum = next(i for i in visits if i["pin_id"] == pins["museum"])
    assert museum["hours"].startswith(GOOGLE_TIMES)  # the screen shows Google hours ...

    ics = api.client.get(f"/api/itineraries/{v1['id']}/export.ics")
    assert ics.headers["content-type"].startswith("text/calendar")
    assert "attachment" in ics.headers["content-disposition"]
    body = ics.text
    assert body.count("BEGIN:VEVENT") == len(visits) and "\r\n" in body
    assert "SUMMARY:박물관" in body and "テスト博物館" in body
    assert all(len(line.encode()) <= 75 for line in body.split("\r\n"))
    assert GOOGLE_TIMES not in body  # ... the files do not

    html = api.client.get(f"/api/itineraries/{v1['id']}/print").text
    assert "박물관" in html and "1일차" in html and "google.com/maps/dir" in html and GOOGLE_TIMES not in html

    z = zipfile.ZipFile(io.BytesIO(api.client.get(f"/api/itineraries/{v1['id']}/mymaps.zip").content))
    csvs = sorted(n for n in z.namelist() if n.endswith(".csv"))
    assert csvs and csvs[0].startswith("day1_") and "README.txt" in z.namelist()
    rows = [r for n in csvs for r in csv.DictReader(io.StringIO(z.read(n).decode()))]
    assert len(rows) == len(visits)
    m = next(r for r in rows if r["이름"] == "박물관")
    assert m["현지 이름"] == "テスト博物館"
    assert m["위치"] == ", ".join(x for x in ("テスト博物館", m["동네"], "Tokyo") if x)
    assert not any(str(museum["lat"])[:6] in z.read(n).decode() for n in csvs)  # no coordinates

    off = api.client.get(f"/api/trips/{tid}/offline").json()
    assert off["itinerary_id"] == v1["id"] and off["trip"]["timezone"] == "Asia/Tokyo"
    assert sum(len(d["stops"]) for d in off["days"]) == len(visits)
    assert off["bookings"]["stays"][0]["label"] == "숙소"
    flat = str(off)
    assert GOOGLE_TIMES not in flat and "'lat'" not in flat and "'hours'" not in flat


@respx.mock
def test_offline_bundle_without_a_plan(api: ApiHarness) -> None:
    tid = api.create_trip()["id"]
    off = api.client.get(f"/api/trips/{tid}/offline").json()
    assert (off["itinerary_id"], off["days"], off["checklist"]) == (None, [], [])
    assert api.client.get("/api/itineraries/9999/export.ics").status_code == 404


def _stop(i: int, gid: str | None = "g") -> Stop:
    at = datetime(2030, 12, 28, 9, tzinfo=UTC)
    return Stop(i, date(2030, 12, 28), i, at, at, f"s{i}", None, None, None, gid and f"{gid}{i}", [])


def test_day_route_urls_split_into_legs_of_five() -> None:
    assert day_route_urls([]) == []
    one = day_route_urls([_stop(1)])
    assert len(one) == 1 and "origin" not in one[0] and "destination_place_id=g1" in one[0]
    urls = day_route_urls([_stop(i) for i in range(1, 8)])  # 1-5, then 5-7
    assert len(urls) == 2
    assert "origin=s1" in urls[0] and "destination=s5" in urls[0] and "waypoints=s2%7Cs3%7Cs4" in urls[0]
    assert "origin=s5" in urls[1] and "destination=s7" in urls[1]
    assert "waypoint_place_ids" not in day_route_urls([_stop(1), _stop(2, None), _stop(3)])[0]


def test_ics_folding_keeps_utf8_characters_whole() -> None:
    line = "SUMMARY:" + "가" * 40
    folded = _fold(line).split("\r\n ")
    assert len(folded) > 1 and "".join(folded) == line
    assert all(len(x.encode()) <= 75 for x in folded)
