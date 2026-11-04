"""Map Google place types to app categories and default dwell times (``config/defaults.yaml``)."""

from dongseon.core.defaults import Categories


def category_for_types(types: list[str], categories: Categories) -> str:
    """Return the app category of the first mapped Google type, or the fallback."""
    for t in types:
        if t in categories.mapping:
            return categories.mapping[t]
    return categories.fallback


def dwell_for(category: str, categories: Categories) -> int:
    """Default dwell minutes for an app category (fallback category's value when missing)."""
    return categories.dwell_min.get(category, categories.dwell_min.get(categories.fallback, 60))
