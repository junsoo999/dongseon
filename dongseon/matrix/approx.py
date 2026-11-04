"""Travel-time approximation from straight-line distance (shown as "근사").

Used because Google Routes returns no transit routes in Japan. Parameters live in ``config/cities/<city>.yaml``.
"""

import math
from dataclasses import dataclass
from typing import Literal

from dongseon.core.cities import Approx
from dongseon.sources.google_places import LatLng

Mode = Literal["walk", "rail"]


@dataclass(frozen=True)
class Leg:
    """An approximate leg."""

    minutes: int
    mode: Mode
    km: float


def distance_km(a: LatLng, b: LatLng) -> float:
    """Great-circle distance in kilometers."""
    r = 6371.0
    p1, p2 = math.radians(a.lat), math.radians(b.lat)
    dp, dl = p2 - p1, math.radians(b.lng - a.lng)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def approx_leg(a: LatLng, b: LatLng, params: Approx) -> Leg:
    """Estimate one leg: walk when short, otherwise rail (station access + wait + ride), whichever is faster."""
    km = distance_km(a, b) * params.detour_factor
    walk = km * 1000 / params.walk_m_per_min
    if km <= params.walk_max_km:
        return Leg(minutes=max(1, round(walk)), mode="walk", km=km)
    rail = params.station_access_min + params.wait_min + km / params.rail_speed_kmh * 60
    if walk <= rail:
        return Leg(minutes=round(walk), mode="walk", km=km)
    return Leg(minutes=round(rail), mode="rail", km=km)
