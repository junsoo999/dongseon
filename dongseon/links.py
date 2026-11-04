"""Search deep links with route, dates and travelers filled in (no scraping: the user opens them)."""

from dataclasses import dataclass
from datetime import date
from urllib.parse import quote, urlencode


@dataclass(frozen=True)
class Link:
    """A labeled outbound link."""

    site: str
    label: str
    url: str


def flight_links(origin: str, city_code: str, start: date, end: date, adults: int) -> list[Link]:
    """Round-trip flight searches on Google Flights and Naver."""
    q = f"Flights from {origin} to {city_code} on {start.isoformat()} through {end.isoformat()} for {adults} adults"
    google = "https://www.google.com/travel/flights?" + urlencode({"q": q, "hl": "ko", "curr": "KRW"})
    naver = (
        f"https://flight.naver.com/flights/international/{origin}-{city_code}-{start:%Y%m%d}/"
        f"{city_code}-{origin}-{end:%Y%m%d}?" + urlencode({"adult": adults, "fareType": "Y"})
    )
    return [
        Link("google_flights", f"Google 항공권 {origin}→{city_code}", google),
        Link("naver", f"네이버 항공권 {origin}→{city_code}", naver),
    ]


def stay_links(area_query: str, city_name_en: str, check_in: date, check_out: date, adults: int) -> list[Link]:
    """Airbnb and Booking.com searches for one area."""
    place = f"{area_query}, {city_name_en}"
    airbnb = f"https://www.airbnb.co.kr/s/{quote(place.replace(', ', '--'))}/homes?" + urlencode(
        {"checkin": check_in.isoformat(), "checkout": check_out.isoformat(), "adults": adults}
    )
    booking = "https://www.booking.com/searchresults.ko.html?" + urlencode(
        {
            "ss": place,
            "checkin": check_in.isoformat(),
            "checkout": check_out.isoformat(),
            "group_adults": adults,
            "no_rooms": 1,
        }
    )
    return [Link("airbnb", "에어비앤비", airbnb), Link("booking", "부킹닷컴", booking)]
