"""Read a pasted booking email (``booking_parse``) into a flight or stay draft the user confirms before saving.

The text is masked first (card numbers, passport numbers, birth dates, emails, phone numbers) and never stored;
only the masked text reaches the model, with no tools. The result is a draft, not a saved row.
"""

import datetime as dt
import re
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from dongseon.llm.claude_cli import ClaudeCli, LlmError, load_prompt

PROMPT = "booking_parse_v1"
MAX_CHARS = 20_000
TIMEOUT_S = 180

_DATE = (
    r"(?:\d{4}\s*[-./년]\s*\d{1,2}\s*[-./월]\s*\d{1,2}\s*일?"
    r"|\d{1,2}\s*[-./]\s*\d{1,2}\s*[-./]\s*\d{2,4}"
    r"|\d{1,2}\s*[A-Za-z]{3,9}\.?\s*\d{2,4}"
    r"|[A-Za-z]{3,9}\.?\s*\d{1,2},?\s*\d{4})"
)
_BIRTH_LINE = re.compile(r"(생년월일|생일|birth|\bDOB\b|date of birth)", re.IGNORECASE)
_CARD = re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)")
_PASSPORT = re.compile(r"\b[A-Z]{1,2}\d{7,8}\b")
_PASSPORT_LINE = re.compile(r"(여권|passport)", re.IGNORECASE)
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_PHONE = re.compile(r"(?<![\w])\+?\d{1,4}[ -]?\(?\d{1,4}\)?(?:[ -]?\d{3,4}){2}(?![\w])")


def _luhn(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        n = int(ch)
        if i % 2:
            n = n * 2 - 9 if n > 4 else n * 2
        total += n
    return total % 10 == 0


@dataclass
class Masked:
    """Masked text and what was masked (counts by kind)."""

    text: str
    counts: dict[str, int] = field(default_factory=dict)


def mask(text: str) -> Masked:
    """Mask card numbers, passport numbers, birth dates, emails and phone numbers."""
    counts: dict[str, int] = {}

    def sub(pattern: re.Pattern[str], label: str, s: str, check=None) -> str:
        def repl(m: re.Match[str]) -> str:
            if check and not check(m.group(0)):
                return m.group(0)
            counts[label] = counts.get(label, 0) + 1
            return f"[{label}]"

        return pattern.sub(repl, s)

    out = sub(_CARD, "카드번호", text, lambda s: _luhn(re.sub(r"\D", "", s)))
    out = sub(_EMAIL, "이메일", out)
    lines = []
    for line in out.splitlines():
        if _BIRTH_LINE.search(line):
            line = sub(re.compile(_DATE), "생년월일", line)
        if _PASSPORT_LINE.search(line):
            line = sub(re.compile(r"\b[A-Z0-9]{6,9}\b"), "여권번호", line, lambda s: any(c.isdigit() for c in s))
        lines.append(line)
    out = "\n".join(lines)
    out = sub(_PASSPORT, "여권번호", out)
    out = sub(_PHONE, "전화번호", out)
    return Masked(out, counts)


class LegDraft(BaseModel):
    """A flight leg as written in the mail (local times)."""

    direction: Literal["out", "back"]
    carrier: str | None = Field(default=None, max_length=50)
    flight_no: str | None = Field(default=None, max_length=20)
    dep_airport: str = Field(pattern=r"^[A-Z]{3}$")
    dep_local: dt.datetime
    arr_airport: str = Field(pattern=r"^[A-Z]{3}$")
    arr_local: dt.datetime


class FlightDraft(BaseModel):
    """A booked round trip."""

    label: str = Field(min_length=1, max_length=100)
    total_amount: int | None = Field(default=None, ge=0)
    currency: str = Field(default="KRW", pattern=r"^[A-Z]{3}$")
    baggage_note: str | None = Field(default=None, max_length=200)
    legs: list[LegDraft] = Field(min_length=1, max_length=8)


class StayDraft(BaseModel):
    """A booked stay; the user still picks its location."""

    name: str = Field(min_length=1, max_length=100)
    search_query: str | None = Field(default=None, max_length=100)  # name to search, e.g. the official name
    check_in: dt.date | None = None
    check_out: dt.date | None = None
    total_amount: int | None = Field(default=None, ge=0)
    currency: str = Field(default="JPY", pattern=r"^[A-Z]{3}$")


class BookingAnswer(BaseModel):
    """The model's answer."""

    kind: Literal["flight", "stay", "none"]
    flight: FlightDraft | None = None
    stay: StayDraft | None = None
    note: str | None = Field(default=None, max_length=300)


SCHEMA = BookingAnswer.model_json_schema()


@dataclass(frozen=True)
class Parsed:
    """A validated draft plus what was masked."""

    answer: BookingAnswer
    masked: dict[str, int]


def parse_booking(llm: ClaudeCli, text: str, *, trip_start: dt.date, trip_end: dt.date) -> Parsed:
    """Mask a pasted booking email and read it into a draft.

    Raises:
        LlmError: The call failed or the answer did not validate.
    """
    m = mask(text[:MAX_CHARS])
    payload = {"trip_start": trip_start.isoformat(), "trip_end": trip_end.isoformat(), "mail": m.text}
    result = llm.run("booking_parse", load_prompt(PROMPT), payload, SCHEMA, timeout=TIMEOUT_S)
    try:
        answer = BookingAnswer.model_validate(result.data)
    except ValidationError as e:
        raise LlmError(f"invalid booking output: {e.error_count()} errors") from e
    if (answer.kind == "flight" and answer.flight is None) or (answer.kind == "stay" and answer.stay is None):
        answer = BookingAnswer(kind="none", note=answer.note)
    return Parsed(answer, m.counts)
