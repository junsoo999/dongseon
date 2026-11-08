"""Opening hours per place and date.

Precedence: user input > Google special hours (currentOpeningHours, next 7 days) > AI research > Google weekly hours
> unknown. Google hours are used within the request and kept in process memory for at most ``CACHE_TTL_S``; they are
never written to the database (docs/google-terms.md). Minutes count from local midnight; a close after midnight is
above 1440.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from typing import Literal

Window = tuple[int, int]
Status = Literal["open", "closed", "unknown"]
Source = Literal["user", "google_special", "ai_research", "google_regular", "none"]

CACHE_TTL_S = 600
DAY_MIN = 24 * 60


@dataclass(frozen=True)
class GoogleHours:
    """Parsed Google opening hours: weekly windows by Google weekday (0 = Sunday) and dated special windows."""

    weekly: dict[int, list[Window]]
    dated: dict[date, list[Window]]
    has_weekly: bool


@dataclass(frozen=True)
class OverrideRow:
    """A stored user or AI-research entry for one date."""

    source: Literal["user", "ai_research"]
    status: str
    open_min: int | None
    close_min: int | None
    source_url: str | None = None


@dataclass(frozen=True)
class DayHours:
    """Hours of one place on one date, with where they came from."""

    status: Status
    windows: list[Window] = field(default_factory=list)
    source: Source = "none"
    source_url: str | None = None
    holiday_unconfirmed: bool = False


def _minutes(point: dict) -> int:
    return int(point.get("hour", 0)) * 60 + int(point.get("minute", 0))


def _window(open_: dict, close: dict | None) -> tuple[int, Window]:
    """Return (google weekday, window). A missing close means open 24 hours from the open time."""
    day = int(open_.get("day", 0))
    start = _minutes(open_)
    if close is None:
        return day, (start, start + DAY_MIN)
    span = (int(close.get("day", day)) - day) % 7
    end = _minutes(close) + span * DAY_MIN
    if end <= start:
        end += DAY_MIN
    return day, (start, end)


def parse_google_hours(data: dict) -> GoogleHours:
    """Parse a Place Details response with ``regularOpeningHours`` and ``currentOpeningHours``."""
    weekly: dict[int, list[Window]] = {}
    regular = (data.get("regularOpeningHours") or {}).get("periods") or []
    for p in regular:
        if "open" not in p:
            continue
        day, w = _window(p["open"], p.get("close"))
        weekly.setdefault(day, []).append(w)
    if len(regular) == 1 and "close" not in regular[0]:  # "open 24 hours" is one period without a close
        weekly = {d: [(0, DAY_MIN)] for d in range(7)}
    dated: dict[date, list[Window]] = {}
    for p in (data.get("currentOpeningHours") or {}).get("periods") or []:
        o = p.get("open") or {}
        d = o.get("date")
        if not d:
            continue
        _day, w = _window(o, p.get("close"))
        dated.setdefault(date(d["year"], d["month"], d["day"]), []).append(w)
    return GoogleHours(weekly={k: sorted(v) for k, v in weekly.items()}, dated=dated, has_weekly=bool(regular))


def google_weekday(d: date) -> int:
    """Google's weekday numbering (0 = Sunday)."""
    return (d.weekday() + 1) % 7


def hours_on(
    d: date,
    google: GoogleHours | None,
    overrides: list[OverrideRow],
    *,
    in_holiday: bool,
    special_horizon: date | None = None,
) -> DayHours:
    """Resolve one date's hours by precedence.

    Args:
        d: Local date.
        google: Parsed Google hours, or ``None`` when unavailable.
        overrides: Stored user and AI-research rows for this date.
        in_holiday: Whether ``d`` falls in a configured holiday period.
        special_horizon: Last date covered by ``currentOpeningHours`` (today + 6); dates after it cannot have specials.
    """

    def from_row(row: OverrideRow) -> DayHours:
        if row.status == "closed":
            return DayHours("closed", [], row.source, row.source_url)
        if row.open_min is not None and row.close_min is not None:
            return DayHours("open", [(row.open_min, row.close_min)], row.source, row.source_url)
        return DayHours("unknown", [], row.source, row.source_url, holiday_unconfirmed=in_holiday)

    user = next((r for r in overrides if r.source == "user"), None)
    if user:
        return from_row(user)
    if google and (special_horizon is None or d <= special_horizon) and d in google.dated:
        return DayHours("open", google.dated[d], "google_special")
    ai = next((r for r in overrides if r.source == "ai_research"), None)
    if ai:
        return from_row(ai)
    if google and google.has_weekly:
        windows = google.weekly.get(google_weekday(d), [])
        status: Status = "open" if windows else "closed"
        return DayHours(status, windows, "google_regular", holiday_unconfirmed=in_holiday)
    return DayHours("unknown", [], "none", holiday_unconfirmed=in_holiday)


class HoursCache:
    """Process-memory cache of parsed Google hours for at most ``CACHE_TTL_S`` (never persisted)."""

    def __init__(self, ttl_s: float = CACHE_TTL_S, clock: Callable[[], float] = time.monotonic) -> None:
        """Create an empty cache."""
        self._ttl = ttl_s
        self._clock = clock
        self._rows: dict[str, tuple[float, GoogleHours]] = {}

    def peek(self, place_id: str) -> GoogleHours | None:
        """Return cached hours without fetching, or ``None`` when absent or expired."""
        hit = self._rows.get(place_id)
        if hit and self._clock() - hit[0] < self._ttl:
            return hit[1]
        return None

    def get(self, place_id: str, fetch: Callable[[str], dict]) -> GoogleHours:
        """Return cached hours or fetch and parse them."""
        now = self._clock()
        hit = self._rows.get(place_id)
        if hit and now - hit[0] < self._ttl:
            return hit[1]
        for key in [k for k, (t, _) in self._rows.items() if now - t >= self._ttl]:
            del self._rows[key]
        parsed = parse_google_hours(fetch(place_id))
        self._rows[place_id] = (now, parsed)
        return parsed


HOURS_CACHE = HoursCache()
