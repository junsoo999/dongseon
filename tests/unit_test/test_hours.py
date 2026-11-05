from datetime import date

from dongseon.planner.hours import HoursCache, OverrideRow, hours_on, parse_google_hours

from .conftest import places_fixture

MUSEUM = parse_google_hours(places_fixture("details_hours"))
NONE = parse_google_hours(places_fixture("details_hours_missing"))
MON, TUE, FRI = date(2030, 12, 23), date(2030, 12, 24), date(2030, 12, 27)


def test_weekly_hours_and_closed_day() -> None:
    assert MUSEUM.has_weekly
    assert hours_on(TUE, MUSEUM, [], in_holiday=False).windows == [(600, 1080)]
    mon = hours_on(MON, MUSEUM, [], in_holiday=False)
    assert (mon.status, mon.source) == ("closed", "google_regular")


def test_special_hours_win_within_horizon_only() -> None:
    fri = hours_on(FRI, MUSEUM, [], in_holiday=False)
    assert (fri.source, fri.windows) == ("google_special", [(600, 900)])
    late = hours_on(FRI, MUSEUM, [], in_holiday=False, special_horizon=date(2030, 12, 26))
    assert late.source == "google_regular"


def test_precedence_user_over_google_over_ai() -> None:
    user = OverrideRow("user", "closed", None, None)
    ai = OverrideRow("ai_research", "open", 660, 900, "https://example.com")
    assert hours_on(FRI, MUSEUM, [ai, user], in_holiday=True).source == "user"
    assert hours_on(FRI, MUSEUM, [ai], in_holiday=True).source == "google_special"
    tue = hours_on(TUE, MUSEUM, [ai], in_holiday=True)
    assert (tue.source, tue.windows, tue.source_url) == ("ai_research", [(660, 900)], "https://example.com")


def test_holiday_without_confirmation_is_flagged() -> None:
    assert hours_on(TUE, MUSEUM, [], in_holiday=True).holiday_unconfirmed
    unknown = hours_on(TUE, NONE, [], in_holiday=True)
    assert (unknown.status, unknown.source, unknown.holiday_unconfirmed) == ("unknown", "none", True)


def test_24_hours_and_overnight_periods() -> None:
    always = parse_google_hours({"regularOpeningHours": {"periods": [{"open": {"day": 0, "hour": 0, "minute": 0}}]}})
    assert hours_on(TUE, always, [], in_holiday=False).windows == [(0, 1440)]
    bar = parse_google_hours(
        {"regularOpeningHours": {"periods": [{"open": {"day": 2, "hour": 18}, "close": {"day": 3, "hour": 2}}]}}
    )
    assert hours_on(TUE, bar, [], in_holiday=False).windows == [(1080, 1560)]


def test_cache_expires() -> None:
    now = [0.0]
    calls: list[str] = []
    cache = HoursCache(ttl_s=600, clock=lambda: now[0])

    def fetch(pid: str) -> dict:
        calls.append(pid)
        return places_fixture("details_hours")

    cache.get("a", fetch)
    cache.get("a", fetch)
    now[0] = 601
    cache.get("a", fetch)
    assert calls == ["a", "a"]
