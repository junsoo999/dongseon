"""AI research results: holiday opening hours, stay-area notes, and reading a pasted booking email."""

import json
from datetime import date, datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from dongseon.api.deps import LlmDep, SessionDep, SettingsDep
from dongseon.api.routes.trips import get_trip_or_404
from dongseon.core.cities import load_city
from dongseon.db.models import AiSuggestion, HoursOverride
from dongseon.llm.area_notes import KIND as AREA_KIND
from dongseon.llm.area_notes import AreaNote
from dongseon.llm.booking import MAX_CHARS, FlightDraft, StayDraft, parse_booking
from dongseon.llm.claude_cli import LlmError, TokenLimitError
from dongseon.llm.hours_research import PRIORITIES, holiday_dates
from dongseon.llm.research import Source

router = APIRouter(tags=["research"])


class ResearchedDay(BaseModel):
    """One date's AI-researched hours ("AI 조사, 출처, 확인 필요")."""

    date: date
    status: str  # open | closed
    open: str | None
    close: str | None
    source_url: str | None
    checked_at: datetime


class ResearchedPlace(BaseModel):
    """A must/want pin with dates in a holiday period."""

    pin_id: int
    label: str
    priority: str
    days: list[ResearchedDay]


class HoursResearchOut(BaseModel):
    """Holiday dates of the trip and what research found for each target pin."""

    dates: list[date]
    holiday_note: str | None
    places: list[ResearchedPlace]


def _hhmm(m: int | None) -> str | None:
    return None if m is None else f"{(m // 60) % 24:02d}:{m % 60:02d}"


@router.get("/trips/{trip_id}/hours-research", response_model=HoursResearchOut)
def hours_research(trip_id: int, session: SessionDep, settings: SettingsDep) -> HoursResearchOut:
    """Holiday dates and the stored AI research rows for the trip's must/want pins."""
    trip = get_trip_or_404(session, trip_id)
    city = load_city(settings.cities_path, trip.city_key)
    dates = holiday_dates(trip, city)
    periods = city.holidays_on(dates[0]) if dates else []
    places: list[ResearchedPlace] = []
    for p in sorted(trip.pins, key=lambda x: (x.priority != "must", x.id)):
        if p.priority not in PRIORITIES or not dates:
            continue
        rows = session.scalars(
            select(HoursOverride)
            .where(
                HoursOverride.place_id == p.place_id,
                HoursOverride.source == "ai_research",
                HoursOverride.day.in_(dates),
            )
            .order_by(HoursOverride.day)
        )
        places.append(
            ResearchedPlace(
                pin_id=p.id,
                label=p.place.label,
                priority=p.priority,
                days=[
                    ResearchedDay(
                        date=r.day,
                        status=r.status,
                        open=_hhmm(r.open_min),
                        close=_hhmm(r.close_min),
                        source_url=r.source_url,
                        checked_at=r.checked_at,
                    )
                    for r in rows
                ],
            )
        )
    return HoursResearchOut(
        dates=dates, holiday_note=periods[0].note.split(".")[0] if periods else None, places=places
    )


class AreaNoteOut(BaseModel):
    """An AI note on a stay area ("AI 제안")."""

    id: int
    area: str
    summary: str
    pros: list[str]
    cons: list[str]
    sources: list[Source]
    created_at: datetime


@router.get("/trips/{trip_id}/area-notes", response_model=list[AreaNoteOut])
def area_notes(trip_id: int, session: SessionDep) -> list[AreaNoteOut]:
    """The latest AI note per stay area."""
    get_trip_or_404(session, trip_id)
    rows = session.scalars(
        select(AiSuggestion)
        .where(AiSuggestion.trip_id == trip_id, AiSuggestion.kind == AREA_KIND, AiSuggestion.status == "pending")
        .order_by(AiSuggestion.created_at.desc())
    )
    out: dict[str, AreaNoteOut] = {}
    for r in rows:
        note = AreaNote.model_validate(json.loads(r.payload_json))
        if note.area not in out:
            out[note.area] = AreaNoteOut(id=r.id, created_at=r.created_at, **note.model_dump())
    return list(out.values())


class BookingIn(BaseModel):
    """A pasted booking confirmation (never stored)."""

    text: str = Field(min_length=20, max_length=MAX_CHARS)


class BookingOut(BaseModel):
    """A draft to confirm in the flight or stay form ("AI 제안")."""

    kind: str  # flight | stay | none
    flight: FlightDraft | None
    stay: StayDraft | None
    note: str | None
    masked: dict[str, int]  # what was hidden before the text reached the model


@router.post("/trips/{trip_id}/parse-booking", response_model=BookingOut)
def parse_booking_mail(trip_id: int, body: BookingIn, session: SessionDep, llm: LlmDep) -> BookingOut:
    """Mask the pasted text, read it with Claude (no tools) and return a draft; nothing is saved."""
    trip = get_trip_or_404(session, trip_id)
    start, end = trip.start_date, trip.end_date
    session.commit()  # release SQLite's write lock: the call records its usage on another connection
    try:
        parsed = parse_booking(llm, body.text, trip_start=start, trip_end=end)
    except TokenLimitError as e:
        raise HTTPException(status_code=429, detail="오늘 AI 사용 한도에 도달했습니다") from e
    except LlmError as e:
        raise HTTPException(status_code=502, detail="AI가 메일을 읽지 못했습니다. 잠시 뒤 다시 시도하세요") from e
    a = parsed.answer
    return BookingOut(kind=a.kind, flight=a.flight, stay=a.stay, note=a.note, masked=parsed.masked)
