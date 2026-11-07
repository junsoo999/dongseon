"""Build and store an itinerary: gather the trip's pins, stays, flights and opening hours, solve, and validate.

Three ways to make a version share one path: a fresh solve, a re-solve that keeps the user's locked visits, and a
user-edited layout timed as given. Every version is timed by :func:`dongseon.planner.solver.schedule` and checked
by :func:`_visit_warnings`. Travel times are the straight-line approximation ("근사"); Google opening hours are
fetched for must/want pins and kept in process memory only.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from dongseon.api.routes.flights import _reference
from dongseon.api.routes.stays import build_score
from dongseon.core.cities import Approx, CityConfig
from dongseon.core.config import Settings
from dongseon.core.profile import Profile, TimeWindow
from dongseon.db.models import FlightOption, HoursOverride, Itinerary, ItineraryItem, Stay, Trip, TripPin
from dongseon.flights.evaluate import LegTimes, evaluate
from dongseon.matrix.approx import approx_leg
from dongseon.places.service import coords_for
from dongseon.planner.hours import HOURS_CACHE, DayHours, GoogleHours, OverrideRow, hours_on
from dongseon.planner.solver import DAY_MIN, Day, Stop, Visit, schedule, solve
from dongseon.sources.google_places import GooglePlacesClient, LatLng, PlaceNotFoundError, PlacesError

PENALTY_SCALE = 10_000
HOURS_FOR = ("must", "want")  # Enterprise lookups only where they matter


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


@dataclass(frozen=True)
class Edit:
    """A user's layout for a new version.

    Attributes:
        layout: Pin ids per date, in visiting order.
        locked: Pins whose date and order a re-solve keeps.
        excluded: Pins the user took out; a re-solve leaves them out too.
        resolve: Re-solve the unlocked pins (True) or time the layout exactly as given (False).
        base_dropped: Reasons from the version being edited, for pins still left out.
        pinned: Extra pins a re-solve keeps in place without marking them locked (AI suggestion checks).
        held_out: Extra pins a re-solve leaves out without marking them removed (AI suggestion checks).
    """

    layout: dict[date, list[int]]
    locked: frozenset[int] = frozenset()
    excluded: frozenset[int] = frozenset()
    resolve: bool = False
    base_dropped: dict[int, str] = field(default_factory=dict)
    pinned: frozenset[int] = frozenset()
    held_out: frozenset[int] = frozenset()


def edit_of(it: Itinerary, *, resolve: bool = False) -> Edit:
    """The layout, locks and exclusions of a stored version."""
    stats = json.loads(it.solver_stats_json or "{}")
    layout: dict[date, list[int]] = {date.fromisoformat(d): [] for d in stats.get("days") or {}}
    for item in sorted(it.items, key=lambda x: (x.day, x.seq)):
        if item.pin_id:
            layout.setdefault(item.day, []).append(item.pin_id)
    return Edit(
        layout=layout,
        locked=frozenset(i.pin_id for i in it.items if i.locked and i.pin_id),
        excluded=frozenset(stats.get("excluded") or []),
        resolve=resolve,
        base_dropped={x["pin_id"]: x["reason"] for x in stats.get("dropped") or []},
    )


@dataclass
class PlanContext:
    """Everything a version needs: days, stops with per-day windows, opening hours and the travel function."""

    trip: Trip
    city: CityConfig
    tz: ZoneInfo
    dates: list[date]
    days: list[Day]
    depot_labels: dict[int, str]
    depot_points: dict[int, dict[str, object]]  # user or config data only: {"lat", "lng"} or {"place_id"}
    day_warnings: dict[int, list[str]]
    pins: dict[int, TripPin]
    stops: dict[int, Stop]
    hours: dict[int, dict[int, DayHours]]
    unplaceable: dict[int, str]
    meals: dict[str, tuple[int, int]]
    approx: Approx
    travel: Callable[[object, object], int]


def prepare(
    session: Session,
    *,
    trip: Trip,
    city: CityConfig,
    profile: Profile,
    settings: Settings,
    http: httpx.Client | None,
    client: GooglePlacesClient | None,
) -> PlanContext:
    """Gather days, depots, opening hours and stops for a trip."""
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
    depot_points: dict[int, dict[str, object]] = {}
    for i, d in enumerate(dates):
        stay = next((s for s in stays if s.check_in and s.check_out and s.check_in <= d < s.check_out), None) or next(
            (s for s in stays if s.check_in and s.check_out and s.check_in < d <= s.check_out), None
        )
        point = _stay_point(stay, coords) if stay else None
        if point and stay:
            depot_labels[i] = stay.label
            if stay.user_lat is not None and stay.user_lng is not None:
                depot_points[i] = {"lat": stay.user_lat, "lng": stay.user_lng}
            elif stay.place and stay.place.google_place_id:
                depot_points[i] = {"place_id": stay.place.google_place_id}
        elif fallback_area and fallback_area.lat is not None and fallback_area.lng is not None:
            point = LatLng(fallback_area.lat, fallback_area.lng)
            depot_labels[i] = f"{fallback_area.label} (숙소 미확정)"
            depot_points[i] = {"lat": fallback_area.lat, "lng": fallback_area.lng}
        else:
            raise HTTPException(status_code=422, detail="출발점으로 쓸 숙소나 동네 좌표가 없습니다")
        start, end = windows[i]
        if end - start < 60:
            warnings[i].append("이 날은 쓸 수 있는 시간이 1시간도 안 됩니다")
        days.append(Day(i, start, max(start, end), point))

    # Opening hours per pin and date (all dates, so user-placed visits can be checked too).
    overrides: dict[tuple[int, date], list[OverrideRow]] = {}
    for o in session.scalars(select(HoursOverride).where(HoursOverride.place_id.in_([p.place_id for p in pins]))):
        overrides.setdefault((o.place_id, o.day), []).append(
            OverrideRow(
                "user" if o.source == "user" else "ai_research", o.status, o.open_min, o.close_min, o.source_url
            )
        )
    horizon = datetime.now(tz).date() + timedelta(days=6)
    meals: dict[str, tuple[int, int]] = {k: _window_minutes(v) for k, v in profile.meal_windows.items()}
    weights = {str(k): v for k, v in profile.priority_weights.items()}
    stops: dict[int, Stop] = {}
    hours_by_pin: dict[int, dict[int, DayHours]] = {}
    unplaceable: dict[int, str] = {}
    for p in pins:
        gid = p.place.google_place_id
        point = coords.get(gid) if gid else None
        if point is None:
            unplaceable[p.id] = "지도 위치가 없어 일정에 넣지 못했습니다"
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
            h = hours_on(
                d,
                google,
                overrides.get((p.place_id, d), []),
                in_holiday=bool(city.holidays_on(d)),
                special_horizon=horizon,
            )
            hours_by_pin[p.id][i] = h
            if h.status == "closed" or (p.locked_date and p.locked_date != d):
                continue
            wins = h.windows if h.status == "open" else [(0, DAY_MIN)]
            if p.meal in meals:
                wins = _intersect(wins, meals[p.meal])
            if p.reserved_start:
                t = _local_minutes(p.reserved_start, tz, d)
                wins = [(t, t + p.dwell_min)] if 0 <= t < DAY_MIN else []
            if wins:
                per_day[i] = wins
        stops[p.id] = Stop(p.id, point, p.dwell_min, weights.get(p.priority, 1) * PENALTY_SCALE, per_day)

    def travel(a: object, b: object) -> int:
        assert isinstance(a, LatLng) and isinstance(b, LatLng)
        leg = approx_leg(a, b, approx)
        return leg.minutes + (profile.buffers_min.transfer if leg.mode == "rail" else 0)

    return PlanContext(
        trip=trip,
        city=city,
        tz=tz,
        dates=dates,
        days=days,
        depot_labels=depot_labels,
        depot_points=depot_points,
        day_warnings=warnings,
        pins={p.id: p for p in pins},
        stops=stops,
        hours=hours_by_pin,
        unplaceable=unplaceable,
        meals=meals,
        approx=approx,
        travel=travel,
    )


def _check_layout(ctx: PlanContext, layout: dict[date, list[int]]) -> dict[int, list[int]]:
    """Map a date layout to day indexes, rejecting unknown dates, unknown or unplaceable pins and duplicates."""
    index = {d: i for i, d in enumerate(ctx.dates)}
    out: dict[int, list[int]] = {}
    seen: set[int] = set()
    for d, pin_ids in layout.items():
        if d not in index:
            raise HTTPException(status_code=422, detail=f"여행 기간이 아닌 날짜입니다: {d.isoformat()}")
        for pid in pin_ids:
            if pid not in ctx.pins:
                raise HTTPException(status_code=422, detail="이 여행의 장소가 아닙니다")
            if pid not in ctx.stops:
                raise HTTPException(status_code=422, detail=f"지도 위치가 없는 장소는 넣을 수 없습니다: {pid}")
            if pid in seen:
                raise HTTPException(status_code=422, detail="같은 장소가 두 번 들어 있습니다")
            seen.add(pid)
        out[index[d]] = list(pin_ids)
    return out


def _solve_layout(
    ctx: PlanContext, edit: Edit | None, time_limit_s: int
) -> tuple[dict[int, list[int]], dict[int, str], str]:
    """Solve for an order per day, keeping locked pins on their date and in their order."""
    excluded = (edit.excluded | edit.held_out) if edit else frozenset()
    locks: dict[int, tuple[int, int]] = {}
    if edit:
        keep = edit.locked | edit.pinned
        for i, pin_ids in _check_layout(ctx, edit.layout).items():
            for order, pid in enumerate(p for p in pin_ids if p in keep):
                locks[pid] = (i, order)
    stops: list[Stop] = []
    for pid, stop in ctx.stops.items():
        if pid in excluded:
            continue
        if pid in locks:
            i = locks[pid][0]
            # The user placed it here: keep it even if its hours do not fit (the validator warns).
            wins = stop.windows.get(i) or [(0, DAY_MIN)]
            stop = replace(stop, windows={i: wins}, lock=locks[pid])
        stops.append(stop)
    plan = solve(ctx.days, stops, ctx.travel, time_limit_s=time_limit_s)
    layout = {i: [v.key for v in plan.days.get(i, [])] for i in range(len(ctx.days))}
    return layout, plan.dropped, plan.status


def _visit_warnings(ctx: PlanContext, i: int, pin: TripPin, visit: Visit, h: DayHours | None) -> list[str]:
    """Warnings for one visit: hours, holidays, the pin's fixed date and reservation."""
    w: list[str] = []
    if h and h.status == "closed":
        w.append("이 날은 휴무입니다")
    elif not visit.in_window:
        w.append("영업시간(식사 시간대) 안에 들어가지 않습니다" if pin.meal else "영업시간 안에 들어가지 않습니다")
    if h and h.holiday_unconfirmed:
        w.append("연휴 기간 영업 미확인")
    if h and h.source == "ai_research":
        w.append("AI 조사 기준 영업시간")
    d = ctx.dates[i]
    if pin.locked_date and pin.locked_date != d:
        w.append(f"고정한 날짜({pin.locked_date.month}/{pin.locked_date.day})와 다릅니다")
    if pin.reserved_start:
        reserved = pin.reserved_start.astimezone(ctx.tz)
        if reserved.date() != d or _minutes(reserved.time()) != visit.start - i * DAY_MIN:
            w.append(f"예약 시각({reserved.month}/{reserved.day} {reserved:%H:%M})과 다릅니다")
    return w


def _store(
    session: Session,
    ctx: PlanContext,
    layout: dict[int, list[int]],
    *,
    origin: str,
    locked: frozenset[int],
    excluded: frozenset[int],
    dropped: dict[int, str],
    status: str = "ok",
    persist: bool = True,
) -> Itinerary:
    """Time, validate and save a layout as the new active version (older versions become archived).

    With ``persist=False`` nothing is written: the result is a transient preview (id 0, negative item ids).
    """
    trip = ctx.trip
    version = (
        session.scalar(
            select(Itinerary.version).where(Itinerary.trip_id == trip.id).order_by(Itinerary.version.desc())
        )
        or 0
    ) + 1
    if persist:
        for old in session.scalars(
            select(Itinerary).where(Itinerary.trip_id == trip.id, Itinerary.status == "active")
        ):
            old.status = "archived"
    itinerary = Itinerary(
        trip_id=trip.id,
        version=version,
        origin=origin,
        status="active" if persist else "preview",
        created_at=datetime.now(UTC),
    )
    if persist:
        session.add(itinerary)
    else:
        itinerary.id = 0

    def at(abs_min: int) -> datetime:
        local = datetime.combine(ctx.dates[0], time(0), ctx.tz) + timedelta(minutes=abs_min)
        return local.astimezone(UTC)

    meals = ctx.meals
    day_stats = {}
    for i, d in enumerate(ctx.dates):
        day = ctx.days[i]
        order = [ctx.stops[pid] for pid in layout.get(i, [])]
        visits, (back_abs, back_move) = schedule(day, order, ctx.travel)
        prev = day.depot
        lunch = dinner = False
        for seq, v in enumerate(visits):
            pin = ctx.pins[v.key]
            h = ctx.hours.get(pin.id, {}).get(i)
            here = ctx.stops[v.key].point
            assert isinstance(prev, LatLng) and isinstance(here, LatLng)
            mode = approx_leg(prev, here, ctx.approx).mode
            prev = here
            local_start, local_end = v.start - i * DAY_MIN, v.end - i * DAY_MIN
            for meal in ("lunch", "dinner"):
                lo, hi = meals.get(meal, (0, 0))
                eats = pin.meal == meal or (
                    pin.place.category in ("food", "cafe") and local_start < hi and local_end > lo
                )
                lunch = lunch or (eats and meal == "lunch")
                dinner = dinner or (eats and meal == "dinner")
            itinerary.items.append(
                ItineraryItem(
                    day=d,
                    seq=seq,
                    kind="meal" if pin.meal else "visit",
                    pin_id=pin.id,
                    label=pin.place.label,
                    start_at=at(v.start),
                    end_at=at(v.end),
                    move_mode=mode if v.move_min else None,
                    move_min=v.move_min,
                    locked=pin.id in locked,
                    warnings_json=json.dumps(
                        {
                            "warnings": _visit_warnings(ctx, i, pin, v, h),
                            "hours": hours_label(h) if h else None,
                            "hours_source": h.source if h else None,
                        },
                        ensure_ascii=False,
                    ),
                )
            )
        dw = list(ctx.day_warnings[i])
        return_min = back_abs - i * DAY_MIN
        if visits and return_min > day.end_min:
            over = return_min - day.end_min
            dw.append(f"하루 끝({day.end_min // 60:02d}:{day.end_min % 60:02d})보다 {over}분 늦게 돌아옵니다")
        if visits and not lunch and day.start_min <= meals.get("lunch", (0, 0))[0]:
            dw.append("점심 일정이 없습니다")
        if visits and not dinner and day.end_min >= meals.get("dinner", (0, 0))[1]:
            dw.append("저녁 일정이 없습니다")
        holidays = ctx.city.holidays_on(d)
        if holidays:
            dw.append(f"연휴 기간: {holidays[0].note.split('.')[0]}")
        day_stats[d.isoformat()] = {
            "start_min": day.start_min,
            "end_min": day.end_min,
            "depot": ctx.depot_labels[i],
            "depot_point": ctx.depot_points.get(i),
            "return_min": return_min if visits else None,
            "return_move_min": back_move if visits else None,
            "warnings": dw,
        }
    placed = {pid for pids in layout.values() for pid in pids}
    left_out = {pid: ctx.unplaceable[pid] for pid in ctx.unplaceable}
    for pid in ctx.stops:
        if pid in placed:
            continue
        if pid in excluded:
            left_out[pid] = "직접 뺐습니다"
        else:
            left_out[pid] = dropped.get(pid, "일정에 넣지 않았습니다")
    itinerary.solver_stats_json = json.dumps(
        {
            "status": status,
            "approx": True,
            "days": day_stats,
            "excluded": sorted(excluded & set(ctx.pins)),
            "dropped": [
                {
                    "pin_id": k,
                    "label": ctx.pins[k].place.label,
                    "priority": ctx.pins[k].priority,
                    "reason": r,
                    "excluded": k in excluded,
                }
                for k, r in left_out.items()
            ],
        },
        ensure_ascii=False,
    )
    if persist:
        session.flush()
    else:
        for n, item in enumerate(itinerary.items, start=1):
            item.id = -n
    return itinerary


def make_version(
    session: Session,
    ctx: PlanContext,
    edit: Edit | None,
    *,
    origin: str | None = None,
    time_limit_s: int = 3,
    persist: bool = True,
) -> Itinerary:
    """Solve or time a layout in a prepared context and store it (or return a transient preview).

    Args:
        session: DB session; the caller commits.
        ctx: The trip's prepared context (see :func:`prepare`).
        edit: ``None`` for a fresh solve; otherwise a layout, re-solved around locked pins or timed as is.
        origin: Stored origin; defaults to "solver" for solves and "user" for layouts timed as given.
        time_limit_s: Solver time limit.
        persist: Save as the new active version (True) or only build a preview (False).
    """
    if edit is None or edit.resolve:
        layout, dropped, status = _solve_layout(ctx, edit, time_limit_s)
        if edit:
            dropped = {**edit.base_dropped, **dropped}
        origin = origin or "solver"
    else:
        layout, dropped, status = _check_layout(ctx, edit.layout), edit.base_dropped, "ok"
        origin = origin or "user"
    return _store(
        session,
        ctx,
        layout,
        origin=origin,
        locked=edit.locked if edit else frozenset(),
        excluded=edit.excluded if edit else frozenset(),
        dropped=dropped,
        status=status,
        persist=persist,
    )


def build_itinerary(
    session: Session,
    *,
    trip: Trip,
    city: CityConfig,
    profile: Profile,
    settings: Settings,
    http: httpx.Client | None,
    client: GooglePlacesClient | None,
    edit: Edit | None = None,
    time_limit_s: int = 3,
) -> Itinerary:
    """Make and store a new active version.

    Args:
        session: DB session; the caller commits.
        trip: The trip.
        city: Its city config (approximation parameters, stay areas, holidays).
        profile: Household preferences (day windows, meals, buffers, priority weights).
        settings: App settings.
        http: HTTP client for the stay score (FX), or ``None``.
        client: Places client for coordinates and opening hours, or ``None`` without a key.
        edit: ``None`` for a fresh solve; otherwise the user's layout, re-solved around locked pins or timed as is.
        time_limit_s: Solver time limit.
    """
    ctx = prepare(session, trip=trip, city=city, profile=profile, settings=settings, http=http, client=client)
    return make_version(session, ctx, edit, time_limit_s=time_limit_s)
