"""Ignav flight fares (https://ignav.com/openapi.json).

Terms (effective 2026-10-01): returned flight data may be retained indefinitely and analyzed; no attribution is
required. Each successful (HTTP 200) request uses one credit; booking links are fetched only when the user asks.
"""

from dataclasses import dataclass
from datetime import date, datetime

import httpx

from dongseon.sources.http import send_with_retry

BASE_URL = "https://ignav.com/api"


class IgnavError(RuntimeError):
    """Raised for an Ignav error response."""


@dataclass(frozen=True)
class Segment:
    """One flight of an itinerary (times are timezone-aware UTC)."""

    carrier_code: str
    flight_number: str
    carrier_name: str | None
    dep_airport: str
    dep_at: datetime
    arr_airport: str
    arr_at: datetime


@dataclass(frozen=True)
class Fare:
    """A round-trip itinerary with its total price for all travelers."""

    ignav_id: str
    amount: int
    currency: str
    outbound: list[Segment]
    inbound: list[Segment]
    out_carrier: str | None
    in_carrier: str | None


def _utc(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def _segments(leg: dict | None) -> list[Segment]:
    return [
        Segment(
            carrier_code=s.get("marketing_carrier_code") or "",
            flight_number=str(s.get("flight_number") or ""),
            carrier_name=s.get("operating_carrier_name"),
            dep_airport=s["departure_airport"],
            dep_at=_utc(s["departure_time_utc"]),
            arr_airport=s["arrival_airport"],
            arr_at=_utc(s["arrival_time_utc"]),
        )
        for s in (leg or {}).get("segments") or []
    ]


def parse_round_trip(data: dict) -> list[Fare]:
    """Parse a round-trip response, dropping duplicate itineraries (same flights and price)."""
    seen: set[tuple] = set()
    out: list[Fare] = []
    for it in data.get("itineraries") or []:
        outbound, inbound = _segments(it.get("outbound")), _segments(it.get("inbound"))
        price = it.get("price") or {}
        if not outbound or not inbound or price.get("amount") is None:
            continue
        key = (
            tuple((s.carrier_code, s.flight_number, s.dep_at) for s in outbound + inbound),
            round(float(price["amount"])),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(
            Fare(
                ignav_id=it["ignav_id"],
                amount=round(float(price["amount"])),
                currency=price.get("currency") or "USD",
                outbound=outbound,
                inbound=inbound,
                out_carrier=(it.get("outbound") or {}).get("carrier"),
                in_carrier=(it.get("inbound") or {}).get("carrier"),
            )
        )
    return out


class IgnavClient:
    """Minimal Ignav client."""

    def __init__(self, http: httpx.Client, api_key: str) -> None:
        """Create a client."""
        self._http = http
        self._key = api_key

    def _post(self, path: str, body: dict) -> httpx.Response:
        return send_with_retry(
            lambda: self._http.post(f"{BASE_URL}{path}", headers={"X-Api-Key": self._key}, json=body, timeout=60.0)
        )

    def round_trip(
        self,
        origin: str,
        destination: str,
        departure: date,
        return_: date,
        *,
        adults: int,
        children: int = 0,
        market: str = "KR",
        max_stops: int | None = 0,
        checked_bags: int | None = None,
        departure_hours: tuple[int | None, int | None] = (None, None),
        return_hours: tuple[int | None, int | None] = (None, None),
        max_price: int | None = None,
        airlines_exclude: list[str] | None = None,
    ) -> list[Fare]:
        """Search round-trip fares (one credit).

        Args:
            origin: Departure airport (IATA).
            destination: Arrival airport (IATA).
            departure: Outbound date.
            return_: Return date.
            adults: Adult travelers.
            children: Child travelers.
            market: Market (sets the currency; KR = KRW).
            max_stops: Stops per direction (0 = direct, None = any).
            checked_bags: Checked bags for the whole party (None = no preference).
            departure_hours: Earliest/latest outbound departure hour, local time.
            return_hours: Earliest/latest return departure hour, local time.
            max_price: Upper price bound in the market currency.
            airlines_exclude: Carrier codes to leave out.

        Raises:
            IgnavError: On an error response.
        """
        body: dict[str, object] = {
            "origin": origin,
            "destination": destination,
            "departure_date": departure.isoformat(),
            "return_date": return_.isoformat(),
            "adults": adults,
            "children": children,
            "market": market,
            "max_stops": max_stops,
        }
        if checked_bags:
            body["checked_bags"] = checked_bags
        for key, (earliest, latest) in (
            ("departure_time_range", departure_hours),
            ("return_time_range", return_hours),
        ):
            if earliest is not None or latest is not None:
                body[key] = {"earliest_hour": earliest, "latest_hour": latest}
        if max_price is not None:
            body["max_price"] = max_price
        if airlines_exclude:
            body["airlines_exclude"] = airlines_exclude
        resp = self._post("/fares/round-trip", body)
        if not resp.is_success:
            raise IgnavError(f"{resp.status_code}: {resp.text[:200]}")
        return parse_round_trip(resp.json())

    def booking_url(self, ignav_id: str) -> str | None:
        """First booking link for an itinerary, or ``None`` (404 means no usable links and costs no credit)."""
        resp = self._post("/fares/booking-links", {"ignav_id": ignav_id})
        if resp.status_code == 404:
            return None
        if not resp.is_success:
            raise IgnavError(f"{resp.status_code}: {resp.text[:200]}")
        for option in resp.json().get("booking_options") or []:
            for link in option.get("links") or []:
                if link.get("url"):
                    return link["url"]
        return None
