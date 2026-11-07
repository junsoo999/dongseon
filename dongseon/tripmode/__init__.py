"""Trip mode: the trip-window rules, weather, D-7 hours re-checks and rain plans."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from dongseon.db.models import Trip

Phase = Literal["before", "during", "after"]


@dataclass(frozen=True)
class TripClock:
    """Where today falls relative to a trip, in the trip's own timezone."""

    today: date
    phase: Phase
    days_until: int  # days from today to the first day (0 on the first day, negative after it)


def trip_clock(trip: Trip, now: datetime | None = None) -> TripClock:
    """Return today's date in the trip's zone and the phase of the trip."""
    today = (now or datetime.now(ZoneInfo(trip.timezone))).astimezone(ZoneInfo(trip.timezone)).date()
    phase: Phase = "before" if today < trip.start_date else "after" if today > trip.end_date else "during"
    return TripClock(today, phase, (trip.start_date - today).days)


def in_window(trip: Trip, days_before: int, now: datetime | None = None) -> bool:
    """Whether today is between ``days_before`` days before the start and the last day."""
    today = trip_clock(trip, now).today
    return trip.start_date - timedelta(days=days_before) <= today <= trip.end_date
