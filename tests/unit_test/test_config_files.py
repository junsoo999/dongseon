from datetime import date, time
from pathlib import Path

import pytest

from dongseon.core.cities import CityNotFoundError, HolidayPeriod, list_cities, load_city
from dongseon.core.defaults import load_defaults
from dongseon.core.profile import load_profile

from .conftest import CITIES, DEFAULTS, EXAMPLE_PROFILE


def test_example_profile_parses() -> None:
    p = load_profile(EXAMPLE_PROFILE)
    assert p.pace == "normal"
    assert (p.day_window.start, p.day_window.end) == (time(9), time(21))
    assert p.meal_windows["lunch"].start == time(11, 30)
    assert p.priority_weights["must"] > p.priority_weights["want"] > p.priority_weights["maybe"]
    assert p.buffers_min.arrival_immigration == 60


def test_unquoted_yaml_times_are_accepted(tmp_path: Path) -> None:
    text = EXAMPLE_PROFILE.read_text(encoding="utf-8").replace('["09:00", "21:00"]', "[09:00, 21:00]")
    path = tmp_path / "p.yaml"
    path.write_text(text, encoding="utf-8")
    assert load_profile(path).day_window.end == time(21)


def test_tokyo_config_parses() -> None:
    tokyo = load_city(CITIES, "tokyo")
    assert tokyo.timezone == "Asia/Tokyo"
    assert tokyo.currency == "JPY"
    assert {a.code for a in tokyo.airports} == {"HND", "NRT"}
    assert [c.key for c in list_cities(CITIES)] == ["tokyo"]


def test_missing_city_raises() -> None:
    with pytest.raises(CityNotFoundError):
        load_city(CITIES, "atlantis")


def test_holiday_period_wraps_year_end() -> None:
    period = HolidayPeriod(
        key="year_end", start="12-29", end="01-04", note="", source_url="https://example.com", as_of=date(2026, 11, 4)
    )
    assert period.contains(date(2026, 12, 31))
    assert period.contains(date(2027, 1, 4))
    assert not period.contains(date(2027, 1, 5))
    assert not period.contains(date(2026, 12, 28))


def test_holiday_period_rejects_bad_dates() -> None:
    with pytest.raises(ValueError):
        HolidayPeriod(key="x", start="13-01", end="01-04", note="", source_url="u", as_of=date(2026, 1, 1))


def test_every_category_has_a_dwell_time() -> None:
    cats = load_defaults(DEFAULTS).categories
    assert set(cats.mapping.values()) | {cats.fallback} <= set(cats.dwell_min)
