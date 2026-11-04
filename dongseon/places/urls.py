"""Parse Google Maps share URLs pasted by the user.

Short links (``maps.app.goo.gl``) are expanded by following redirects, but only across Google hosts so the
server never fetches arbitrary URLs. Page bodies are never read.
"""

import re
from dataclasses import dataclass
from urllib.parse import parse_qs, unquote_plus, urljoin, urlparse

import httpx

SHORT_HOSTS = {"maps.app.goo.gl", "goo.gl"}
MAX_REDIRECTS = 5

_COORD_PAIR = re.compile(r"^\s*(-?\d{1,2}(?:\.\d+)?)\s*,\s*(-?\d{1,3}(?:\.\d+)?)\s*$")
_AT_COORDS = re.compile(r"/@(-?\d{1,2}\.\d+),(-?\d{1,3}\.\d+)")
_DATA_COORDS = re.compile(r"!3d(-?\d{1,2}\.\d+)!4d(-?\d{1,3}\.\d+)")


class UnsupportedUrlError(ValueError):
    """Raised for a URL that is not a Google Maps link."""


@dataclass(frozen=True)
class ParsedMapsUrl:
    """What a Maps URL tells us. Any field may be missing."""

    place_id: str | None = None
    name: str | None = None
    lat: float | None = None
    lng: float | None = None

    @property
    def has_coords(self) -> bool:
        """Whether both coordinates are present."""
        return self.lat is not None and self.lng is not None


def is_google_host(host: str) -> bool:
    """Whether ``host`` is a Google Maps host we may follow (google.<tld>, google.co.<tld>, goo.gl)."""
    host = host.lower().rstrip(".")
    if host in SHORT_HOSTS or host == "consent.google.com":
        return True
    return bool(re.fullmatch(r"(?:(?:www|maps)\.)?google\.(?:[a-z]{2,3}|co\.[a-z]{2}|com\.[a-z]{2})", host))


def is_short_url(url: str) -> bool:
    """Whether ``url`` is a Maps short link that needs expanding."""
    host = (urlparse(url).hostname or "").lower()
    return host in SHORT_HOSTS


def expand_short_url(http: httpx.Client, url: str) -> str:
    """Follow redirects of a short link (Google hosts only) and return the final Maps URL.

    Raises:
        UnsupportedUrlError: If a redirect leaves Google or there are too many hops.
    """
    current = url
    for _ in range(MAX_REDIRECTS):
        with http.stream("GET", current, follow_redirects=False) as resp:
            location = resp.headers.get("location")
            if not resp.is_redirect or not location:
                return current
        nxt = urljoin(current, location)
        parsed = urlparse(nxt)
        if parsed.hostname == "consent.google.com":
            target = parse_qs(parsed.query).get("continue", [""])[0]
            if target:
                nxt = target
        if parsed.scheme not in ("http", "https") or not is_google_host(urlparse(nxt).hostname or ""):
            raise UnsupportedUrlError("redirect left Google Maps")
        current = nxt
        if not is_short_url(current):
            return current
    raise UnsupportedUrlError("too many redirects")


def parse_maps_url(url: str) -> ParsedMapsUrl:
    """Extract place ID, name and coordinates from a long Google Maps URL.

    Raises:
        UnsupportedUrlError: If the URL is not a Google Maps URL.
    """
    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https") or not is_google_host(parsed.hostname or ""):
        raise UnsupportedUrlError(url)
    query = parse_qs(parsed.query)
    path = unquote_plus(parsed.path)

    place_id = (query.get("query_place_id") or query.get("place_id") or [None])[0]
    name: str | None = None
    for prefix in ("/maps/place/", "/maps/search/"):
        if prefix in path:
            segment = path.split(prefix, 1)[1].split("/", 1)[0]
            if segment and not segment.startswith("@"):
                name = segment.strip()
            break
    text = (query.get("q") or query.get("query") or [None])[0]

    lat = lng = None
    m = _DATA_COORDS.search(parsed.path) or _AT_COORDS.search(parsed.path)
    if m:
        lat, lng = float(m.group(1)), float(m.group(2))
    for candidate in (text, name, (query.get("ll") or [None])[0]):
        if candidate and (pair := _COORD_PAIR.match(candidate)):
            lat, lng = float(pair.group(1)), float(pair.group(2))
    # A "name" that is just "lat,lng" carries no name.
    text = None if text and _COORD_PAIR.match(text) else text
    name = None if name and _COORD_PAIR.match(name) else name
    if not name and text:
        name = text.strip()
    return ParsedMapsUrl(place_id=place_id, name=name or None, lat=lat, lng=lng)
