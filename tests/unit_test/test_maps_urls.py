import httpx
import pytest
import respx

from dongseon.places.urls import UnsupportedUrlError, expand_short_url, is_google_host, parse_maps_url


def test_place_url_with_data_coords_prefers_pin_over_viewport() -> None:
    url = (
        "https://www.google.com/maps/place/Fake+Market/@35.1000000,139.1000000,17z/"
        "data=!3m1!4b1!4m6!3m5!1s0x0:0x0!8m2!3d35.2000000!4d139.2000000!16s%2Fg%2F11?entry=ttu"
    )
    p = parse_maps_url(url)
    assert p.name == "Fake Market"
    assert (p.lat, p.lng) == (35.2, 139.2)
    assert p.place_id is None


def test_place_url_with_viewport_only() -> None:
    p = parse_maps_url("https://www.google.co.jp/maps/place/%E5%81%BD/@35.5,139.5,15z")
    assert p.name == "偽"
    assert (p.lat, p.lng) == (35.5, 139.5)


def test_maps_urls_api_with_place_id() -> None:
    p = parse_maps_url("https://www.google.com/maps/search/?api=1&query=Fake+Cafe&query_place_id=ChIJabc")
    assert p.place_id == "ChIJabc"
    assert p.name == "Fake Cafe"


def test_coordinate_only_query_has_no_name() -> None:
    p = parse_maps_url("https://maps.google.com/?q=35.6,139.7")
    assert p.name is None
    assert (p.lat, p.lng) == (35.6, 139.7)


@pytest.mark.parametrize("url", ["https://evil.example/maps/place/x", "ftp://www.google.com/maps", "not a url"])
def test_non_google_urls_are_rejected(url: str) -> None:
    with pytest.raises(UnsupportedUrlError):
        parse_maps_url(url)


def test_google_host_check() -> None:
    assert is_google_host("www.google.com")
    assert is_google_host("maps.google.co.jp")
    assert is_google_host("google.com.au")
    assert not is_google_host("google.com.evil.example")
    assert not is_google_host("evilgoogle.com")


@respx.mock
def test_short_link_is_expanded_within_google() -> None:
    final = "https://www.google.com/maps/place/Fake/@35.1,139.1,17z"
    respx.get("https://maps.app.goo.gl/abc").respond(302, headers={"location": final})
    assert expand_short_url(httpx.Client(), "https://maps.app.goo.gl/abc") == final


@respx.mock
def test_short_link_through_consent_page() -> None:
    final = "https://www.google.com/maps/place/Fake/@35.1,139.1,17z"
    consent = "https://consent.google.com/m?continue=" + final.replace("/", "%2F").replace(":", "%3A")
    respx.get("https://maps.app.goo.gl/abc").respond(302, headers={"location": consent})
    assert expand_short_url(httpx.Client(), "https://maps.app.goo.gl/abc") == final


@respx.mock
def test_short_link_redirect_outside_google_is_refused() -> None:
    respx.get("https://maps.app.goo.gl/abc").respond(302, headers={"location": "http://127.0.0.1:8100/api/health"})
    with pytest.raises(UnsupportedUrlError):
        expand_short_url(httpx.Client(), "https://maps.app.goo.gl/abc")
