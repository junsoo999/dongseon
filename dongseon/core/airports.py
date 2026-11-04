"""Airport list (``config/airports.yaml``): code, name and timezone for flight legs."""

from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml
from pydantic import BaseModel, field_validator


class AirportInfo(BaseModel):
    """One airport."""

    code: str
    name: str
    timezone: str

    @field_validator("timezone")
    @classmethod
    def _check_tz(cls, value: str) -> str:
        ZoneInfo(value)
        return value

    @property
    def tz(self) -> ZoneInfo:
        """The airport's timezone."""
        return ZoneInfo(self.timezone)


@lru_cache
def load_airports(path: Path) -> dict[str, AirportInfo]:
    """Parse the airport list keyed by IATA code."""
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {a["code"]: AirportInfo.model_validate(a) for a in data.get("airports") or []}
