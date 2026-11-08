"""ICS (RFC 5545) export of a plan's visits for phone calendars."""

from datetime import UTC, datetime

from dongseon.export.plan import PlanExport, directions_url


def _escape(text: str) -> str:
    return (
        text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\r\n", "\n").replace("\n", "\\n")
    )


def _fold(line: str) -> str:
    """Fold a content line at 75 octets without splitting a UTF-8 character."""
    out, cur, size = [], "", 0
    for ch in line:
        n = len(ch.encode("utf-8"))
        if size + n > (75 if not out else 74):  # continuation lines start with one space
            out.append(cur)
            cur, size = "", 0
        cur += ch
        size += n
    out.append(cur)
    return "\r\n ".join(out)


def _utc(at: datetime) -> str:
    return at.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def build_ics(plan: PlanExport, now: datetime | None = None) -> str:
    """Render one VEVENT per planned visit (times in UTC, so no VTIMEZONE is needed).

    Args:
        plan: The exported plan.
        now: The DTSTAMP; defaults to the current time.

    Returns:
        The calendar text with CRLF line endings.
    """
    stamp = _utc(now or datetime.now(UTC))
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//dongseon//plan//KO",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_escape(plan.trip.title)}",
        f"X-WR-TIMEZONE:{plan.trip.timezone}",
    ]
    for day in plan.days:
        for s in day.stops:
            url = directions_url(s.label, s.google_place_id)
            desc = [x for x in (s.local_name, s.note) if x]
            desc += [f"⚠️ {w}" for w in s.warnings]
            desc += [f"시각은 dongseon 일정 v{plan.version}의 추정입니다.", f"길찾기: {url}"]
            lines += [
                "BEGIN:VEVENT",
                f"UID:dongseon-{plan.itinerary_id}-{s.item_id}@dongseon",
                f"DTSTAMP:{stamp}",
                f"DTSTART:{_utc(s.start)}",
                f"DTEND:{_utc(s.end)}",
                f"SUMMARY:{_escape(s.label)}",
                f"LOCATION:{_escape(s.local_name or s.label)}",
                f"DESCRIPTION:{_escape(chr(10).join(desc))}",
                f"URL:{url}",
                "END:VEVENT",
            ]
    lines.append("END:VCALENDAR")
    return "\r\n".join(_fold(x) for x in lines) + "\r\n"
