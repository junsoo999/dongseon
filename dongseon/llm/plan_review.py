"""AI plan review and rain plans: ask for edits, check each one against the plan, store them as suggestions.

The model gets the plan as app data only (``dongseon.llm.payloads``) and answers with edits; the app applies every
edit, times it and compares warnings with the current version (``dongseon.planner.suggest``). Suggestions are
``ai_suggestions`` rows: one ``plan_review`` row (day titles and notes) and one ``plan_edit`` row per edit.
"""

import datetime as dt
import json
import logging
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from dongseon.core.profile import Profile
from dongseon.db.models import AiSuggestion, Itinerary
from dongseon.llm.claude_cli import ClaudeCli, LlmError, load_prompt
from dongseon.llm.payloads import plan_review_payload, rain_plan_payload
from dongseon.llm.research import input_hash
from dongseon.planner.build import PlanContext, edit_of
from dongseon.planner.suggest import EditNotApplicableError, PlanEdit, check_edit, describe

logger = logging.getLogger(__name__)

REVIEW_PROMPT = "plan_review_v1"
RAIN_PROMPT = "rain_plan_v1"
REVIEW_KIND = "plan_review"
EDIT_KIND = "plan_edit"
MAX_EDITS = 8

Source = Literal["review", "rain"]


class DayTitle(BaseModel):
    """A short AI title for one date."""

    date: dt.date
    title: str = Field(max_length=40)


class ReviewAnswer(BaseModel):
    """The model's answer (validated item by item: one bad edit does not drop the others)."""

    day_titles: list[DayTitle] = Field(default_factory=list, max_length=12)
    notes: list[str] = Field(default_factory=list, max_length=6)
    edits: list[PlanEdit] = Field(default_factory=list, max_length=MAX_EDITS)


def _schema() -> dict:
    return ReviewAnswer.model_json_schema()


@dataclass(frozen=True)
class ReviewResult:
    """What a run stored."""

    skipped: bool
    proposed: int
    stored: int
    applicable: int


def _parse(raw: object) -> ReviewAnswer:
    if not isinstance(raw, dict):
        raise LlmError("invalid review output")
    titles: list[DayTitle] = []
    for t in raw.get("day_titles") or []:
        try:
            titles.append(DayTitle.model_validate(t))
        except ValidationError:
            logger.info("dropped an invalid day title")
    edits: list[PlanEdit] = []
    for e in (raw.get("edits") or [])[:MAX_EDITS]:
        try:
            edits.append(PlanEdit.model_validate(e))
        except ValidationError:
            logger.info("dropped an invalid edit")
    notes = [str(n)[:200] for n in (raw.get("notes") or [])[:6] if str(n).strip()]
    return ReviewAnswer(day_titles=titles[:12], notes=notes, edits=edits)


def _same_scope(s: AiSuggestion, source: Source, rain_date: dt.date | None) -> bool:
    data = json.loads(s.payload_json)
    return data.get("source") == source and data.get("date") == (rain_date.isoformat() if rain_date else None)


def _rejected_titles(session: Session, trip_id: int, source: Source) -> list[str]:
    rows = session.scalars(
        select(AiSuggestion)
        .where(AiSuggestion.trip_id == trip_id, AiSuggestion.kind == EDIT_KIND, AiSuggestion.status == "rejected")
        .order_by(AiSuggestion.created_at.desc())
        .limit(30)
    )
    return [d["title"] for d in (json.loads(r.payload_json) for r in rows) if d.get("source") == source]


def run_review(
    session: Session,
    llm: ClaudeCli,
    ctx: PlanContext,
    itinerary: Itinerary,
    profile: Profile,
    *,
    indoor: set[str],
    rain_date: dt.date | None = None,
    force: bool = False,
) -> ReviewResult:
    """Review a version (or plan one rainy day), check each edit and store pending suggestions.

    Older pending suggestions of the same kind (review, or rain for the same date) expire.

    Args:
        session: DB session; the caller commits.
        llm: Claude Code caller.
        ctx: The trip's prepared plan context.
        itinerary: The version to review (normally the active one).
        profile: Household preferences.
        indoor: Categories treated as indoor.
        rain_date: Plan this date for rain instead of reviewing the whole trip.
        force: Ask again even when the same input already has pending suggestions.

    Raises:
        LlmError: The call failed or the output was invalid.
    """
    trip = ctx.trip
    source: Source = "rain" if rain_date else "review"
    if rain_date and rain_date not in ctx.dates:
        raise ValueError("rain date is outside the trip")
    rejected = _rejected_titles(session, trip.id, source)
    if rain_date:
        version = RAIN_PROMPT
        payload = rain_plan_payload(
            trip,
            ctx.city,
            profile,
            itinerary=itinerary,
            pins=ctx.pins,
            indoor=indoor,
            rain_date=rain_date,
            rejected=rejected,
        )
    else:
        version = REVIEW_PROMPT
        payload = plan_review_payload(
            trip, ctx.city, profile, itinerary=itinerary, pins=ctx.pins, indoor=indoor, rejected=rejected
        )
    digest = input_hash(version, payload)
    pending = [
        s
        for s in session.scalars(
            select(AiSuggestion).where(
                AiSuggestion.trip_id == trip.id,
                AiSuggestion.kind.in_((REVIEW_KIND, EDIT_KIND)),
                AiSuggestion.status == "pending",
            )
        )
        if _same_scope(s, source, rain_date)
    ]
    if not force and any(s.input_hash == digest for s in pending):
        return ReviewResult(True, 0, 0, 0)
    # Release SQLite's write lock: the call records its usage in llm_runs on another connection.
    session.commit()
    result = llm.run(REVIEW_KIND if not rain_date else "rain_plan", load_prompt(version), payload, _schema())
    answer = _parse(result.data)

    now = dt.datetime.now(dt.UTC)
    for s in pending:
        s.status = "expired"
    scope = {
        "itinerary_id": itinerary.id,
        "version": itinerary.version,
        "source": source,
        "date": rain_date.isoformat() if rain_date else None,
    }
    titles = [t for t in answer.day_titles if t.date in ctx.dates and (not rain_date or t.date == rain_date)]
    session.add(
        AiSuggestion(
            trip_id=trip.id,
            kind=REVIEW_KIND,
            key=f"{source}:{scope['date'] or ''}:{itinerary.id}",
            payload_json=json.dumps(
                {
                    **scope,
                    "day_titles": [{"date": t.date.isoformat(), "title": t.title} for t in titles],
                    "notes": answer.notes,
                },
                ensure_ascii=False,
            ),
            prompt_version=version,
            input_hash=digest,
            created_at=now,
        )
    )
    base = edit_of(itinerary)
    labels = {p.id: p.place.label for p in ctx.pins.values()}
    stored = applicable = 0
    seen: set[str] = set()
    for e in answer.edits:
        key = f"{e.op}:{e.pin_id}:{e.other_pin_id}:{e.date}:{e.after_pin_id}:{e.dwell_min}"
        if key in seen:
            continue
        seen.add(key)
        if e.pin_id in base.locked or e.other_pin_id in base.locked:
            logger.info("dropped an edit that touches a locked visit")
            continue
        if rain_date and not _touches(e, base.layout, rain_date):
            logger.info("dropped a rain edit that does not change the rainy day")
            continue
        try:
            checked = check_edit(session, ctx, base, e)
        except EditNotApplicableError as err:
            logger.info("dropped an edit: %s", err)
            continue
        stored += 1
        applicable += not checked.problems
        session.add(
            AiSuggestion(
                trip_id=trip.id,
                kind=EDIT_KIND,
                key=key,
                payload_json=json.dumps(
                    {
                        **scope,
                        "edit": e.model_dump(mode="json"),
                        "title": describe(e, labels, ctx.dates),
                        "applicable": not checked.problems,
                        "problems": checked.problems,
                        "resolved": checked.resolved,
                    },
                    ensure_ascii=False,
                ),
                prompt_version=version,
                input_hash=digest,
                created_at=now,
            )
        )
    session.flush()
    return ReviewResult(False, len(answer.edits), stored, applicable)


def _touches(e: PlanEdit, layout: dict[dt.date, list[int]], day: dt.date) -> bool:
    on_day = set(layout.get(day, []))
    return e.date == day or e.pin_id in on_day or (e.other_pin_id is not None and e.other_pin_id in on_day)
