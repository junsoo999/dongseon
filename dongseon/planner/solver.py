"""Day-by-day route solver: a vehicle routing problem with time windows (OR-Tools).

Each trip day is one vehicle that starts and ends at that night's stay. Each pin gets one node per day it may be
visited (its opening hours differ by date); a disjunction lets at most one copy be used, with a drop penalty from
its priority. Times are minutes from 00:00 of the first trip day, so one time dimension spans the whole trip.

A locked stop (the user fixed its day and its order among that day's locked stops) gets one copy on that day, a
penalty no other stop can outweigh, and precedence constraints. Final times always come from :func:`schedule`
(earliest start along the chosen order), which also times user-edited layouts.
"""

import itertools
from collections.abc import Callable
from dataclasses import dataclass, field

from ortools.constraint_solver import pywrapcp, routing_enums_pb2
from ortools.util import optional_boolean_pb2

DAY_MIN = 24 * 60
LOCK_PENALTY = 10**9  # far above any priority penalty: drop a locked stop only if it cannot fit at all

Window = tuple[int, int]  # local minutes on that day


@dataclass(frozen=True)
class Day:
    """One trip day: its usable window (local minutes) and where it starts and ends.

    The day starts and ends at ``depot`` (the night's stay) unless ``start_point`` / ``end_point`` say otherwise
    (e.g. the airport on the arrival or departure day); the window is then measured at those points.
    """

    index: int
    start_min: int
    end_min: int
    depot: object  # anything the travel function understands (e.g. a LatLng)
    start_point: object | None = None
    end_point: object | None = None

    @property
    def origin(self) -> object:
        """Where the day starts."""
        return self.depot if self.start_point is None else self.start_point

    @property
    def finish(self) -> object:
        """Where the day ends."""
        return self.depot if self.end_point is None else self.end_point


@dataclass(frozen=True)
class Stop:
    """A pin to schedule."""

    key: int
    point: object
    dwell_min: int
    penalty: int
    windows: dict[int, list[Window]]  # day index -> windows when the visit may start..end (local minutes)
    lock: tuple[int, int] | None = None  # (day index, order among that day's locked stops)


@dataclass(frozen=True)
class Visit:
    """A scheduled visit in absolute trip minutes."""

    key: int
    day: int
    arrive: int  # arrival after the move (before any wait)
    start: int
    end: int
    move_min: int  # travel from the previous stop or the stay
    in_window: bool = True  # False when no opening window fits (only for forced, user-placed visits)


@dataclass
class Plan:
    """Solver output."""

    days: dict[int, list[Visit]] = field(default_factory=dict)
    day_end: dict[int, tuple[int, int]] = field(default_factory=dict)  # day -> (arrive back at stay, move minutes)
    dropped: dict[int, str] = field(default_factory=dict)  # stop key -> reason (Korean)
    status: str = "ok"  # ok | no_solution


def _abs(day: int, minute: int) -> int:
    return day * DAY_MIN + minute


def _usable(windows: list[Window], dwell: int, day: Day) -> list[Window]:
    """Start-time ranges inside the day window that leave room for the whole dwell before closing."""
    out: list[Window] = []
    for open_, close in windows:
        lo = max(open_, day.start_min)
        hi = min(close, day.end_min) - dwell
        if hi >= lo:
            out.append((lo, hi))
    return out


def schedule(
    day: Day, stops: list[Stop], travel: Callable[[object, object], int]
) -> tuple[list[Visit], tuple[int, int]]:
    """Time a fixed order of stops on one day at the earliest possible starts.

    A stop starts at the first usable window it can still reach; when none fits (closed, or too late) it starts on
    arrival and is marked ``in_window=False``. Late finishes are not cut: the validator reports them.

    Returns:
        The visits in absolute trip minutes and (arrival at the day's end point, minutes of that move).
    """
    t = day.start_min
    prev = day.origin
    visits: list[Visit] = []
    for s in stops:
        m = 0 if s.point is prev else int(travel(prev, s.point))
        arrive = t + m
        start, fits = arrive, False
        for lo, hi in _usable(s.windows.get(day.index, []), s.dwell_min, day):
            if arrive <= hi:
                start, fits = max(arrive, lo), True
                break
        visits.append(
            Visit(
                key=s.key,
                day=day.index,
                arrive=_abs(day.index, arrive),
                start=_abs(day.index, start),
                end=_abs(day.index, start + s.dwell_min),
                move_min=m,
                in_window=fits,
            )
        )
        t, prev = start + s.dwell_min, s.point
    back = 0 if prev is day.finish else int(travel(prev, day.finish))
    return visits, (_abs(day.index, t + back), back)


def solve(
    days: list[Day],
    stops: list[Stop],
    travel: Callable[[object, object], int],
    *,
    time_limit_s: int = 3,
    balance_penalty: int = 2_000,
) -> Plan:
    """Plan visits across days.

    Args:
        days: Trip days in order.
        stops: Pins with per-day windows; a day missing from ``windows`` is not allowed.
        travel: Minutes between two points (already including transfer buffers).
        time_limit_s: Local search time limit.
        balance_penalty: Cost per visit above the even share on a day (keep it below the drop penalties).

    Returns:
        Visits per day, the return to the stay per day, and dropped stops with reasons.
    """
    plan = Plan()
    nodes: list[tuple[str, int, int]] = []  # (kind, day or stop key, day)
    points: list[object] = []
    service: list[int] = []
    starts, ends = [], []
    for d in days:
        starts.append(len(nodes))
        nodes.append(("start", d.index, d.index))
        points.append(d.origin)
        service.append(0)
        ends.append(len(nodes))
        nodes.append(("end", d.index, d.index))
        points.append(d.finish)
        service.append(0)
    copies: dict[int, list[tuple[int, list[Window]]]] = {}
    by_key = {s.key: s for s in stops}
    for s in stops:
        for d in days:
            if s.lock and s.lock[0] != d.index:
                continue
            usable = _usable(s.windows.get(d.index, []), s.dwell_min, d)
            if not usable:
                continue
            copies.setdefault(s.key, []).append(
                (len(nodes), [(_abs(d.index, a), _abs(d.index, b)) for a, b in usable])
            )
            nodes.append(("stop", s.key, d.index))
            points.append(s.point)
            service.append(s.dwell_min)
    for s in stops:
        if s.key not in copies:
            plan.dropped[s.key] = _never_fits_reason(s, days)

    manager = pywrapcp.RoutingIndexManager(len(nodes), len(days), starts, ends)
    routing = pywrapcp.RoutingModel(manager)
    move_cache: dict[tuple[int, int], int] = {}

    def move(i: int, j: int) -> int:
        if (i, j) not in move_cache:
            move_cache[(i, j)] = 0 if points[i] is points[j] else int(travel(points[i], points[j]))
        return move_cache[(i, j)]

    def transit(from_index: int, to_index: int) -> int:
        i, j = manager.IndexToNode(from_index), manager.IndexToNode(to_index)
        return service[i] + move(i, j)

    def cost(from_index: int, to_index: int) -> int:
        return move(manager.IndexToNode(from_index), manager.IndexToNode(to_index))

    transit_idx = routing.RegisterTransitCallback(transit)
    routing.SetArcCostEvaluatorOfAllVehicles(routing.RegisterTransitCallback(cost))
    horizon = len(days) * DAY_MIN + DAY_MIN
    routing.AddDimension(transit_idx, DAY_MIN, horizon, False, "time")
    time_dim = routing.GetDimensionOrDie("time")
    # Spread visits over the days: a soft cap on visits per day, cheaper than dropping a want/must pin.
    count_idx = routing.RegisterUnaryTransitCallback(
        lambda index: 1 if nodes[manager.IndexToNode(index)][0] == "stop" else 0
    )
    routing.AddDimension(count_idx, 0, len(stops) + 1, True, "visits")
    visits_dim = routing.GetDimensionOrDie("visits")
    open_days = [d for d in days if d.end_min - d.start_min >= 60] or days
    per_day = max(1, -(-len(copies) // len(open_days)))
    for v, d in enumerate(days):
        cap = per_day if d in open_days else 0
        visits_dim.SetCumulVarSoftUpperBound(routing.End(v), cap, balance_penalty)
    for v, d in enumerate(days):
        for idx in (routing.Start(v), routing.End(v)):
            time_dim.CumulVar(idx).SetRange(_abs(d.index, d.start_min), _abs(d.index, d.end_min))
        routing.AddVariableMinimizedByFinalizer(time_dim.CumulVar(routing.End(v)))
    for key, entries in copies.items():
        indices = []
        for node, ranges in entries:
            idx = manager.NodeToIndex(node)
            indices.append(idx)
            day = nodes[node][2]
            # Only that day's vehicle (-1 = not visited). SetAllowedVehiclesForIndex takes no Python list in 9.15.
            routing.VehicleVar(idx).SetValues([-1, day])
            cumul = time_dim.CumulVar(idx)
            lo, hi = ranges[0][0], ranges[-1][1]
            cumul.SetRange(lo, hi)
            for (_a, b), (c, _d) in itertools.pairwise(ranges):
                if c > b + 1:
                    cumul.RemoveInterval(b + 1, c - 1)
        stop = by_key[key]
        routing.AddDisjunction(indices, LOCK_PENALTY if stop.lock else stop.penalty, 1)
    # Locked stops keep their order within a day.
    locked = sorted((s.lock, s.key) for s in stops if s.lock and s.key in copies)
    for (la, ka), (lb, kb) in itertools.pairwise(locked):
        if la[0] != lb[0]:
            continue
        a = manager.NodeToIndex(copies[ka][0][0])
        b = manager.NodeToIndex(copies[kb][0][0])
        routing.solver().Add(time_dim.CumulVar(a) + by_key[ka].dwell_min <= time_dim.CumulVar(b))

    params = pywrapcp.DefaultRoutingSearchParameters()
    params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    params.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    params.time_limit.seconds = time_limit_s
    # Moving a visit to another day swaps one day's copy for another in the same disjunction in a single step.
    ops = params.local_search_operators
    ops.use_extended_swap_active = optional_boolean_pb2.BOOL_TRUE
    ops.use_relocate_and_make_active = optional_boolean_pb2.BOOL_TRUE
    solution = routing.SolveWithParameters(params)
    if solution is None:
        plan.status = "no_solution"
        for s in stops:
            plan.dropped.setdefault(s.key, "일정을 만들 수 없었습니다")
        return plan

    visited: set[int] = set()
    for v, d in enumerate(days):
        order: list[Stop] = []
        idx = solution.Value(routing.NextVar(routing.Start(v)))
        while not routing.IsEnd(idx):
            order.append(by_key[nodes[manager.IndexToNode(idx)][1]])
            idx = solution.Value(routing.NextVar(idx))
        plan.days[d.index], plan.day_end[d.index] = schedule(d, order, travel)
        visited.update(s.key for s in order)
    for s in stops:
        if s.key not in visited and s.key not in plan.dropped:
            plan.dropped[s.key] = "하루 시간 안에 넣지 못했습니다 (우선순위가 높은 곳 먼저)"
    return plan


def _never_fits_reason(s: Stop, days: list[Day]) -> str:
    if not any(s.windows.get(d.index) for d in days):
        return "여행 기간에 여는 날이 없습니다"
    return "영업시간이 머무는 시간보다 짧거나 하루 일정 밖입니다"
