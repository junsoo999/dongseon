"""Build and store an itinerary: gather the trip's pins, stays, flights and opening hours, solve, and validate.

Travel times are the straight-line approximation ("근사"); Google opening hours are fetched for must/want pins and
kept in process memory only.
"""

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from dongseon.api.routes.flights import _reference
from dongseon.api.routes.stays import build_score
from dongseon.core.cities import CityConfig
from dongseon.core.config import Settings
from dongseon.core.profile import Profile, TimeWindow
from dongseon.db.models import FlightOption, HoursOverride, Itinerary, ItineraryItem, Stay, Trip, TripPin
from dongseon.flights.evaluate import LegTimes, evaluate
from dongseon.matrix.approx import approx_leg
from dongseon.places.service import coords_for
from dongseon.planner.hours import HOURS_CACHE, DayHours, GoogleHours, OverrideRow, hours_on
from dongseon.planner.solver import DAY_MIN, Day, Stop, solve
from dongseon.sources.google_places import GooglePlacesClient, LatLng, PlaceNotFoundError, PlacesError

PENALTY_SCALE = 10_000
HOURS_FOR = ("must", "want")  # Enterprise lookups only where they matter


@dataclass(frozen=True)
class DayPlanInfo:
    """Per-day facts stored with the itinerary (for the timeline and warnings)."""

    day: date
    start_min: int
    end_min: int
    depot_label: str
    warnings: list[str]


def _minutes(t: time) -> int:
    return t.hour * 60 + t.minute


def _window_minutes(w: TimeWindow) -> tuple[int, int]:
    return _minutes(w.start), _minutes(w.end)


def _local_minutes(at: datetime, tz: ZoneInfo, day: date) -> int:
    local = at.astimezone(tz)
    return (local.date() - day).days * DAY_MIN + local.hour * 60 + local.minute


def _intersect(windows: list[tuple[int, int]], other: tuple[int, int]) -> list[tuple[int, int]]:
    out = []
    for a, b in windows:
        lo, hi = max(a, other[0]), min(b, other[1])
        if hi > lo:
            out.append((lo, hi))
    return out


def _stay_point(stay: Stay, coords: dict[str, LatLng]) -> LatLng | None:
    if stay.user_lat is not None and stay.user_lng is not None:
        return LatLng(stay.user_lat, stay.user_lng)
    gid = stay.place.google_place_id if stay.place else None
    return coords.get(gid) if gid else None


def hours_label(h: DayHours) -> str:
    """Short Korean label, e.g. "10:00~18:00 · Google", "휴무 · 직접 입력", "영업시간 정보 없음"."""
    src = {
        "user": "직접 입력",
        "google_special": "Google 특별 영업",
        "ai_research": "AI 조사",
        "google_regular": "Google",
        "none": "",
    }[h.source]
    if h.status == "closed":
        return f"휴무 · {src}"
    if h.status == "unknown":
        return "영업시간 정보 없음"
    text = ", ".join(f"{a // 60:02d}:{a % 60:02d}~{(b // 60) % 24:02d}:{b % 60:02d}" for a, b in h.windows)
    return f"{text} · {src}"


def build_itinerary(
    session: Session,
    *,
    trip: Trip,
    city: CityConfig,
    profile: Profile,
    settings: Settings,
    http: httpx.Client | None,
    client: GooglePlacesClient | None,
    time_limit_s: int = 3,
) -> Itinerary:
    """Solve the trip and store the result as a new active version (older versions become archived)."""
    if city.approx is None:
        raise HTTPException(status_code=422, detail="이 도시에는 이동시간 근사 설정(approx)이 없습니다")
    approx = city.approx
    tz = ZoneInfo(trip.timezone)
    dates = [trip.start_date + timedelta(days=i) for i in range((trip.end_date - trip.start_date).days + 1)]
    pace_windows: dict[str, TimeWindow] = {str(k): v for k, v in profile.day_windows.items()}
    day_start, day_end = _window_minutes(pace_windows.get(trip.pace, profile.day_window))
    pins = list(session.scalars(select(TripPin).where(TripPin.trip_id == trip.id)))
    stays = list(session.scalars(select(Stay).where(Stay.trip_id == trip.id, Stay.status == "booked")))
    gids = [p.place.google_place_id for p in pins if p.place.google_place_id]
    gids += [s.place.google_place_id for s in stays if s.place and s.place.google_place_id]
    coords = coords_for(session, client, [g for g in gids if g])

    try:
        score = build_score(trip, session, settings, profile, http, client)
    except HTTPException:
        score = None
    ref_label, _kind, access = _reference(session, trip, score)
    fallback_area = next(
        (a for a in city.stay_areas if a.label == ref_label), city.stay_areas[0] if city.stay_areas else None
    )
    fallback = (
        (LatLng(fallback_area.lat, fallback_area.lng), fallback_area.label)
        if fallback_area and fallback_area.lat is not None and fallback_area.lng is not None
        else None
    )

    # Day windows, adjusted for the booked flight.
    windows = {i: [day_start, day_end] for i in range(len(dates))}
    warnings: dict[int, list[str]] = {i: [] for i in range(len(dates))}
    flight = session.scalar(
        select(FlightOption).where(FlightOption.trip_id == trip.id, FlightOption.status == "booked")
    )
    if flight:
        legs = [LegTimes(lg.direction, lg.dep_airport, lg.dep_at, lg.arr_airport, lg.arr_at) for lg in flight.legs]
        ev = evaluate(legs, profile.buffers_min, access)
        if ev and ev.ready_at:
            windows[0][0] = max(day_start, _local_minutes(ev.ready_at, tz, dates[0]))
        if ev and ev.leave_by:
            windows[len(dates) - 1][1] = min(day_end, _local_minutes(ev.leave_by, tz, dates[-1]))
    else:
        warnings[0].append("확정한 항공편이 없어 첫날을 하루 종일로 계산했습니다")
        warnings[len(dates) - 1].append("확정한 항공편이 없어 마지막 날을 하루 종일로 계산했습니다")

    # Depots: the stay of that night (or of the night before on the last day), else the reference area.
    days: list[Day] = []
    depot_labels: dict[int, str] = {}
    for i, d in enumerate(dates):
        stay = next((s for s in stays if s.check_in and s.check_out and s.check_in <= d < s.check_out), None) or next(
            (s for s in stays if s.check_in and s.check_out and s.check_in < d <= s.check_out), None
        )
        point = _stay_point(stay, coords) if stay else None
        if point and stay:
            depot_labels[i] = stay.label
        elif fallback:
            point, depot_labels[i] = fallback[0], f"{fallback[1]} (숙소 미확정)"
        else:
            raise HTTPException(status_code=422, detail="출발점으로 쓸 숙소나 동네 좌표가 없습니다")
        start, end = windows[i]
        if end - start < 60:
            warnings[i].append("이 날은 쓸 수 있는 시간이 1시간도 안 됩니다")
        days.append(Day(i, start, max(start, end), point))

    # Opening hours per pin and date.
    overrides: dict[tuple[int, date], list[OverrideRow]] = {}
    for o in session.scalars(select(HoursOverride).where(HoursOverride.place_id.in_([p.place_id for p in pins]))):
        overrides.setdefault((o.place_id, o.day), []).append(
            OverrideRow(
                "user" if o.source == "user" else "ai_research", o.status, o.open_min, o.close_min, o.source_url
            )
        )
    horizon = datetime.now(tz).date() + timedelta(days=6)
    meals: dict[str, tuple[int, int]] = {k: _window_minutes(v) for k, v in profile.meal_windows.items()}
    stops: list[Stop] = []
    hours_by_pin: dict[int, dict[int, DayHours]] = {}
    dropped_extra: dict[int, str] = {}
    for p in pins:
        gid = p.place.google_place_id
        point = coords.get(gid) if gid else None
        if point is None:
            dropped_extra[p.id] = "지도 위치가 없어 일정에 넣지 못했습니다"
            continue
        google: GoogleHours | None = None
        if client and gid and p.priority in HOURS_FOR:
            try:
                google = HOURS_CACHE.get(gid, client.details_hours)
            except (PlaceNotFoundError, PlacesError):
                google = None
        per_day: dict[int, list[tuple[int, int]]] = {}
        hours_by_pin[p.id] = {}
        for i, d in enumerate(dates):
            if p.locked_date and p.locked_date != d:
                continue
            h = hours_on(
                d,
                google,
                overrides.get((p.place_id, d), []),
                in_holiday=bool(city.holidays_on(d)),
                special_horizon=horizon,
            )
            hours_by_pin[p.id][i] = h
            if h.status == "closed":
                continue
            wins = h.windows if h.status == "open" else [(0, DAY_MIN)]
            if p.meal in meals:
                wins = _intersect(wins, meals[p.meal])
            if p.reserved_start:
                t = _local_minutes(p.reserved_start, tz, d)
                wins = [(t, t + p.dwell_min)] if 0 <= t < DAY_MIN else []
            if wins:
                per_day[i] = wins
        weight = {str(k): v for k, v in profile.priority_weights.items()}.get(p.priority, 1)
        stops.append(Stop(p.id, point, p.dwell_min, weight * PENALTY_SCALE, per_day))

    def travel(a: object, b: object) -> int:
        assert isinstance(a, LatLng) and isinstance(b, LatLng)
        leg = approx_leg(a, b, approx)
        return leg.minutes + (profile.buffers_min.transfer if leg.mode == "rail" else 0)

    plan = solve(days, stops, travel, time_limit_s=time_limit_s)
    by_id = {p.id: p for p in pins}
    stop_map = stops_by_key(stops)

    # Store.
    for old in session.scalars(select(Itinerary).where(Itinerary.trip_id == trip.id, Itinerary.status == "active")):
        old.status = "archived"
    version = (
        session.scalar(
            select(Itinerary.version).where(Itinerary.trip_id == trip.id).order_by(Itinerary.version.desc())
        )
        or 0
    ) + 1
    itinerary = Itinerary(trip_id=trip.id, version=version, origin="solver", created_at=datetime.now(UTC))
    session.add(itinerary)

    def at(i: int, abs_min: int) -> datetime:
        local = datetime.combine(dates[0], time(0), tz) + timedelta(minutes=abs_min)
        return local.astimezone(UTC)

    day_stats = {}
    for i, d in enumerate(dates):
        visits = plan.days.get(i, [])
        prev = days[i].depot
        lunch = dinner = False
        for seq, v in enumerate(visits):
            pin = by_id[v.key]
            h = hours_by_pin.get(pin.id, {}).get(i)
            w: list[str] = []
            if h and h.holiday_unconfirmed:
                w.append("연휴 기간 영업 미확인")
            if h and h.source == "ai_research":
                w.append("AI 조사 기준 영업시간")
            here = stop_map[v.key].point
            assert isinstance(prev, LatLng) and isinstance(here, LatLng)
            mode = approx_leg(prev, here, approx).mode
            prev = here
            local_start = v.start - i * DAY_MIN
            for meal, flag in (("lunch", "l"), ("dinner", "d")):
                lo, hi = meals.get(meal, (0, 0))
                eats = pin.meal == meal or (
                    pin.place.category in ("food", "cafe") and local_start < hi and v.end - i * DAY_MIN > lo
                )
                if eats and flag == "l":
                    lunch = True
                if eats and flag == "d":
                    dinner = True
            itinerary.items.append(
                ItineraryItem(
                    day=d,
                    seq=seq,
                    kind="meal" if pin.meal else "visit",
                    pin_id=pin.id,
                    label=pin.place.label,
                    start_at=at(i, v.start),
                    end_at=at(i, v.end),
                    move_mode=mode if v.move_min else None,
                    move_min=v.move_min,
                    warnings_json=json.dumps(
                        {"warnings": w, "hours": hours_label(h) if h else None}, ensure_ascii=False
                    ),
                )
            )
        dw = list(warnings[i])
        if visits and not lunch and days[i].start_min <= meals.get("lunch", (0, 0))[0]:
            dw.append("점심 일정이 없습니다")
        if visits and not dinner and days[i].end_min >= meals.get("dinner", (0, 0))[1]:
            dw.append("저녁 일정이 없습니다")
        holidays = city.holidays_on(d)
        if holidays:
            dw.append(f"연휴 기간: {holidays[0].note.split('.')[0]}")
        back = plan.day_end.get(i)
        day_stats[d.isoformat()] = {
            "start_min": days[i].start_min,
            "end_min": days[i].end_min,
            "depot": depot_labels[i],
            "return_min": (back[0] - i * DAY_MIN) if back else None,
            "return_move_min": back[1] if back else None,
            "warnings": dw,
        }
    dropped = {**dropped_extra, **plan.dropped}
    itinerary.solver_stats_json = json.dumps(
        {
            "status": plan.status,
            "approx": True,
            "days": day_stats,
            "dropped": [
                {"pin_id": k, "label": by_id[k].place.label, "priority": by_id[k].priority, "reason": r}
                for k, r in dropped.items()
                if k in by_id
            ],
        },
        ensure_ascii=False,
    )
    session.flush()
    return itinerary


def stops_by_key(stops: list[Stop]) -> dict[int, Stop]:
    """Index stops by pin id."""
    return {s.key: s for s in stops}
