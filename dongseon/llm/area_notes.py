"""AI notes on stay areas (``stay_area_notes``): vibe, pros and cons with sources, per configured area.

Stored as ``ai_suggestions`` rows of kind ``area_note`` (one per area, newest pending row wins); a new run expires
the older ones. Runs with the same input within ``MAX_AGE_DAYS`` are skipped.
"""

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from dongseon.core.cities import CityConfig
from dongseon.core.profile import Profile
from dongseon.db.models import AiSuggestion, Trip
from dongseon.llm.claude_cli import ClaudeCli, LlmError, load_prompt
from dongseon.llm.payloads import area_notes_payload
from dongseon.llm.research import Source, input_hash, items_schema, normalize_name, recently_researched

logger = logging.getLogger(__name__)

PROMPT = "stay_area_notes_v1"
KIND = "area_note"
TIMEOUT_S = 900


class AreaNote(BaseModel):
    """One area's note."""

    area: str = Field(max_length=50)
    summary: str = Field(max_length=300)
    pros: list[str] = Field(default_factory=list, max_length=4)
    cons: list[str] = Field(default_factory=list, max_length=4)
    sources: list[Source] = Field(min_length=1, max_length=3)


@dataclass(frozen=True)
class AreaNotesResult:
    """What a run did."""

    skipped: bool
    stored: int


def run_area_notes(
    session: Session,
    llm: ClaudeCli,
    trip: Trip,
    city: CityConfig,
    profile: Profile,
    *,
    force: bool = False,
) -> AreaNotesResult:
    """Research notes for the city's stay areas and store them.

    Raises:
        LlmError: The call failed or the output was invalid.
    """
    labels = [a.label for a in city.stay_areas]
    if not labels:
        return AreaNotesResult(True, 0)
    payload = area_notes_payload(trip, city, profile)
    digest = input_hash(PROMPT, payload)
    if not force and recently_researched(session, trip.id, KIND, digest):
        return AreaNotesResult(True, 0)
    session.commit()
    result = llm.run(
        "stay_area_notes",
        load_prompt(PROMPT),
        payload,
        items_schema(AreaNote, len(labels)),
        tools=("WebSearch", "WebFetch"),
        timeout=TIMEOUT_S,
    )
    raw = result.data.get("items") if isinstance(result.data, dict) else None
    if not isinstance(raw, list):
        raise LlmError("invalid area notes output")
    known = {normalize_name(x): x for x in labels}
    notes: dict[str, AreaNote] = {}
    for data in raw:
        try:
            note = AreaNote.model_validate(data)
        except ValidationError:
            logger.info("dropped an invalid area note")
            continue
        label = known.get(normalize_name(note.area))
        if label and label not in notes:
            notes[label] = note.model_copy(update={"area": label})
    for old in session.scalars(
        select(AiSuggestion).where(
            AiSuggestion.trip_id == trip.id, AiSuggestion.kind == KIND, AiSuggestion.status == "pending"
        )
    ):
        if old.key in {normalize_name(x) for x in notes}:
            old.status = "expired"
    now = datetime.now(UTC)
    for label, note in notes.items():
        session.add(
            AiSuggestion(
                trip_id=trip.id,
                kind=KIND,
                key=normalize_name(label),
                payload_json=json.dumps(note.model_dump(mode="json"), ensure_ascii=False),
                prompt_version=PROMPT,
                input_hash=digest,
                created_at=now,
            )
        )
    session.flush()
    return AreaNotesResult(False, len(notes))
