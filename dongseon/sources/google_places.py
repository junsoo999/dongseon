"""Google Places API (New) client.

Every billable request is counted with the injected ``meter`` before it is sent. Field masks are kept
minimal; each request bills at the highest SKU among its fields (see ``docs/google-terms.md``,
https://developers.google.com/maps/documentation/places/web-service/data-fields, checked 2026-11-04).

Nothing returned here may be stored except ``place_id`` and, in ``geo_cache``, coordinates for 30 days.
"""

from collections.abc import Callable
from dataclasses import dataclass

import httpx

from dongseon.sources.http import send_with_retry

BASE_URL = "https://places.googleapis.com/v1"

# Place Details: id + location + types are all Essentials (types is Essentials; primaryType would be Pro).
DETAILS_ESSENTIALS_FIELDS = "id,location,types"
SKU_DETAILS_ESSENTIALS = "places_details_essentials"
# Place Details with only id: Essentials (IDs Only), no free-tier cap. Used to re-check stored place IDs.
DETAILS_IDS_ONLY_FIELDS = "id"
SKU_DETAILS_IDS_ONLY = "places_details_ids_only"
# Text Search with only places.id: Text Search Essentials (IDs Only), no free-tier cap.
TEXT_SEARCH_IDS_ONLY_FIELDS = "places.id"
SKU_TEXT_SEARCH_IDS_ONLY = "places_text_search_ids_only"
# Autocomplete (New): billed per request as Autocomplete Requests (the first 12 in a session; later ones are free).
# Counting every request is a deliberate overestimate.
SKU_AUTOCOMPLETE = "places_autocomplete"

Meter = Callable[[str], None]


class PlacesError(RuntimeError):
    """Raised for a Places API error response."""

    def __init__(self, status_code: int, status: str, message: str) -> None:
        """Keep the HTTP code and the API's error status."""
        super().__init__(f"{status_code} {status}: {message}")
        self.status_code = status_code
        self.status = status


class PlacesAuthError(PlacesError):
    """Raised when the API key is invalid or not allowed to call the API."""


class PlaceNotFoundError(PlacesError):
    """Raised when a place ID is invalid or no longer exists."""


@dataclass(frozen=True)
class Suggestion:
    """One autocomplete suggestion. Display-only: never store ``main_text`` or ``secondary_text``."""

    place_id: str
    main_text: str
    secondary_text: str
    types: list[str]


@dataclass(frozen=True)
class PlaceGeo:
    """Coordinates and types of a place (Place Details Essentials)."""

    place_id: str
    lat: float
    lng: float
    types: list[str]


@dataclass(frozen=True)
class LatLng:
    """A coordinate pair."""

    lat: float
    lng: float


def _raise_for_error(resp: httpx.Response) -> None:
    if resp.is_success:
        return
    try:
        err = resp.json().get("error", {})
    except ValueError:
        err = {}
    status = str(err.get("status") or "")
    message = str(err.get("message") or resp.text[:200])
    reasons = {d.get("reason") for d in err.get("details") or [] if isinstance(d, dict)}
    if resp.status_code in (401, 403) or "API_KEY_INVALID" in reasons:
        raise PlacesAuthError(resp.status_code, status, message)
    if resp.status_code == 404 or (status == "INVALID_ARGUMENT" and "Place ID" in message):
        raise PlaceNotFoundError(resp.status_code, status, message)
    raise PlacesError(resp.status_code, status, message)


class GooglePlacesClient:
    """Minimal Places API (New) client with per-request metering."""

    def __init__(self, http: httpx.Client, api_key: str, meter: Meter, *, language: str = "ko") -> None:
        """Create a client.

        Args:
            http: HTTP client (tests inject one routed through respx).
            api_key: Server key.
            meter: Called with the SKU before every request; raises to block the call.
            language: ``languageCode`` for results.
        """
        self._http = http
        self._key = api_key
        self._meter = meter
        self._language = language

    def _headers(self, field_mask: str | None = None) -> dict[str, str]:
        headers = {"X-Goog-Api-Key": self._key}
        if field_mask:
            headers["X-Goog-FieldMask"] = field_mask
        return headers

    def autocomplete(
        self,
        text: str,
        *,
        session_token: str,
        region_code: str | None = None,
        bias: LatLng | None = None,
        bias_radius_m: float = 20_000.0,
    ) -> list[Suggestion]:
        """Return place suggestions for partial input.

        Args:
            text: What the user has typed.
            session_token: Same token for every keystroke and the terminating details request.
            region_code: Two-letter country code; also restricts results to that country.
            bias: Prefer results around this point (e.g. the trip city).
            bias_radius_m: Bias circle radius (Places allows up to 50 km).

        Returns:
            Place suggestions (query suggestions are skipped).
        """
        body: dict[str, object] = {"input": text, "sessionToken": session_token, "languageCode": self._language}
        if region_code:
            body["regionCode"] = region_code
            body["includedRegionCodes"] = [region_code.lower()]
        if bias:
            body["locationBias"] = {
                "circle": {"center": {"latitude": bias.lat, "longitude": bias.lng}, "radius": bias_radius_m}
            }
        self._meter(SKU_AUTOCOMPLETE)
        resp = send_with_retry(
            lambda: self._http.post(f"{BASE_URL}/places:autocomplete", headers=self._headers(), json=body)
        )
        _raise_for_error(resp)
        out: list[Suggestion] = []
        for item in resp.json().get("suggestions") or []:
            pred = item.get("placePrediction")
            if not pred:
                continue
            fmt = pred.get("structuredFormat") or {}
            out.append(
                Suggestion(
                    place_id=pred["placeId"],
                    main_text=(fmt.get("mainText") or {}).get("text") or (pred.get("text") or {}).get("text", ""),
                    secondary_text=(fmt.get("secondaryText") or {}).get("text", ""),
                    types=list(pred.get("types") or []),
                )
            )
        return out

    def details_geo(self, place_id: str, *, session_token: str | None = None) -> PlaceGeo:
        """Fetch coordinates and types (Essentials). Ends an autocomplete session when ``session_token`` is given.

        Raises:
            PlaceNotFoundError: If the ID is invalid or the place is gone.
        """
        params = {"languageCode": self._language}
        if session_token:
            params["sessionToken"] = session_token
        self._meter(SKU_DETAILS_ESSENTIALS)
        resp = send_with_retry(
            lambda: self._http.get(
                f"{BASE_URL}/places/{place_id}", headers=self._headers(DETAILS_ESSENTIALS_FIELDS), params=params
            )
        )
        _raise_for_error(resp)
        data = resp.json()
        loc = data["location"]
        return PlaceGeo(
            place_id=data["id"], lat=float(loc["latitude"]), lng=float(loc["longitude"]), types=data.get("types") or []
        )

    def refresh_id(self, place_id: str) -> str:
        """Re-check a stored place ID (IDs Only, free) and return the current ID, which may have changed.

        Raises:
            PlaceNotFoundError: If the place no longer exists.
        """
        self._meter(SKU_DETAILS_IDS_ONLY)
        resp = send_with_retry(
            lambda: self._http.get(f"{BASE_URL}/places/{place_id}", headers=self._headers(DETAILS_IDS_ONLY_FIELDS))
        )
        _raise_for_error(resp)
        return resp.json()["id"]

    def search_ids(
        self, query: str, *, region_code: str | None = None, near: LatLng | None = None, radius_m: float = 500.0
    ) -> list[str]:
        """Find place IDs for a text query (Text Search IDs Only, free), best match first.

        Args:
            query: Place name or description.
            region_code: Two-letter country code to bias results.
            near: Bias results around this point (e.g. coordinates from a shared URL).
            radius_m: Bias circle radius.
        """
        body: dict[str, object] = {"textQuery": query, "languageCode": self._language, "pageSize": 5}
        if region_code:
            body["regionCode"] = region_code
        if near:
            body["locationBias"] = {
                "circle": {"center": {"latitude": near.lat, "longitude": near.lng}, "radius": radius_m}
            }
        self._meter(SKU_TEXT_SEARCH_IDS_ONLY)
        resp = send_with_retry(
            lambda: self._http.post(
                f"{BASE_URL}/places:searchText", headers=self._headers(TEXT_SEARCH_IDS_ONLY_FIELDS), json=body
            )
        )
        _raise_for_error(resp)
        return [p["id"] for p in resp.json().get("places") or []]
