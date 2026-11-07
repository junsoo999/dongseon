"""Every LLM input is built here (``docs/google-terms.md``): user data, config values and app-computed results only.

Never add Google Maps Content (Google names, addresses, coordinates, opening hours, travel times) to a payload.
"""

import json
from datetime import date, timedelta
from zoneinfo import ZoneInfo

from dongseon.core.cities import CityConfig
from dongseon.core.profile import Profile
from dongseon.db.models import Itinerary, Trip, TripPin


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


def _hhmm(minutes: int) -> str:
    return f"{(minutes // 60) % 24:02d}:{minutes % 60:02d}"


def _plan_days(it: Itinerary, pins: dict[int, TripPin], tz: ZoneInfo, indoor: set[str]) -> list[dict]:
    """The plan as app data: user labels and categories, the app's own planned times and warning texts.

    Opening-hours labels (``warnings_json["hours"]``), travel minutes and coordinates are left out on purpose.
    """
    stats = json.loads(it.solver_stats_json or "{}")
    out: list[dict] = []
    for iso, info in (stats.get("days") or {}).items():
        d = date.fromisoformat(iso)
        items = []
        for item in sorted((x for x in it.items if x.day == d), key=lambda x: x.seq):
            pin = pins.get(item.pin_id) if item.pin_id else None
            if pin is None:
                continue
            items.append(
                {
                    "pin_id": pin.id,
                    "label": pin.place.label,
                    "category": pin.place.category,
                    "indoor": pin.place.category in indoor,
                    "priority": pin.priority,
                    "meal": pin.meal,
                    "start": item.start_at.astimezone(tz).strftime("%H:%M"),
                    "end": item.end_at.astimezone(tz).strftime("%H:%M"),
                    "dwell_min": pin.dwell_min,
                    "locked": item.locked,
                    "warnings": json.loads(item.warnings_json or "{}").get("warnings") or [],
                }
            )
        out.append(
            {
                "date": iso,
                "weekday": d.strftime("%a"),
                "day_window": f"{_hhmm(info['start_min'])}-{_hhmm(info['end_min'])}",
                "stay": info.get("depot"),
                "warnings": info.get("warnings") or [],
                "items": items,
            }
        )
    return out


def _pool(it: Itinerary, pins: dict[int, TripPin], indoor: set[str]) -> list[dict]:
    stats = json.loads(it.solver_stats_json or "{}")
    return [
        {
            "pin_id": x["pin_id"],
            "label": pins[x["pin_id"]].place.label,
            "category": pins[x["pin_id"]].place.category,
            "indoor": pins[x["pin_id"]].place.category in indoor,
            "priority": pins[x["pin_id"]].priority,
            "dwell_min": pins[x["pin_id"]].dwell_min,
            "why_not_planned": x["reason"],
            "removed_by_user": bool(x.get("excluded")),
        }
        for x in stats.get("dropped") or []
        if x["pin_id"] in pins
    ]


def _review_base(trip: Trip, city: CityConfig, profile: Profile) -> dict:
    return {
        **_trip(trip, city, profile),
        "pace": trip.pace,
        "meal_windows": {k: f"{v.start:%H:%M}-{v.end:%H:%M}" for k, v in profile.meal_windows.items()},
        "food_likes": profile.food.likes,
        "food_avoid": profile.food.avoid,
        "holidays": [
            {"start": p.start, "end": p.end, "note": p.note}
            for p in city.holiday_periods
            if any(
                p.contains(trip.start_date + timedelta(days=i))
                for i in range((trip.end_date - trip.start_date).days + 1)
            )
        ],
    }


def plan_review_payload(
    trip: Trip,
    city: CityConfig,
    profile: Profile,
    *,
    itinerary: Itinerary,
    pins: dict[int, TripPin],
    indoor: set[str],
    rejected: list[str],
) -> dict:
    """Input for ``plan_review``: the version's plan, the pins left out, preferences and holiday notes."""
    return {
        **_review_base(trip, city, profile),
        "days": _plan_days(itinerary, pins, ZoneInfo(trip.timezone), indoor),
        "pool": _pool(itinerary, pins, indoor),
        "rejected": rejected,
    }


def rain_plan_payload(
    trip: Trip,
    city: CityConfig,
    profile: Profile,
    *,
    itinerary: Itinerary,
    pins: dict[int, TripPin],
    indoor: set[str],
    rain_date: date,
    rejected: list[str],
) -> dict:
    """Input for ``rain_plan``: the rainy day's plan and indoor pins planned on other days or left out."""
    days = _plan_days(itinerary, pins, ZoneInfo(trip.timezone), indoor)
    rainy = next((d for d in days if d["date"] == rain_date.isoformat()), None)
    elsewhere = [
        {**{k: x[k] for k in ("pin_id", "label", "category", "priority", "dwell_min")}, "planned_date": d["date"]}
        for d in days
        if d["date"] != rain_date.isoformat()
        for x in d["items"]
        if x["indoor"]
    ]
    pool = [
        {**{k: x[k] for k in ("pin_id", "label", "category", "priority", "dwell_min")}, "planned_date": None}
        for x in _pool(itinerary, pins, indoor)
        if x["indoor"] and not x["removed_by_user"]
    ]
    return {
        **_review_base(trip, city, profile),
        "rain_date": rain_date.isoformat(),
        "day": rainy,
        "indoor_candidates": elsewhere + pool,
        "rejected": rejected,
    }


def hours_research_payload(trip: Trip, city: CityConfig, *, pins: list[TripPin], dates: list[date]) -> dict:
    """Input for ``hours_research``: the user's labels, categories and notes, and the holiday dates.

    No Google names, addresses or hours: the model identifies the place from the user's own label.
    """
    return {
        "city": city.name,
        "country": city.country,
        "dates": [d.isoformat() for d in dates],
        "holidays": [
            {"start": p.start, "end": p.end, "note": p.note}
            for p in city.holiday_periods
            if any(p.contains(d) for d in dates)
        ],
        "places": [
            {"pin_id": p.id, "label": p.place.label, "category": p.place.category, "note": p.place.user_note}
            for p in pins
        ],
    }


def area_notes_payload(trip: Trip, city: CityConfig, profile: Profile) -> dict:
    """Input for ``stay_area_notes``: configured area labels and the household's stay preferences."""
    return {
        **_trip(trip, city, profile),
        "areas": [{"label": a.label, "name_en": a.search_name} for a in city.stay_areas],
        "prefer": profile.stay.prefer,
        "wants": profile.stay.wants,
    }
