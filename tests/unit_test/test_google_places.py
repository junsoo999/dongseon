import httpx
import pytest
import respx

from dongseon.core.usage import FreeTierExceededError
from dongseon.sources.google_places import (
    BASE_URL,
    SKU_AUTOCOMPLETE,
    SKU_DETAILS_ESSENTIALS,
    SKU_TEXT_SEARCH_IDS_ONLY,
    GooglePlacesClient,
    LatLng,
    PlaceNotFoundError,
    PlacesAuthError,
)
from dongseon.sources.http import send_with_retry

from .conftest import places_fixture

PID = "ChIJY4HWjseLGGARIBjdW6fAwYs"


def _client(calls: list[str]) -> GooglePlacesClient:
    return GooglePlacesClient(httpx.Client(), "test-key", calls.append)


@respx.mock
def test_autocomplete_parses_place_predictions_and_meters() -> None:
    route = respx.post(f"{BASE_URL}/places:autocomplete").respond(json=places_fixture("autocomplete"))
    calls: list[str] = []
    out = _client(calls).autocomplete("가짜", session_token="tok-12345678", region_code="JP")
    assert calls == [SKU_AUTOCOMPLETE]
    assert out[0].place_id == PID
    assert out[0].main_text == "가짜 장소 1"
    assert out[0].secondary_text == "가짜구 가짜동 1"
    sent = route.calls.last.request
    assert sent.headers["X-Goog-Api-Key"] == "test-key"
    body = sent.read().decode()
    assert '"includedRegionCodes":["jp"]' in body.replace(" ", "")


@respx.mock
def test_details_geo_uses_essentials_field_mask() -> None:
    route = respx.get(f"{BASE_URL}/places/{PID}").respond(json=places_fixture("details_essentials"))
    calls: list[str] = []
    geo = _client(calls).details_geo(PID, session_token="tok-12345678")
    assert calls == [SKU_DETAILS_ESSENTIALS]
    assert (geo.lat, geo.lng) == (35.6000001, 139.7000001)
    assert geo.types[0] == "market"
    req = route.calls.last.request
    assert req.headers["X-Goog-FieldMask"] == "id,location,types"
    assert req.url.params["sessionToken"] == "tok-12345678"


@respx.mock
def test_search_ids_is_ids_only() -> None:
    route = respx.post(f"{BASE_URL}/places:searchText").respond(json=places_fixture("text_search_ids"))
    calls: list[str] = []
    ids = _client(calls).search_ids("x", near=LatLng(35.6, 139.7))
    assert calls == [SKU_TEXT_SEARCH_IDS_ONLY]
    assert len(ids) == 2
    assert route.calls.last.request.headers["X-Goog-FieldMask"] == "places.id"


@respx.mock
def test_error_classification() -> None:
    respx.get(f"{BASE_URL}/places/bad").respond(400, json=places_fixture("details_not_found"))
    respx.post(f"{BASE_URL}/places:searchText").respond(400, json=places_fixture("bad_key"))
    client = _client([])
    with pytest.raises(PlaceNotFoundError):
        client.details_geo("bad")
    with pytest.raises(PlacesAuthError):
        client.search_ids("x")


@respx.mock
def test_meter_refusal_blocks_the_request() -> None:
    route = respx.post(f"{BASE_URL}/places:autocomplete").respond(json={})

    def refuse(sku: str) -> None:
        raise FreeTierExceededError(sku, 10, 10)

    with pytest.raises(FreeTierExceededError):
        GooglePlacesClient(httpx.Client(), "k", refuse).autocomplete("ab", session_token="tok-12345678")
    assert not route.called


def test_retry_on_5xx_then_success() -> None:
    responses = iter([httpx.Response(503), httpx.Response(500), httpx.Response(200)])
    delays: list[float] = []
    resp = send_with_retry(lambda: next(responses), sleep=delays.append)
    assert resp.status_code == 200
    assert delays == [1.0, 2.0]


def test_retry_gives_up_after_three_attempts() -> None:
    attempts = 0

    def send() -> httpx.Response:
        nonlocal attempts
        attempts += 1
        raise httpx.ConnectTimeout("t")

    with pytest.raises(httpx.ConnectTimeout):
        send_with_retry(send, sleep=lambda _s: None)
    assert attempts == 3


def test_client_errors_are_not_retried() -> None:
    attempts = []
    resp = send_with_retry(lambda: attempts.append(1) or httpx.Response(400), sleep=lambda _s: None)
    assert resp.status_code == 400
    assert len(attempts) == 1
