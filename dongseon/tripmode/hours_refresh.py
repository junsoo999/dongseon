"""Re-check the active plan against today's opening hours (D-7 on) and leave an alert when warnings change.

Google special hours only reach seven days ahead, so a plan made earlier was checked against regular hours. This
re-times the active version as it is with fresh hours (nothing is re-solved or saved as a version) and compares the
problems. Only the app's own warning text is stored (``trip_alerts``); the hours themselves never are.
"""

import json
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from dongseon.db.models import Itinerary, TripAlert
from dongseon.planner.build import PlanContext, edit_of, make_version
from dongseon.planner.suggest import problems

KIND = "hours_changed"


@dataclass(frozen=True)
class HoursRefresh:
    """What changed versus the saved version."""

    added: list[str]  # new problems with today's hours
    resolved: list[str]  # saved problems that are gone with today's hours
    alert_id: int | None


def refresh_hours(session: Session, ctx: PlanContext, active: Itinerary) -> HoursRefresh:
    """Compare the saved version with the same layout timed today and replace the trip's open hours alert.

    Args:
        session: DB session; the caller commits.
        ctx: The trip's context prepared now (fresh Google hours for must/want pins).
        active: The trip's active version.
    """
    retimed = make_version(session, ctx, edit_of(active), persist=False)
    added = problems(active, retimed, ctx)
    resolved = [p for p in problems(retimed, active, ctx) if not p.endswith("일정에서 빠집니다")]
    payload = json.dumps({"added": added, "resolved": resolved}, ensure_ascii=False)
    last = session.scalar(
        select(TripAlert)
        .where(TripAlert.trip_id == ctx.trip.id, TripAlert.kind == KIND)
        .order_by(TripAlert.id.desc())
        .limit(1)
    )
    if last and last.itinerary_id == active.id and last.payload_json == payload and (added or resolved):
        return HoursRefresh(added, resolved, last.id)  # same finding as before: keep it (and a dismissal) as is
    for old in session.scalars(
        select(TripAlert).where(TripAlert.trip_id == ctx.trip.id, TripAlert.kind == KIND, TripAlert.status == "new")
    ):
        old.status = "dismissed"
    alert_id = None
    if added or resolved:
        alert = TripAlert(
            trip_id=ctx.trip.id,
            kind=KIND,
            itinerary_id=active.id,
            payload_json=payload,
            created_at=datetime.now(UTC),
        )
        session.add(alert)
        session.flush()
        alert_id = alert.id
    return HoursRefresh(added, resolved, alert_id)
