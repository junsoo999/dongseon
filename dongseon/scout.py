"""Run AI scouting for a trip: place and stay research with inputs from the app's own data."""

import json
import logging
from dataclasses import dataclass

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from dongseon.api.routes.stays import build_score
from dongseon.core.cities import CityConfig
from dongseon.core.config import Settings
from dongseon.core.profile import Profile
from dongseon.db.models import AiSuggestion, Stay, Trip
from dongseon.llm.claude_cli import ClaudeCli
from dongseon.llm.payloads import places_research_payload, stay_research_payload
from dongseon.llm.research import ScoutResult, normalize_name, run_research
from dongseon.sources.google_places import GooglePlacesClient

logger = logging.getLogger(__name__)

PLACE_WANT = {"food": 8, "other": 6}
TOP_AREAS = 3


@dataclass(frozen=True)
class ScoutSummary:
    """Results per research kind."""

    results: list[ScoutResult]


def _rejected_names(session: Session, trip_id: int, kind: str) -> list[str]:
    rows = session.scalars(
        select(AiSuggestion).where(
            AiSuggestion.trip_id == trip_id, AiSuggestion.kind == kind, AiSuggestion.status == "rejected"
        )
    ).all()
    return [json.loads(r.payload_json).get("name", "") for r in rows][:50]


def scout_trip(
    session: Session,
    *,
    trip: Trip,
    city: CityConfig,
    profile: Profile,
    settings: Settings,
    llm: ClaudeCli,
    client: GooglePlacesClient,
    http: httpx.Client,
    kinds: tuple[str, ...] = ("place", "stay"),
    force: bool = False,
) -> ScoutSummary:
    """Research new places and stays for one trip and store them as pending suggestions."""
    results: list[ScoutResult] = []
    labels = [p.place.label for p in trip.pins]
    area_labels = [a.label for a in city.stay_areas]
    if "place" in kinds:
        payload = places_research_payload(
            trip,
            city,
            profile,
            existing_labels=labels,
            rejected=_rejected_names(session, trip.id, "place"),
            areas=area_labels,
            want=PLACE_WANT,
        )
        results.append(
            run_research(
                session,
                llm,
                client,
                city,
                trip_id=trip.id,
                kind="place",
                payload=payload,
                blocked_keys={normalize_name(x) for x in labels},
                force=force,
            )
        )
    if "stay" in kinds:
        score = build_score(trip, session, settings, profile, http, client)
        ranked = [o for o in score.origins if o.kind == "area" and o.rank is not None][:TOP_AREAS]
        if not ranked:  # no must/want pins yet: fall back to the configured areas in order
            ranked_areas = [{"label": a, "rank": None, "avg_min": None} for a in area_labels[:TOP_AREAS]]
        else:
            ranked_areas = [{"label": o.label, "rank": o.rank, "avg_min": o.weighted_avg_min} for o in ranked]
        stay_labels = list(session.scalars(select(Stay.label).where(Stay.trip_id == trip.id)))
        payload = stay_research_payload(
            trip, city, profile, areas=ranked_areas, rejected=_rejected_names(session, trip.id, "stay")
        )
        results.append(
            run_research(
                session,
                llm,
                client,
                city,
                trip_id=trip.id,
                kind="stay",
                payload=payload,
                blocked_keys={normalize_name(x) for x in stay_labels},
                force=force,
            )
        )
    return ScoutSummary(results)
