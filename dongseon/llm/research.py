"""AI scouting: web research for places and stays, stored as pending suggestions the user accepts or rejects.

Headless Claude Code runs with ``WebSearch``/``WebFetch`` only. Items without a source are dropped, names are
matched to Google place IDs with the free IDs Only search, and matches far from the city are discarded. Runs are
skipped when the same input (hash + prompt version) was researched within ``MAX_AGE_DAYS``.
"""

import hashlib
import json
import logging
import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from dongseon.core.cities import CityConfig
from dongseon.db.models import AiSuggestion
from dongseon.llm.claude_cli import ClaudeCli, LlmError, load_prompt
from dongseon.places.service import distance_m, store_geo
from dongseon.sources.google_places import GooglePlacesClient, LatLng, PlaceNotFoundError

logger = logging.getLogger(__name__)

MAX_AGE_DAYS = 7
TIMEOUT_S = 900  # web research takes a few minutes
CITY_RADIUS_M = 40_000.0  # a match farther than this from the city center is a wrong match
PLACES_PROMPT = "places_research_v1"
STAYS_PROMPT = "stay_research_v1"


class Source(BaseModel):
    """A cited page."""

    title: str = Field(max_length=300)
    url: str = Field(pattern=r"^https?://", max_length=2000)


class PlaceItem(BaseModel):
    """One researched place."""

    name: str = Field(min_length=1, max_length=100)
    name_local: str | None = Field(default=None, max_length=100)
    area: str = Field(max_length=50)
    category: Literal["food", "cafe", "bar", "sight", "museum", "shopping", "experience"]
    meal: Literal["lunch", "dinner"] | None = None
    why: str = Field(max_length=300)
    reservation: Literal["required", "recommended", "not_needed", "unknown"] = "unknown"
    price_range: str | None = Field(default=None, max_length=100)
    holiday_note: str | None = Field(default=None, max_length=300)
    sources: list[Source] = Field(min_length=1, max_length=3)
    confidence: Literal["high", "medium", "low"] = "medium"


class StayItem(BaseModel):
    """One researched hotel-type stay."""

    name: str = Field(min_length=1, max_length=100)
    name_local: str | None = Field(default=None, max_length=100)
    area: str = Field(max_length=50)
    type: Literal["hotel", "apartment_hotel", "ryokan", "other"] = "hotel"
    has_bathtub: bool | None = None
    nightly_low: int | None = Field(default=None, ge=0)
    nightly_high: int | None = Field(default=None, ge=0)
    currency: str = Field(default="JPY", pattern=r"^[A-Z]{3}$")
    price_note: str | None = Field(default=None, max_length=300)
    why: str = Field(max_length=300)
    sources: list[Source] = Field(min_length=1, max_length=3)
    confidence: Literal["high", "medium", "low"] = "medium"


class _Envelope(BaseModel):
    items: list[dict]


def _schema(item: type[BaseModel], max_items: int) -> dict:
    """``{"items": [item, ...]}`` with the item's ``$defs`` hoisted to the root so ``#/$defs/...`` resolves."""
    item_schema = item.model_json_schema()
    defs = item_schema.pop("$defs", {})
    schema: dict = {
        "type": "object",
        "properties": {"items": {"type": "array", "items": item_schema, "maxItems": max_items}},
        "required": ["items"],
        "additionalProperties": False,
    }
    if defs:
        schema["$defs"] = defs
    return schema


PLACES_SCHEMA = _schema(PlaceItem, 20)
STAYS_SCHEMA = _schema(StayItem, 12)


def normalize_name(name: str) -> str:
    """Dedupe key: NFKC, lowercase, no spaces or punctuation."""
    text = unicodedata.normalize("NFKC", name).lower()
    return re.sub(r"[\s\W_]+", "", text)


def input_hash(prompt_version: str, payload: dict) -> str:
    """Hash of the prompt version and payload (minus the date) for run caching."""
    stable = {k: v for k, v in payload.items() if k != "today"}
    raw = json.dumps({"v": prompt_version, "p": stable}, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def recently_researched(session: Session, trip_id: int, kind: str, digest: str) -> bool:
    """Whether the same input produced suggestions within ``MAX_AGE_DAYS``."""
    since = datetime.now(UTC) - timedelta(days=MAX_AGE_DAYS)
    return (
        session.scalar(
            select(AiSuggestion.id).where(
                AiSuggestion.trip_id == trip_id,
                AiSuggestion.kind == kind,
                AiSuggestion.input_hash == digest,
                AiSuggestion.created_at >= since,
            )
        )
        is not None
    )


def known_keys(session: Session, trip_id: int, kind: str) -> set[str]:
    """Dedupe keys of every suggestion of this kind already made for the trip (any status)."""
    return set(
        session.scalars(select(AiSuggestion.key).where(AiSuggestion.trip_id == trip_id, AiSuggestion.kind == kind))
    )


def match_place(
    session: Session, client: GooglePlacesClient, city: CityConfig, name: str, name_local: str | None, area: str
) -> str | None:
    """Find a place ID for a researched name; ``None`` when nothing near the city matches."""
    center = LatLng(city.center.lat, city.center.lng) if city.center else None
    region = city.region_code or city.country
    for query in [q for q in (f"{name_local} {area}" if name_local else None, f"{name} {area} {city.name}") if q]:
        ids = client.search_ids(query, region_code=region, near=center, radius_m=CITY_RADIUS_M / 2)
        if not ids:
            continue
        try:
            geo = client.details_geo(ids[0])
        except PlaceNotFoundError:
            continue
        if center and distance_m(center, LatLng(geo.lat, geo.lng)) > CITY_RADIUS_M:
            continue
        store_geo(session, geo)
        return geo.place_id
    return None


@dataclass(frozen=True)
class ScoutResult:
    """Counts from one research run."""

    kind: str
    skipped: bool
    proposed: int
    stored: int
    unmatched: int


def _validated[T: BaseModel](raw: object, item: type[T]) -> list[T]:
    try:
        items = _Envelope.model_validate(raw).items
    except ValidationError as e:
        raise LlmError(f"invalid research output: {e.error_count()} errors") from e
    out: list[T] = []
    for data in items:
        try:
            out.append(item.model_validate(data))
        except ValidationError:
            logger.info("dropped an invalid research item")
    return out


def run_research(
    session: Session,
    llm: ClaudeCli,
    client: GooglePlacesClient,
    city: CityConfig,
    *,
    trip_id: int,
    kind: Literal["place", "stay"],
    payload: dict,
    blocked_keys: set[str],
    force: bool = False,
) -> ScoutResult:
    """Research, validate, dedupe, match and store pending suggestions.

    Args:
        session: DB session.
        llm: Claude Code caller.
        client: Places client for name → place ID matching.
        city: Trip city config.
        trip_id: Trip the suggestions belong to.
        kind: "place" or "stay".
        payload: Input built in ``dongseon.llm.payloads``.
        blocked_keys: Normalized names to skip (already planned or already suggested).
        force: Research even when the same input ran recently.

    Raises:
        LlmError: The call failed or the output was invalid.
    """
    version = PLACES_PROMPT if kind == "place" else STAYS_PROMPT
    digest = input_hash(version, payload)
    if not force and recently_researched(session, trip_id, kind, digest):
        return ScoutResult(kind, True, 0, 0, 0)
    schema = PLACES_SCHEMA if kind == "place" else STAYS_SCHEMA
    # Release SQLite's write lock: the call records its usage in llm_runs on another connection.
    session.commit()
    result = llm.run(
        f"{kind}_research", load_prompt(version), payload, schema, tools=("WebSearch", "WebFetch"), timeout=TIMEOUT_S
    )
    items: list[PlaceItem] | list[StayItem] = (
        _validated(result.data, PlaceItem) if kind == "place" else _validated(result.data, StayItem)
    )
    blocked = set(blocked_keys) | known_keys(session, trip_id, kind)
    stored = unmatched = 0
    now = datetime.now(UTC)
    for it in items:
        key = normalize_name(it.name)
        if not key or key in blocked:
            continue
        blocked.add(key)
        pid = match_place(session, client, city, it.name, it.name_local, it.area)
        if pid is None:
            unmatched += 1
        session.add(
            AiSuggestion(
                trip_id=trip_id,
                kind=kind,
                key=key,
                payload_json=it.model_dump_json(),
                google_place_id=pid,
                prompt_version=version,
                input_hash=digest,
                created_at=now,
            )
        )
        stored += 1
    session.flush()
    return ScoutResult(kind, False, len(items), stored, unmatched)
