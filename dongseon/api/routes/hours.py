"""Opening hours the user enters for one place on one date (highest precedence; Google hours are never stored)."""

import re
from datetime import UTC, date, datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, field_validator
from sqlalchemy import select

from dongseon.api.deps import SessionDep
from dongseon.api.routes.places import _get_pin
from dongseon.db.models import HoursOverride

router = APIRouter(tags=["hours"])

_HHMM = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


class HoursIn(BaseModel):
    """Open with a time range, or closed. A close at or before the open time means after midnight."""

    status: Literal["open", "closed"]
    open: str | None = None  # HH:MM local
    close: str | None = None

    @field_validator("open", "close")
    @classmethod
    def _hhmm(cls, v: str | None) -> str | None:
        if v is not None and not _HHMM.match(v):
            raise ValueError("HH:MM 형식이어야 합니다")
        return v


class HoursOut(BaseModel):
    """A stored user entry."""

    pin_id: int
    day: date
    status: str
    open_min: int | None
    close_min: int | None
    source: str


def _min(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


@router.put("/trips/{trip_id}/pins/{pin_id}/hours/{day}", response_model=HoursOut)
def set_hours(trip_id: int, pin_id: int, day: date, body: HoursIn, session: SessionDep) -> HoursOut:
    """Set the user's hours for a pin's place on a date (replaces an earlier user entry)."""
    pin = _get_pin(session, trip_id, pin_id)
    open_min = close_min = None
    if body.status == "open":
        if body.open is None or body.close is None:
            raise HTTPException(status_code=422, detail="여는 시각과 닫는 시각을 모두 입력하세요")
        open_min, close_min = _min(body.open), _min(body.close)
        if close_min <= open_min:
            close_min += 24 * 60
    row = session.scalar(
        select(HoursOverride).where(
            HoursOverride.place_id == pin.place_id, HoursOverride.day == day, HoursOverride.source == "user"
        )
    )
    if row is None:
        row = HoursOverride(place_id=pin.place_id, day=day, source="user", status=body.status)
        session.add(row)
    row.status, row.open_min, row.close_min = body.status, open_min, close_min
    row.source_url, row.checked_at = None, datetime.now(UTC)
    session.flush()
    return HoursOut(
        pin_id=pin.id, day=day, status=row.status, open_min=open_min, close_min=close_min, source=row.source
    )


@router.delete("/trips/{trip_id}/pins/{pin_id}/hours/{day}", status_code=204)
def clear_hours(trip_id: int, pin_id: int, day: date, session: SessionDep) -> Response:
    """Remove the user's entry so the next source (Google, AI research) applies again."""
    pin = _get_pin(session, trip_id, pin_id)
    row = session.scalar(
        select(HoursOverride).where(
            HoursOverride.place_id == pin.place_id, HoursOverride.day == day, HoursOverride.source == "user"
        )
    )
    if row is not None:
        session.delete(row)
    return Response(status_code=204)
