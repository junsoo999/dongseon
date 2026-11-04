"""Score places to stay by approximate travel time to the trip's must/want pins.

The score is a priority-weighted average of minutes (lower is better); weights come from the profile.
"""

from dataclasses import dataclass

from dongseon.core.cities import Approx
from dongseon.matrix.approx import approx_leg
from dongseon.sources.google_places import LatLng


@dataclass(frozen=True)
class Target:
    """A pin to reach, with its priority weight."""

    label: str
    point: LatLng
    weight: int


@dataclass(frozen=True)
class AirportAccess:
    """An airport's location and its express links (hub location + ride minutes)."""

    point: LatLng
    express: list[tuple[LatLng, int]]


@dataclass(frozen=True)
class OriginScore:
    """Travel summary from one place to stay."""

    weighted_avg_min: int | None
    max_min: int | None
    farthest_label: str | None
    airport_min: dict[str, int]


def airport_minutes(origin: LatLng, access: AirportAccess, params: Approx) -> int:
    """Fastest of the direct estimate and each express link (approx to the hub + wait + published ride time)."""
    best = approx_leg(origin, access.point, params).minutes
    for hub, ride_min in access.express:
        best = min(best, approx_leg(origin, hub, params).minutes + round(params.wait_min) + ride_min)
    return best


def score_origin(
    origin: LatLng, targets: list[Target], airports: dict[str, AirportAccess], params: Approx
) -> OriginScore:
    """Summarize approximate minutes from ``origin`` to every target and airport."""
    airport_min = {code: airport_minutes(origin, a, params) for code, a in airports.items()}
    if not targets:
        return OriginScore(None, None, None, airport_min)
    legs = [(t, approx_leg(origin, t.point, params).minutes) for t in targets]
    total_w = sum(t.weight for t, _ in legs)
    weighted = sum(t.weight * m for t, m in legs) / total_w if total_w else sum(m for _, m in legs) / len(legs)
    far_t, far_m = max(legs, key=lambda x: x[1])
    return OriginScore(round(weighted), far_m, far_t.label, airport_min)
