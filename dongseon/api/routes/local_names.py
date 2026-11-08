"""AI-researched local names (``local_name`` suggestions): list, apply one or all verified, reject."""

from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from dongseon.api.deps import SessionDep
from dongseon.api.routes.trips import get_trip_or_404
from dongseon.db.models import AiSuggestion, TripPin
from dongseon.llm.local_names import KIND, LocalNameSuggestion
from dongseon.llm.research import Source

router = APIRouter(tags=["local-names"])


class LocalNameOut(BaseModel):
    """A pending local name for a pin ("AI 제안")."""

    id: int
    pin_id: int
    label: str
    name_local: str
    sources: list[Source]
    confidence: str
    verified: bool
    created_at: datetime


class LocalNamesOut(BaseModel):
    """How many pins have a local name, and the pending suggestions."""

    total: int  # pins with a place ID
    filled: int  # of which have a local name
    suggestions: list[LocalNameOut]


class AppliedOut(BaseModel):
    """How many names were applied."""

    applied: int


def _pending(session: Session, trip_id: int) -> list[AiSuggestion]:
    return list(
        session.scalars(
            select(AiSuggestion)
            .where(AiSuggestion.trip_id == trip_id, AiSuggestion.kind == KIND, AiSuggestion.status == "pending")
            .order_by(AiSuggestion.id)
        )
    )


def _get(session: Session, suggestion_id: int) -> AiSuggestion:
    s = session.get(AiSuggestion, suggestion_id)
    if s is None or s.kind != KIND:
        raise HTTPException(status_code=404, detail="현지 이름 제안을 찾을 수 없습니다")
    if s.status != "pending":
        raise HTTPException(status_code=409, detail="이미 처리한 제안입니다")
    return s


def _apply(session: Session, s: AiSuggestion) -> bool:
    """Set the pin's place local name unless the user already typed one; mark the row accepted either way."""
    item = LocalNameSuggestion.model_validate_json(s.payload_json)
    pin = session.get(TripPin, item.pin_id)
    s.status = "accepted"
    if pin is None or pin.place.local_name:
        return False
    pin.place.local_name = item.name_local
    return True


@router.get("/trips/{trip_id}/local-names", response_model=LocalNamesOut)
def local_names(trip_id: int, session: SessionDep) -> LocalNamesOut:
    """Local name coverage and pending AI suggestions (verified first)."""
    trip = get_trip_or_404(session, trip_id)
    pins = {p.id: p for p in trip.pins if p.place.google_place_id}
    out: list[LocalNameOut] = []
    for s in _pending(session, trip_id):
        item = LocalNameSuggestion.model_validate_json(s.payload_json)
        pin = pins.get(item.pin_id)
        if pin is None or pin.place.local_name:
            continue
        out.append(
            LocalNameOut(
                id=s.id,
                label=pin.place.label,
                created_at=s.created_at,
                **item.model_dump(exclude={"pin_id"}),
                pin_id=pin.id,
            )
        )
    out.sort(key=lambda x: (not x.verified, x.id))
    return LocalNamesOut(total=len(pins), filled=sum(1 for p in pins.values() if p.place.local_name), suggestions=out)


@router.post("/local-names/{suggestion_id}/accept", status_code=204)
def accept_local_name(suggestion_id: int, session: SessionDep) -> None:
    """Apply one suggested local name."""
    _apply(session, _get(session, suggestion_id))


@router.post("/local-names/{suggestion_id}/reject", status_code=204)
def reject_local_name(suggestion_id: int, session: SessionDep) -> None:
    """Reject a suggested name; later research will not propose it again."""
    _get(session, suggestion_id).status = "rejected"


@router.post("/trips/{trip_id}/local-names/accept-verified", response_model=AppliedOut)
def accept_verified(trip_id: int, session: SessionDep) -> AppliedOut:
    """Apply every pending name the search confirmed."""
    get_trip_or_404(session, trip_id)
    applied = 0
    for s in _pending(session, trip_id):
        if LocalNameSuggestion.model_validate_json(s.payload_json).verified:
            applied += _apply(session, s)
    session.flush()
    return AppliedOut(applied=applied)
