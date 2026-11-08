"""AI research of local-language place names (``local_names``) so exports can be geocoded by name.

Pins whose place has no ``local_name`` yet are researched in batches from the user's label, category and note only.
Each name is checked with the free IDs Only search: when the place's own ID comes back for the name, the
suggestion is "verified". Results are ``ai_suggestions`` rows of kind ``local_name`` (key = place id) that the user
applies or rejects; rejected names are sent back so they are not proposed again.
"""

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from dongseon.core.cities import CityConfig
from dongseon.db.models import AiSuggestion, Trip, TripPin
from dongseon.llm.claude_cli import ClaudeCli, LlmError, load_prompt
from dongseon.llm.payloads import local_names_payload
from dongseon.llm.research import CITY_RADIUS_M, Source, input_hash, items_schema, normalize_name, recently_researched
from dongseon.sources.google_places import GooglePlacesClient, LatLng

logger = logging.getLogger(__name__)

PROMPT = "local_names_v1"
KIND = "local_name"
TIMEOUT_S = 900
BATCH = 10  # pins per call


class LocalNameItem(BaseModel):
    """One researched name."""

    pin_id: int
    name_local: str = Field(min_length=1, max_length=100)
    sources: list[Source] = Field(min_length=1, max_length=3)
    confidence: Literal["high", "medium", "low"] = "medium"


class LocalNameSuggestion(LocalNameItem):
    """What a ``local_name`` suggestion row stores."""

    verified: bool  # the IDs Only search for the name returned this place


SCHEMA = items_schema(LocalNameItem, BATCH)


@dataclass(frozen=True)
class LocalNamesResult:
    """What a run did."""

    pins: int  # pins researched
    stored: int  # suggestions stored
    verified: int  # of which the search confirmed the place
    skipped: bool  # every batch had the same input recently


def targets(session: Session, trip: Trip) -> list[TripPin]:
    """Pins with a place ID, no local name and no pending suggestion."""
    pending = set(
        session.scalars(
            select(AiSuggestion.key).where(
                AiSuggestion.trip_id == trip.id, AiSuggestion.kind == KIND, AiSuggestion.status == "pending"
            )
        )
    )
    return [
        p
        for p in sorted(trip.pins, key=lambda x: x.id)
        if p.place.google_place_id and not p.place.local_name and str(p.place_id) not in pending
    ]


def _rejected(session: Session, trip_id: int) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for r in session.scalars(
        select(AiSuggestion).where(
            AiSuggestion.trip_id == trip_id, AiSuggestion.kind == KIND, AiSuggestion.status == "rejected"
        )
    ):
        out.setdefault(r.key, []).append(json.loads(r.payload_json)["name_local"])
    return out


def verify(client: GooglePlacesClient, city: CityConfig, name: str, google_place_id: str) -> bool:
    """Whether a text search for ``name`` near the city returns the place's own ID (IDs Only, free)."""
    center = LatLng(city.center.lat, city.center.lng) if city.center else None
    ids = client.search_ids(
        name, region_code=city.region_code or city.country, near=center, radius_m=CITY_RADIUS_M / 2
    )
    return google_place_id in ids


def run_local_names(
    session: Session,
    llm: ClaudeCli,
    client: GooglePlacesClient,
    trip: Trip,
    city: CityConfig,
    *,
    force: bool = False,
) -> LocalNamesResult:
    """Research local names for the trip's pins that lack one and store them as suggestions.

    Raises:
        LlmError: A call failed (suggestions from earlier batches stay stored).
    """
    pins = targets(session, trip)
    rejected = _rejected(session, trip.id)
    stored = verified = researched = 0
    for i in range(0, len(pins), BATCH):
        batch = pins[i : i + BATCH]
        by_id = {p.id: p for p in batch}
        payload = local_names_payload(
            city, pins=batch, rejected={p.id: rejected.get(str(p.place_id), []) for p in batch}
        )
        digest = input_hash(PROMPT, payload)
        if not force and recently_researched(session, trip.id, KIND, digest):
            continue
        researched += len(batch)
        session.commit()  # release SQLite's write lock while the call runs
        result = llm.run(
            "local_names", load_prompt(PROMPT), payload, SCHEMA, tools=("WebSearch", "WebFetch"), timeout=TIMEOUT_S
        )
        raw = result.data.get("items") if isinstance(result.data, dict) else None
        if not isinstance(raw, list):
            raise LlmError("invalid local names output")
        now = datetime.now(UTC)
        seen: set[int] = set()
        for data in raw:
            try:
                item = LocalNameItem.model_validate(data)
            except ValidationError:
                logger.info("dropped an invalid local name item")
                continue
            pin = by_id.get(item.pin_id)
            if pin is None or pin.id in seen or item.confidence == "low":
                continue
            name = item.name_local.strip()
            key = str(pin.place_id)
            if normalize_name(name) in {normalize_name(x) for x in rejected.get(key, [])}:
                continue
            seen.add(pin.id)
            gid = pin.place.google_place_id
            assert gid is not None
            ok = verify(client, city, name, gid)
            row = LocalNameSuggestion(**item.model_dump(exclude={"name_local"}), name_local=name, verified=ok)
            session.add(
                AiSuggestion(
                    trip_id=trip.id,
                    kind=KIND,
                    key=key,
                    payload_json=row.model_dump_json(),
                    google_place_id=gid,
                    prompt_version=PROMPT,
                    input_hash=digest,
                    created_at=now,
                )
            )
            stored += 1
            verified += ok
        session.commit()
    return LocalNamesResult(researched, stored, verified, skipped=bool(pins) and researched == 0)
