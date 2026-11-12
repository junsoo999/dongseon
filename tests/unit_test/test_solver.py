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


def test_locked_stops_keep_day_and_order() -> None:
    # Without locks the solver would visit 1 (near) before 2 (far) on day 0.
    stops = [
        Stop(1, 10, 60, 100_000, {1: ALL_DAY}, lock=(1, 1)),
        Stop(2, 50, 60, 100_000, {1: ALL_DAY}, lock=(1, 0)),
        Stop(3, 20, 60, 100_000, {0: ALL_DAY, 1: ALL_DAY}),
    ]
    plan = solve(_days(2), stops, travel, time_limit_s=1)
    day1 = [v.key for v in plan.days[1]]
    assert day1.index(2) < day1.index(1)
    assert not plan.dropped


def test_schedule_waits_for_opening_and_flags_misses() -> None:
    from dongseon.planner.solver import schedule

    day = _days(1)[0]
    stops = [
        Stop(1, 30, 60, 1, {0: [(10 * 60, 12 * 60)]}),  # opens 10:00
        Stop(2, 40, 60, 1, {}),  # closed that day
    ]
    visits, (back, back_move) = schedule(day, stops, travel)
    assert visits[0].start == 10 * 60 and visits[0].in_window
    assert visits[1].start == 11 * 60 + 10 and not visits[1].in_window
    assert back_move == 40 and back == 12 * 60 + 10 + 40


MEALS = {"breakfast": (9 * 60, 10 * 60 + 30), "lunch": (11 * 60 + 30, 13 * 60 + 30), "dinner": (18 * 60, 20 * 60 + 30)}


def test_at_most_one_restaurant_per_meal_slot_and_cafes_are_free() -> None:
    restaurants = [Stop(k, 10 * k, 60, 100_000, {0: ALL_DAY}, slots=dict(MEALS)) for k in range(1, 5)]
    cafes = [Stop(10 + k, 5 * k, 30, 100_000, {0: ALL_DAY}) for k in range(1, 3)]
    plan = solve(_days(1), restaurants + cafes, travel, time_limit_s=1)
    visits = plan.days[0]
    meals = [v for v in visits if v.key < 10]
    assert len(meals) == 3 and {11, 12} <= {v.key for v in visits}
    for v in meals:  # one in each slot, each inside its slot
        assert sum(lo <= v.start < hi and v.end <= hi for lo, hi in MEALS.values()) == 1
    assert len({next(k for k, (lo, hi) in MEALS.items() if lo <= v.start < hi) for v in meals}) == 3
    [(dropped, reason)] = plan.dropped.items()
    assert dropped < 10 and "식사 자리" in reason


def test_a_marked_meal_only_takes_its_own_slot() -> None:
    stops = [
        Stop(1, 10, 60, 100_000, {0: ALL_DAY, 1: ALL_DAY}, slots={"dinner": MEALS["dinner"]}),
        Stop(2, 20, 60, 100_000, {0: ALL_DAY, 1: ALL_DAY}, slots={"dinner": MEALS["dinner"]}),
    ]
    plan = solve(_days(2), stops, travel, time_limit_s=1)
    assert not plan.dropped
    assert sorted(len(plan.days[d]) for d in (0, 1)) == [1, 1]  # one dinner a day
    assert all(v.start - v.day * DAY_MIN >= 18 * 60 for d in (0, 1) for v in plan.days[d])


def test_meal_slots_follow_category_meal_mark_and_reservation() -> None:
    from datetime import UTC, datetime
    from zoneinfo import ZoneInfo

    from dongseon.db.models import Place, TripPin
    from dongseon.planner.build import meal_slots

    tz = ZoneInfo("Asia/Tokyo")

    def pin(category: str, meal: str | None = None, reserved: datetime | None = None) -> TripPin:
        return TripPin(place=Place(label="x", category=category), meal=meal, reserved_start=reserved, dwell_min=60)

    assert meal_slots(pin("cafe"), MEALS, tz) is None  # dessert and cafes are not meals
    assert meal_slots(pin("food"), MEALS, tz) == MEALS
    assert meal_slots(pin("bar", meal="dinner"), MEALS, tz) == {"dinner": MEALS["dinner"]}
    at_12 = datetime(2030, 12, 28, 3, 0, tzinfo=UTC)  # 12:00 in Tokyo
    assert meal_slots(pin("food", reserved=at_12), MEALS, tz) == {"lunch": (720, 780)}
    at_16 = datetime(2030, 12, 28, 7, 0, tzinfo=UTC)  # 16:00: outside every slot, not counted
    assert meal_slots(pin("food", reserved=at_16), MEALS, tz) is None


def test_max_meals_caps_restaurants_even_with_more_slots() -> None:
    slots = dict(MEALS) | {"afternoon": (14 * 60 + 30, 17 * 60)}  # four slots
    restaurants = [Stop(k, 10 * k, 60, 100_000, {0: ALL_DAY}, slots=slots) for k in range(1, 5)]
    plan = solve(_days(1), restaurants, travel, time_limit_s=1, max_meals=3)
    assert len(plan.days[0]) == 3
    [(_key, reason)] = plan.dropped.items()
    assert "식사 자리" in reason
