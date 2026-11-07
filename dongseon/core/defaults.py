"""Shared, non-personal defaults (``config/defaults.yaml``): free-tier caps, categories, dwell times."""

from datetime import date
from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class FreeTier(BaseModel):
    """Monthly free call caps per Google SKU, as published by Google on ``as_of``.

    A ``None`` cap means the SKU has no free-tier cap (e.g. Text Search IDs Only); it is counted but never blocked.
    """

    as_of: date
    source_url: str
    billing_timezone: str
    monthly_free: dict[str, int | None]


class Categories(BaseModel):
    """Google ``primaryType`` to app category mapping and default dwell minutes per category."""

    mapping: dict[str, str] = Field(default_factory=dict)
    fallback: str = "other"
    dwell_min: dict[str, int] = Field(default_factory=dict)
    indoor: list[str] = Field(default_factory=list)  # categories that work on a rainy day


class TripMode(BaseModel):
    """When trip-mode refreshes start and when a forecast counts as rain."""

    window_days: int = 14  # daily refreshes hours, weather and rain plans from this many days before the start
    hours_refresh_days: int = 7  # Google special hours cover today + 6 days
    rain_probability_pct: int = 60  # forecast precipitation probability at or above this is a rainy day
    climate_years: int = 5  # past years averaged for dates beyond the forecast


class Defaults(BaseModel):
    """The parsed defaults file."""

    google_free_tier: FreeTier
    categories: Categories = Field(default_factory=Categories)
    trip_mode: TripMode = Field(default_factory=TripMode)


def load_defaults(path: Path) -> Defaults:
    """Parse and validate ``config/defaults.yaml``.

    Args:
        path: Defaults file path.

    Returns:
        The validated defaults.
    """
    return Defaults.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")) or {})
