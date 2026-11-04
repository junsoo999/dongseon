"""Rakuten Travel vacant hotel search (VacantHotelSearch 2017-04-26).

Free official API. Requests need the app ID, access key and the registered site URL as Referer and Origin; the
API allows about one request per second. Show "Supported by Rakuten Developers" next to results.
"""

import time
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

import httpx

from dongseon.sources.http import send_with_retry

URL = "https://openapi.rakuten.co.jp/engine/api/Travel/VacantHotelSearch/20170426"
MIN_INTERVAL_S = 1.2
CREDIT_TEXT = "Supported by Rakuten Developers"
CREDIT_URL = "https://developers.rakuten.com/"
# Words that suggest an in-room bathtub ("separate bath and toilet", "bathtub"); a hint, not a guarantee.
BATH_HINTS = ("バス・トイレ別", "バストイレ別", "バス、トイレ", "浴槽", "バスタブ", "独立")


class RakutenError(RuntimeError):
    """Raised for a Rakuten error response."""


@dataclass(frozen=True)
class HotelOffer:
    """The cheapest vacant plan of one hotel for the searched dates."""

    hotel_no: int
    name: str
    lat: float
    lng: float
    nearest_station: str | None
    access: str | None
    special: str | None
    review_average: float | None
    review_count: int | None
    thumbnail_url: str | None
    info_url: str | None
    plan_name: str | None
    room_name: str | None
    first_night_total: int | None  # all guests, first night, JPY (the API reports only the first night)
    reserve_url: str | None
    bath_hint: bool


def _first(parts: list, key: str) -> dict:
    for p in parts:
        if isinstance(p, dict) and key in p:
            return p[key]
    return {}


def parse_vacant(data: dict) -> list[HotelOffer]:
    """Parse a formatVersion=2 response into one offer per hotel (its cheapest room plan)."""
    offers: list[HotelOffer] = []
    for parts in data.get("hotels") or []:
        info = _first(parts, "hotelBasicInfo")
        rooms = _first(parts, "roomInfo") or []
        best: tuple[int, dict, dict] | None = None
        # formatVersion 2 lists rooms as [{"roomBasicInfo": ...}, {"dailyCharge": ...}] pairs
        flat = rooms if isinstance(rooms, list) else []
        for i in range(0, len(flat) - 1, 2):
            basic, charge = flat[i].get("roomBasicInfo"), flat[i + 1].get("dailyCharge")
            if not basic or not charge or charge.get("total") is None:
                continue
            total = int(charge["total"])
            if best is None or total < best[0]:
                best = (total, basic, charge)
        if not info or info.get("latitude") is None:
            continue
        text = " ".join(str(x) for x in (info.get("hotelSpecial"), best[1].get("roomName") if best else None) if x)
        offers.append(
            HotelOffer(
                hotel_no=int(info["hotelNo"]),
                name=unicodedata.normalize("NFKC", str(info.get("hotelName") or "")).strip(),
                lat=float(info["latitude"]),
                lng=float(info["longitude"]),
                nearest_station=info.get("nearestStation"),
                access=info.get("access"),
                special=info.get("hotelSpecial"),
                review_average=info.get("reviewAverage"),
                review_count=info.get("reviewCount"),
                thumbnail_url=info.get("hotelThumbnailUrl"),
                info_url=info.get("hotelInformationUrl"),
                plan_name=best[1].get("planName") if best else None,
                room_name=best[1].get("roomName") if best else None,
                first_night_total=best[0] if best else None,
                reserve_url=best[1].get("reserveUrl") if best else None,
                bath_hint=any(h in text for h in BATH_HINTS),
            )
        )
    return offers


class RakutenClient:
    """Vacant hotel search with the API's one-request-per-second pacing."""

    def __init__(
        self,
        http: httpx.Client,
        *,
        app_id: str,
        access_key: str,
        referer: str,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """Create a client."""
        self._http = http
        self._app_id = app_id
        self._key = access_key
        self._referer = referer
        self._origin = referer.rstrip("/")
        self._sleep = sleep
        self._clock = clock
        self._last = 0.0

    def vacant(
        self,
        lat: float,
        lng: float,
        check_in: date,
        check_out: date,
        *,
        adults: int,
        radius_km: float = 1.0,
        hits: int = 30,
    ) -> list[HotelOffer]:
        """Hotels with vacancies around a point (WGS84), cheapest first.

        Raises:
            RakutenError: On an error response (``404`` "not_found" means no vacancies and returns ``[]``).
        """
        wait = MIN_INTERVAL_S - (self._clock() - self._last)
        if wait > 0:
            self._sleep(wait)
        params: dict[str, str | int | float] = {
            "applicationId": self._app_id,
            "accessKey": self._key,
            "format": "json",
            "formatVersion": 2,
            "checkinDate": check_in.isoformat(),
            "checkoutDate": check_out.isoformat(),
            "adultNum": adults,
            "latitude": round(lat, 6),
            "longitude": round(lng, 6),
            "datumType": 1,
            "searchRadius": radius_km,
            "sort": "+roomCharge",
            "hits": hits,
        }
        headers = {"Referer": self._referer, "Origin": self._origin}
        resp = send_with_retry(lambda: self._http.get(URL, params=params, headers=headers, timeout=20.0))
        self._last = self._clock()
        if resp.status_code == 404:
            return []
        if not resp.is_success:
            raise RakutenError(f"{resp.status_code}: {resp.text[:200]}")
        return parse_vacant(resp.json())
