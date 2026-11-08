"""Daily weather from Open-Meteo (no key; free for non-commercial use under 10,000 calls a day, CC BY 4.0).

The forecast covers up to 16 days. Dates beyond it get a climate figure: the same calendar dates averaged over past
years from the historical archive. Coordinates come from the city config (not Google). Show "Weather data by
Open-Meteo.com" wherever the values appear.
"""

from dataclasses import dataclass
from datetime import date

import httpx

from dongseon.sources.http import send_with_retry

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
ATTRIBUTION = "Weather data by Open-Meteo.com"
ATTRIBUTION_URL = "https://open-meteo.com/"
FORECAST_DAYS = 16
_DAILY = "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum"


@dataclass(frozen=True)
class DailyWeather:
    """One day's values as Open-Meteo returns them (missing values are ``None``)."""

    day: date
    code: int | None  # WMO weather code
    tmax: float | None  # °C
    tmin: float | None
    precip_mm: float | None
    precip_prob: int | None = None  # %, forecast only


def _column(daily: dict, key: str, n: int) -> list:
    values = daily.get(key) or []
    return list(values) + [None] * (n - len(values))


def _parse(data: dict) -> list[DailyWeather]:
    daily = data.get("daily") or {}
    days = daily.get("time") or []
    n = len(days)
    code = _column(daily, "weather_code", n)
    tmax = _column(daily, "temperature_2m_max", n)
    tmin = _column(daily, "temperature_2m_min", n)
    rain = _column(daily, "precipitation_sum", n)
    prob = _column(daily, "precipitation_probability_max", n)
    return [
        DailyWeather(
            day=date.fromisoformat(d),
            code=int(code[i]) if code[i] is not None else None,
            tmax=tmax[i],
            tmin=tmin[i],
            precip_mm=rain[i],
            precip_prob=int(prob[i]) if prob[i] is not None else None,
        )
        for i, d in enumerate(days)
    ]


def fetch_forecast(http: httpx.Client, lat: float, lng: float, timezone: str) -> list[DailyWeather]:
    """Fetch the daily forecast from today for ``FORECAST_DAYS`` days.

    Raises:
        httpx.HTTPError: On network errors or a non-2xx response.
    """
    params = {
        "latitude": lat,
        "longitude": lng,
        "daily": _DAILY + ",precipitation_probability_max",
        "timezone": timezone,
        "forecast_days": FORECAST_DAYS,
    }
    resp = send_with_retry(lambda: http.get(FORECAST_URL, params=params))
    resp.raise_for_status()
    return _parse(resp.json())


def fetch_archive(
    http: httpx.Client, lat: float, lng: float, timezone: str, start: date, end: date
) -> list[DailyWeather]:
    """Fetch observed daily weather for a past date range.

    Raises:
        httpx.HTTPError: On network errors or a non-2xx response.
    """
    params = {
        "latitude": lat,
        "longitude": lng,
        "daily": _DAILY,
        "timezone": timezone,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
    }
    resp = send_with_retry(lambda: http.get(ARCHIVE_URL, params=params))
    resp.raise_for_status()
    return _parse(resp.json())
