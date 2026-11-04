"""Every LLM input is built here (``docs/google-terms.md``): user data, config values and app-computed results only.

Never add Google Maps Content (Google names, addresses, coordinates, opening hours, travel times) to a payload.
"""

from datetime import date

from dongseon.core.cities import CityConfig
from dongseon.core.profile import Profile
from dongseon.db.models import Trip


def _trip(trip: Trip, city: CityConfig, profile: Profile) -> dict:
    return {
        "city": city.name,
        "country": city.country,
        "start_date": trip.start_date.isoformat(),
        "end_date": trip.end_date.isoformat(),
        "travelers": max(1, len(profile.travelers)),
        "today": date.today().isoformat(),  # noqa: DTZ011 - a calendar hint for the model
    }


def places_research_payload(
    trip: Trip,
    city: CityConfig,
    profile: Profile,
    *,
    existing_labels: list[str],
    rejected: list[str],
    areas: list[str],
    want: dict[str, int],
) -> dict:
    """Input for ``places_research``: preferences, user labels of planned places, area labels from config."""
    return {
        **_trip(trip, city, profile),
        "food_likes": profile.food.likes,
        "food_avoid": profile.food.avoid,
        "interests": [],
        "areas": areas,
        "existing": existing_labels,
        "rejected": rejected,
        "want": want,
    }


def stay_research_payload(
    trip: Trip, city: CityConfig, profile: Profile, *, areas: list[dict], rejected: list[str]
) -> dict:
    """Input for ``stay_research``: preferences and the app's area ranking (labels and approximate minutes)."""
    return {
        **_trip(trip, city, profile),
        "prefer": profile.stay.prefer,
        "wants": profile.stay.wants,
        "nightly_budget_krw": profile.stay.nightly_budget_krw,
        "areas": areas,
        "rejected": rejected,
    }
