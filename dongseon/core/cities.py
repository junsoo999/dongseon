"""Per-city configuration (``config/cities/<key>.yaml``): timezone, currency, airports, stay areas, holidays."""

from datetime import date
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml
from pydantic import BaseModel, Field, field_validator


class ExpressLink(BaseModel):
    """A fast airport train from a hub station, with its published fastest ride time."""

    hub_label: str
    hub_query: str
    ride_min: int
    name: str
    source_url: str


class Airport(BaseModel):
    """An airport, resolved to a Google place by its search query."""

    code: str
    query: str
    express: list[ExpressLink] = Field(default_factory=list)


class StayArea(BaseModel):
    """A candidate neighborhood, represented by its main station."""

    label: str
    query: str


class HolidayPeriod(BaseModel):
    """A recurring period with irregular opening hours (e.g. year-end holidays).

    ``start`` and ``end`` are ``"MM-DD"``; a period may wrap the year end (``12-29`` to ``01-04``).
    """

    key: str
    start: str
    end: str
    note: str
    source_url: str
    as_of: date

    @field_validator("start", "end")
    @classmethod
    def _check_mm_dd(cls, value: str) -> str:
        month, day = (int(x) for x in value.split("-"))
        date(2024, month, day)  # leap year, so 02-29 is accepted
        return value

    def contains(self, d: date) -> bool:
        """Whether ``d`` falls inside the period (inclusive, wrapping the year end)."""
        key = f"{d.month:02d}-{d.day:02d}"
        if self.start <= self.end:
            return self.start <= key <= self.end
        return key >= self.start or key <= self.end


class Center(BaseModel):
    """A map center."""

    lat: float
    lng: float


class Approx(BaseModel):
    """Parameters of the straight-line travel-time approximation (see the city YAML for sources)."""

    as_of: date
    detour_factor: float
    walk_m_per_min: float
    walk_max_km: float
    rail_speed_kmh: float
    rail_speed_source_url: str
    station_access_min: float
    wait_min: float


class CityConfig(BaseModel):
    """One city's static configuration."""

    key: str
    name: str
    country: str
    timezone: str
    currency: str
    region_code: str | None = None
    center: Center | None = None
    airports: list[Airport] = Field(default_factory=list)
    stay_areas: list[StayArea] = Field(default_factory=list)
    approx: Approx | None = None
    holiday_periods: list[HolidayPeriod] = Field(default_factory=list)

    @field_validator("timezone")
    @classmethod
    def _check_timezone(cls, value: str) -> str:
        ZoneInfo(value)
        return value

    @property
    def tz(self) -> ZoneInfo:
        """The city's timezone."""
        return ZoneInfo(self.timezone)

    def holidays_on(self, d: date) -> list[HolidayPeriod]:
        """Holiday periods that include ``d``."""
        return [p for p in self.holiday_periods if p.contains(d)]


class CityNotFoundError(LookupError):
    """Raised when ``config/cities/<key>.yaml`` does not exist."""


def load_city(cities_dir: Path, key: str) -> CityConfig:
    """Load and validate one city's YAML.

    Args:
        cities_dir: Directory holding ``<key>.yaml`` files.
        key: City key, e.g. ``"tokyo"``.

    Returns:
        The validated city config.

    Raises:
        CityNotFoundError: If the file does not exist.
    """
    path = cities_dir / f"{key}.yaml"
    if not path.exists():
        raise CityNotFoundError(key)
    return CityConfig.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")) or {})


def list_cities(cities_dir: Path) -> list[CityConfig]:
    """Load every city YAML in ``cities_dir``, sorted by key."""
    return [load_city(cities_dir, p.stem) for p in sorted(cities_dir.glob("*.yaml"))]
