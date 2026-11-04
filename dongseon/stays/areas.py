"""Link a city's configured stay areas and airports to Google place IDs (IDs Only search, free)."""

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from dongseon.core.cities import CityConfig
from dongseon.db.models import AreaPlace
from dongseon.sources.google_places import GooglePlacesClient


@dataclass(frozen=True)
class AreaRef:
    """A configured area or airport and its place ID (``None`` when not found)."""

    kind: str  # stay_area | airport | hub (an express train's station, key "<airport code>:<hub label>")
    key: str
    label: str
    google_place_id: str | None


def ensure_area_places(session: Session, client: GooglePlacesClient | None, city: CityConfig) -> list[AreaRef]:
    """Return every configured stay area and airport, resolving new or changed ones when a client is given."""
    wanted = [("stay_area", a.label, a.label, a.query) for a in city.stay_areas]
    wanted += [("airport", a.code, a.code, a.query) for a in city.airports]
    wanted += [("hub", f"{a.code}:{x.hub_label}", x.hub_label, x.hub_query) for a in city.airports for x in a.express]
    rows = {(r.kind, r.key): r for r in session.scalars(select(AreaPlace).where(AreaPlace.city_key == city.key)).all()}
    region = city.region_code or city.country
    out: list[AreaRef] = []
    for kind, key, label, query in wanted:
        row = rows.get((kind, key))
        if (row is None or row.query != query or row.google_place_id is None) and client is not None:
            ids = client.search_ids(query, region_code=region)
            if row is None:
                row = AreaPlace(city_key=city.key, kind=kind, key=key, query=query, resolved_at=datetime.now(UTC))
                session.add(row)
            row.query, row.google_place_id, row.resolved_at = query, (ids[0] if ids else None), datetime.now(UTC)
            session.flush()
        out.append(AreaRef(kind=kind, key=key, label=label, google_place_id=row.google_place_id if row else None))
    return out
