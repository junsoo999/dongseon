"""AI plan review: start a review or rain plan, list its suggestions, preview, accept or reject them.

Every edit is checked again against the current active version when it is previewed or accepted, so a suggestion
made for an older version stays honest. Accepting saves the checked layout as a new version (origin "ai").
"""

import json
from datetime import date, datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from dongseon.api.deps import HttpDep, ProfileDep, SessionDep, SettingsDep
from dongseon.api.routes import jobs
from dongseon.api.routes.itineraries import ItineraryOut, itinerary_out
from dongseon.api.routes.jobs import JobStatus
from dongseon.api.routes.places import OptionalPlacesDep
from dongseon.api.routes.trips import get_trip_or_404
from dongseon.core.cities import load_city
from dongseon.core.lock import is_locked
from dongseon.db.models import AiSuggestion, Itinerary, Trip
from dongseon.llm.plan_review import EDIT_KIND, REVIEW_KIND
from dongseon.planner.build import edit_of, make_version, prepare
from dongseon.planner.suggest import Checked, EditNotApplicableError, PlanEdit, check_edit

router = APIRouter(tags=["review"])


class ReviewIn(BaseModel):
    """Review the whole version, or plan one date for rain."""

    rain_date: date | None = None
    force: bool = False


class DayTitleOut(BaseModel):
    """An AI title for a date."""

    date: date
    title: str


class PlanReviewOut(BaseModel):
    """Day titles and cautions from one AI run ("AI 제안")."""

    id: int
    source: str  # review | rain
    date: date | None  # the rainy date for rain plans
    itinerary_version: int
    day_titles: list[DayTitleOut]
    notes: list[str]
    created_at: datetime


class PlanEditOut(BaseModel):
    """One AI edit and how it checked out against the version it was made for ("AI 제안")."""

    id: int
    source: str
    date: date | None
    itinerary_version: int
    op: str
    title: str
    reason: str
    applicable: bool
    problems: list[str]
    created_at: datetime


class PlanSuggestionsOut(BaseModel):
    """Pending AI plan suggestions for a trip, newest first."""

    reviews: list[PlanReviewOut]
    edits: list[PlanEditOut]


class PreviewOut(BaseModel):
    """The edit applied to the current version (not saved) and its new problems."""

    itinerary: ItineraryOut
    applicable: bool
    problems: list[str]
    resolved: bool  # the touched days were re-solved


def _active(session: SessionDep, trip_id: int) -> Itinerary:
    it = session.scalar(select(Itinerary).where(Itinerary.trip_id == trip_id, Itinerary.status == "active"))
    if it is None:
        raise HTTPException(status_code=404, detail="일정이 아직 없습니다")
    return it


@router.post("/itineraries/{itinerary_id}/review", response_model=JobStatus, status_code=202)
def start_review(itinerary_id: int, body: ReviewIn, session: SessionDep, settings: SettingsDep) -> JobStatus:
    """Start the AI review (or rain plan) of the active version in the background."""
    it = session.get(Itinerary, itinerary_id)
    if it is None:
        raise HTTPException(status_code=404, detail="일정을 찾을 수 없습니다")
    if it.status != "active":
        raise HTTPException(status_code=409, detail="최신 버전만 검토할 수 있습니다")
    trip = get_trip_or_404(session, it.trip_id)
    if body.rain_date and not trip.start_date <= body.rain_date <= trip.end_date:
        raise HTTPException(status_code=422, detail="여행 기간이 아닌 날짜입니다")
    if is_locked(settings.lock_path, "review"):
        raise HTTPException(status_code=409, detail="AI 검토가 이미 실행 중입니다")
    args = ["review", "--itinerary", str(it.id)]
    if body.rain_date:
        args += ["--rain", body.rain_date.isoformat()]
    if body.force:
        args.append("--force")
    jobs.spawn_cli(args)
    return jobs.job_status("review", session, settings).model_copy(update={"running": True})


@router.get("/trips/{trip_id}/plan-suggestions", response_model=PlanSuggestionsOut)
def list_plan_suggestions(trip_id: int, session: SessionDep) -> PlanSuggestionsOut:
    """Pending AI day titles, notes and edits."""
    get_trip_or_404(session, trip_id)
    rows = session.scalars(
        select(AiSuggestion)
        .where(
            AiSuggestion.trip_id == trip_id,
            AiSuggestion.kind.in_((REVIEW_KIND, EDIT_KIND)),
            AiSuggestion.status == "pending",
        )
        .order_by(AiSuggestion.created_at.desc(), AiSuggestion.id)
    )
    reviews: list[PlanReviewOut] = []
    edits: list[PlanEditOut] = []
    for s in rows:
        d = json.loads(s.payload_json)
        common = {
            "id": s.id,
            "source": d["source"],
            "date": d.get("date"),
            "itinerary_version": d["version"],
            "created_at": s.created_at,
        }
        if s.kind == REVIEW_KIND:
            reviews.append(PlanReviewOut(**common, day_titles=d.get("day_titles") or [], notes=d.get("notes") or []))
        else:
            edits.append(
                PlanEditOut(
                    **common,
                    op=d["edit"]["op"],
                    title=d["title"],
                    reason=d["edit"]["reason"],
                    applicable=d["applicable"],
                    problems=d.get("problems") or [],
                )
            )
    return PlanSuggestionsOut(reviews=reviews, edits=edits)


def _pending(session: SessionDep, suggestion_id: int, kinds: tuple[str, ...]) -> AiSuggestion:
    s = session.get(AiSuggestion, suggestion_id)
    if s is None or s.kind not in kinds:
        raise HTTPException(status_code=404, detail="제안을 찾을 수 없습니다")
    if s.status != "pending":
        raise HTTPException(status_code=409, detail="이미 처리한 제안입니다")
    return s


def _check(
    s: AiSuggestion,
    session: SessionDep,
    settings: SettingsDep,
    profile: ProfileDep,
    http: HttpDep,
    client: OptionalPlacesDep,
) -> tuple[Trip, Itinerary, Checked]:
    trip = get_trip_or_404(session, s.trip_id)
    active = _active(session, trip.id)
    city = load_city(settings.cities_path, trip.city_key)
    ctx = prepare(session, trip=trip, city=city, profile=profile, settings=settings, http=http, client=client)
    edit = PlanEdit.model_validate(json.loads(s.payload_json)["edit"])
    try:
        return trip, active, check_edit(session, ctx, edit_of(active), edit)
    except EditNotApplicableError as e:
        raise HTTPException(status_code=409, detail="지금 일정에는 맞지 않는 제안입니다") from e


@router.get("/plan-suggestions/{suggestion_id}/preview", response_model=PreviewOut)
def preview_plan_suggestion(
    suggestion_id: int,
    session: SessionDep,
    settings: SettingsDep,
    profile: ProfileDep,
    http: HttpDep,
    client: OptionalPlacesDep,
) -> PreviewOut:
    """Apply an edit to the current version without saving it."""
    s = _pending(session, suggestion_id, (EDIT_KIND,))
    trip, _active_it, checked = _check(s, session, settings, profile, http, client)
    return PreviewOut(
        itinerary=itinerary_out(checked.preview, trip, session),
        applicable=not checked.problems,
        problems=checked.problems,
        resolved=checked.resolved,
    )


@router.post("/plan-suggestions/{suggestion_id}/accept", response_model=ItineraryOut, status_code=201)
def accept_plan_suggestion(
    suggestion_id: int,
    session: SessionDep,
    settings: SettingsDep,
    profile: ProfileDep,
    http: HttpDep,
    client: OptionalPlacesDep,
) -> ItineraryOut:
    """Save an applicable edit as a new version (origin "ai"); 409 when it adds problems to the current plan."""
    s = _pending(session, suggestion_id, (EDIT_KIND,))
    trip, _active_it, checked = _check(s, session, settings, profile, http, client)
    if checked.problems:
        raise HTTPException(status_code=409, detail="적용하면 새 문제가 생깁니다: " + " / ".join(checked.problems))
    edit = PlanEdit.model_validate(json.loads(s.payload_json)["edit"])
    if edit.op == "set_dwell" and edit.dwell_min is not None:
        checked.ctx.pins[edit.pin_id].dwell_min = edit.dwell_min
    it = make_version(session, checked.ctx, checked.edit, origin="ai")
    s.status = "accepted"
    session.flush()
    session.refresh(it)
    return itinerary_out(it, trip, session)


@router.post("/plan-suggestions/{suggestion_id}/reject", status_code=204)
def reject_plan_suggestion(suggestion_id: int, session: SessionDep) -> None:
    """Reject an edit (later reviews are told about it) or dismiss a review's titles and notes."""
    _pending(session, suggestion_id, (EDIT_KIND, REVIEW_KIND)).status = "rejected"
