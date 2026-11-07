"""AI research of opening hours on holiday dates (``hours_research``), stored as ``hours_overrides`` (ai_research).

Only must/want pins whose trip dates fall in a configured holiday period are researched, in batches, with
``WebSearch``/``WebFetch``. A day is stored only when it says open (with times) or closed, cites a page and is not
low confidence. Precedence keeps user input and Google special hours above these rows (``planner/hours.py``).
"""

import datetime as dt
import logging
import re
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from dongseon.core.cities import CityConfig
from dongseon.db.models import HoursOverride, Trip, TripPin
from dongseon.llm.claude_cli import ClaudeCli, LlmError, load_prompt
from dongseon.llm.payloads import hours_research_payload
from dongseon.llm.research import Source, items_schema

logger = logging.getLogger(__name__)

PROMPT = "hours_research_v1"
TIMEOUT_S = 900
BATCH = 6  # pins per call
FRESH_DAYS = 7  # a pin with rows for every holiday date checked this recently is skipped
PRIORITIES = ("must", "want")
_HHMM = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


class HoursDay(BaseModel):
    """One date's finding for one place."""

    date: dt.date
    status: Literal["open", "closed", "unknown"]
    open: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    close: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    source_url: str | None = Field(default=None, pattern=r"^https?://", max_length=2000)
    confidence: Literal["high", "medium", "low"] = "medium"


class HoursItem(BaseModel):
    """Findings for one pin."""

    pin_id: int
    place_name: str = Field(max_length=100)  # the place the model believes the label means
    days: list[HoursDay] = Field(max_length=14)
    sources: list[Source] = Field(min_length=1, max_length=3)


SCHEMA = items_schema(HoursItem, BATCH)


@dataclass(frozen=True)
class HoursResearchResult:
    """What a run did."""

    pins: int  # pins researched
    stored: int  # dates stored
    skipped: int  # pins skipped as fresh


def holiday_dates(trip: Trip, city: CityConfig) -> list[dt.date]:
    """Trip dates inside a configured holiday period."""
    days = (trip.end_date - trip.start_date).days + 1
    return [d for d in (trip.start_date + dt.timedelta(days=i) for i in range(days)) if city.holidays_on(d)]


def _minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def targets(session: Session, trip: Trip, city: CityConfig, *, force: bool) -> tuple[list[TripPin], int]:
    """Pins to research and how many were skipped as fresh."""
    dates = holiday_dates(trip, city)
    if not dates:
        return [], 0
    pins = [p for p in trip.pins if p.priority in PRIORITIES]
    if force:
        return pins, 0
    since = dt.datetime.now(dt.UTC) - dt.timedelta(days=FRESH_DAYS)
    out: list[TripPin] = []
    for p in pins:
        fresh = set(
            session.scalars(
                select(HoursOverride.day).where(
                    HoursOverride.place_id == p.place_id,
                    HoursOverride.source == "ai_research",
                    HoursOverride.checked_at >= since,
                    HoursOverride.day.in_(dates),
                )
            )
        )
        if not set(dates) <= fresh:
            out.append(p)
    return out, len(pins) - len(out)


def _store(session: Session, pins: dict[int, TripPin], items: list[HoursItem], dates: set[dt.date]) -> int:
    stored = 0
    now = dt.datetime.now(dt.UTC)
    for item in items:
        pin = pins.get(item.pin_id)
        if pin is None:
            continue
        for d in item.days:
            if d.date not in dates or d.status == "unknown" or d.confidence == "low" or not d.source_url:
                continue
            open_min = close_min = None
            if d.status == "open":
                if d.open is None or d.close is None:
                    continue
                open_min, close_min = _minutes(d.open), _minutes(d.close)
                if close_min <= open_min:
                    close_min += 24 * 60
            row = session.scalar(
                select(HoursOverride).where(
                    HoursOverride.place_id == pin.place_id,
                    HoursOverride.day == d.date,
                    HoursOverride.source == "ai_research",
                )
            )
            if row is None:
                row = HoursOverride(place_id=pin.place_id, day=d.date, source="ai_research", status=d.status)
                session.add(row)
            row.status, row.open_min, row.close_min = d.status, open_min, close_min
            row.source_url, row.checked_at = d.source_url, now
            stored += 1
    session.flush()
    return stored


def run_hours_research(
    session: Session, llm: ClaudeCli, trip: Trip, city: CityConfig, *, force: bool = False
) -> HoursResearchResult:
    """Research holiday-date hours for the trip's must/want pins and store what is cited.

    Raises:
        LlmError: A call failed (rows from earlier batches stay stored).
    """
    pins, skipped = targets(session, trip, city, force=force)
    dates = holiday_dates(trip, city)
    by_id = {p.id: p for p in pins}
    stored = 0
    for i in range(0, len(pins), BATCH):
        batch = pins[i : i + BATCH]
        payload = hours_research_payload(trip, city, pins=batch, dates=dates)
        session.commit()  # release SQLite's write lock while the call runs
        result = llm.run(
            "hours_research", load_prompt(PROMPT), payload, SCHEMA, tools=("WebSearch", "WebFetch"), timeout=TIMEOUT_S
        )
        raw = result.data.get("items") if isinstance(result.data, dict) else None
        if not isinstance(raw, list):
            raise LlmError("invalid hours research output")
        items: list[HoursItem] = []
        for data in raw:
            try:
                items.append(HoursItem.model_validate(data))
            except ValidationError:
                logger.info("dropped an invalid hours item")
        stored += _store(session, by_id, items, set(dates))
        session.commit()
    return HoursResearchResult(len(pins), stored, skipped)
