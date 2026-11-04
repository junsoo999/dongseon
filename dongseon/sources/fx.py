"""Reference exchange rates from Frankfurter (ECB data, no key). Fetched at most once a day per pair."""

from dataclasses import dataclass
from datetime import UTC, date, datetime

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from dongseon.db.models import FxRate
from dongseon.sources.http import send_with_retry

FRANKFURTER_URL = "https://api.frankfurter.dev/v1/latest"
SOURCE_LABEL = "ECB 기준환율 (Frankfurter)"


@dataclass(frozen=True)
class Rate:
    """``1 base = rate quote`` as published on ``date``."""

    base: str
    quote: str
    rate: float
    date: date


def fetch_latest(http: httpx.Client, base: str, quote: str) -> Rate:
    """Fetch the latest published rate.

    Raises:
        httpx.HTTPError: On network errors or a non-2xx response.
    """
    resp = send_with_retry(lambda: http.get(FRANKFURTER_URL, params={"base": base, "symbols": quote}))
    resp.raise_for_status()
    data = resp.json()
    return Rate(
        base=data["base"], quote=quote, rate=float(data["rates"][quote]), date=date.fromisoformat(data["date"])
    )


def get_rate(session: Session, http: httpx.Client | None, base: str, quote: str = "KRW") -> Rate | None:
    """Return the newest stored rate, fetching once a day; ``None`` when nothing is stored and fetching fails."""
    if base == quote:
        return Rate(base=base, quote=quote, rate=1.0, date=datetime.now(UTC).date())
    latest = session.scalar(
        select(FxRate).where(FxRate.base == base, FxRate.quote == quote).order_by(FxRate.rate_date.desc()).limit(1)
    )
    fresh = latest is not None and latest.fetched_at.date() == datetime.now(UTC).date()
    if not fresh and http is not None:
        try:
            got = fetch_latest(http, base, quote)
        except (httpx.HTTPError, KeyError, ValueError):
            got = None
        if got is not None:
            row = session.scalar(
                select(FxRate).where(FxRate.rate_date == got.date, FxRate.base == base, FxRate.quote == quote)
            )
            if row is None:
                row = FxRate(rate_date=got.date, base=base, quote=quote, rate=got.rate, fetched_at=datetime.now(UTC))
                session.add(row)
            row.rate, row.fetched_at = got.rate, datetime.now(UTC)
            session.flush()
            latest = row
    if latest is None:
        return None
    return Rate(base=latest.base, quote=latest.quote, rate=latest.rate, date=latest.rate_date)
