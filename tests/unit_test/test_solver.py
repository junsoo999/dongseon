import itertools

from dongseon.planner.solver import DAY_MIN, Day, Stop, solve


# Points on a line (minutes apart = distance); the stay is at 0.
def travel(a: object, b: object) -> int:
    return abs(int(a) - int(b))  # type: ignore[arg-type]


STAY = 0
ALL_DAY = [(0, DAY_MIN)]


def _days(n: int, start: int = 9 * 60, end: int = 21 * 60) -> list[Day]:
    return [Day(i, start, end, STAY) for i in range(n)]


def test_visits_respect_hours_and_order_by_distance() -> None:
    stops = [
        Stop(1, 30, 60, 100_000, {0: ALL_DAY}),
        Stop(2, 60, 60, 100_000, {0: ALL_DAY}),
        Stop(3, 10, 60, 100_000, {0: [(14 * 60, 18 * 60)]}),  # only afternoon
    ]
    plan = solve(_days(1), stops, travel, time_limit_s=1)
    assert plan.status == "ok" and not plan.dropped
    visits = plan.days[0]
    assert {v.key for v in visits} == {1, 2, 3}
    museum = next(v for v in visits if v.key == 3)
    assert museum.start >= 14 * 60 and museum.end <= 18 * 60
    assert all(a.end + b.move_min <= b.start for a, b in itertools.pairwise(visits))
    back, _ = plan.day_end[0]
    assert back <= 21 * 60


def test_closed_day_moves_visit_to_an_open_day() -> None:
    stops = [Stop(1, 20, 60, 100_000, {1: ALL_DAY})]  # closed on day 0
    plan = solve(_days(2), stops, travel, time_limit_s=1)
    assert [v.key for v in plan.days[1]] == [1]
    assert plan.days[0] == []
    assert plan.days[1][0].start >= DAY_MIN + 9 * 60


def test_low_priority_is_dropped_when_time_runs_out() -> None:
    stops = [
        Stop(1, 30, 300, 1_000_000, {0: ALL_DAY}),  # must
        Stop(2, 30, 300, 1_000_000, {0: ALL_DAY}),  # must
        Stop(3, 30, 300, 10_000, {0: ALL_DAY}),  # maybe: only 12 h available
    ]
    plan = solve(_days(1), stops, travel, time_limit_s=1)
    assert set(plan.dropped) == {3}
    assert "시간" in plan.dropped[3]


def test_never_open_and_too_short_windows_are_explained() -> None:
    stops = [
        Stop(1, 10, 60, 100_000, {}),
        Stop(2, 10, 120, 100_000, {0: [(10 * 60, 11 * 60)]}),
    ]
    plan = solve(_days(1), stops, travel, time_limit_s=1)
    assert plan.dropped[1] == "여행 기간에 여는 날이 없습니다"
    assert "짧거나" in plan.dropped[2]


def test_split_windows_skip_the_gap() -> None:
    lunch_break = [(9 * 60, 12 * 60), (14 * 60, 17 * 60)]
    stops = [Stop(1, 5, 90, 100_000, {0: lunch_break}), Stop(2, 300, 120, 100_000, {0: [(9 * 60, 12 * 60 + 30)]})]
    plan = solve(_days(1), stops, travel, time_limit_s=1)
    v = next(x for x in plan.days[0] if x.key == 1)
    assert v.end <= 12 * 60 or v.start >= 14 * 60


def test_visits_spread_over_days() -> None:
    stops = [Stop(k, 10 + k, 60, 100_000, {0: ALL_DAY, 1: ALL_DAY, 2: ALL_DAY}) for k in range(6)]
    plan = solve(_days(3), stops, travel, time_limit_s=1)
    assert not plan.dropped
    assert sorted(len(v) for v in plan.days.values()) == [2, 2, 2]
