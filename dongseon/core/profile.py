"""Read the household profile (``config/profile.yaml``; tests use ``config/profile.example.yaml``)."""

from datetime import time
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator

Pace = Literal["relaxed", "normal", "packed"]
Priority = Literal["must", "want", "maybe"]


def _parse_hhmm(value: object) -> time:
    """Parse ``"HH:MM"`` (YAML may also give an int of minutes for ``HH:MM`` without quotes)."""
    if isinstance(value, time):
        return value
    if isinstance(value, int):  # YAML 1.1 reads unquoted 09:00 as sexagesimal minutes
        return time(value // 60, value % 60)
    hh, mm = str(value).split(":")
    return time(int(hh), int(mm))


class TimeWindow(BaseModel):
    """A local time range within one day."""

    start: time
    end: time

    @classmethod
    def from_pair(cls, pair: list[object]) -> "TimeWindow":
        """Build from a ``["HH:MM", "HH:MM"]`` pair."""
        start, end = pair
        return cls(start=_parse_hhmm(start), end=_parse_hhmm(end))


class Traveler(BaseModel):
    """A traveler, identified by a display label only."""

    label: str


class Buffers(BaseModel):
    """Buffers in minutes."""

    departure_airport: int = 120
    arrival_immigration: int = 60
    transfer: int = 10


class Walking(BaseModel):
    """Walking preferences."""

    max_walk_min_per_leg: int = 15


class FoodPrefs(BaseModel):
    """Food likes and dislikes (free text)."""

    likes: list[str] = Field(default_factory=list)
    avoid: list[str] = Field(default_factory=list)


class StayPrefs(BaseModel):
    """Stay preferences for recommendations."""

    prefer: list[str] = Field(default_factory=list)  # e.g. ["airbnb", "hotel"]
    wants: list[str] = Field(default_factory=list)  # e.g. ["욕조"]
    nightly_budget_krw: int | None = None


class Profile(BaseModel):
    """Household travel preferences."""

    travelers: list[Traveler] = Field(default_factory=list)
    home_airports: list[str] = Field(default_factory=list)
    pace: Pace = "normal"
    day_windows: dict[Pace, TimeWindow]
    # Meal slots: a restaurant visit fits inside one, and each slot holds at most one restaurant a day.
    meal_windows: dict[Literal["breakfast", "lunch", "afternoon", "dinner"], TimeWindow]
    max_meals_per_day: int = Field(default=3, ge=1, le=4)
    buffers_min: Buffers = Field(default_factory=Buffers)
    priority_weights: dict[Priority, int] = Field(default_factory=lambda: {"must": 100, "want": 10, "maybe": 1})
    walking: Walking = Field(default_factory=Walking)
    food: FoodPrefs = Field(default_factory=FoodPrefs)
    stay: StayPrefs = Field(default_factory=StayPrefs)

    @field_validator("day_windows", "meal_windows", mode="before")
    @classmethod
    def _pairs_to_windows(cls, value: object) -> object:
        if isinstance(value, dict):
            return {k: TimeWindow.from_pair(v) if isinstance(v, list) else v for k, v in value.items()}
        return value

    @field_validator("meal_windows")
    @classmethod
    def _default_third_meal(cls, value: dict[str, TimeWindow]) -> dict[str, TimeWindow]:
        if "breakfast" not in value and "afternoon" not in value:  # profiles written before the third slot
            value = {**value, "afternoon": TimeWindow(start=time(14, 30), end=time(17, 0))}
        return value

    @property
    def day_window(self) -> TimeWindow:
        """The day window for the default pace."""
        return self.day_windows[self.pace]


def load_profile(path: Path) -> Profile:
    """Parse and validate the profile YAML.

    Args:
        path: Profile file path.

    Returns:
        The validated profile.
    """
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return Profile.model_validate(data)
