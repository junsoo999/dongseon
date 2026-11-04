"""Google API usage meter: counts calls per SKU per billing month and enforces free-tier ratios.

Call :func:`meter_call` right before each billable Google request. It increments the month's counter
in ``api_usage`` and raises :class:`FreeTierExceededError` instead when the call would cross the stop ratio.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from dongseon.core.defaults import FreeTier
from dongseon.db.models import ApiUsage

logger = logging.getLogger(__name__)

UsageLevel = Literal["ok", "warn", "stop"]


class FreeTierExceededError(RuntimeError):
    """Raised when a call would push a SKU past the configured share of its monthly free cap."""

    def __init__(self, sku: str, count: int, cap: int) -> None:
        """Store the SKU and its counts."""
        super().__init__(f"{sku}: {count}/{cap} calls this month")
        self.sku = sku
        self.count = count
        self.cap = cap


class UnknownSkuError(KeyError):
    """Raised for a SKU missing from ``google_free_tier.monthly_free`` (a programming or config error)."""


@dataclass(frozen=True)
class SkuUsage:
    """One SKU's usage this month."""

    sku: str
    count: int
    cap: int | None
    level: UsageLevel


def billing_month(tier: FreeTier, now: datetime | None = None) -> str:
    """Return the ``YYYY-MM`` billing month in Google's billing timezone."""
    now = now or datetime.now(UTC)
    return now.astimezone(ZoneInfo(tier.billing_timezone)).strftime("%Y-%m")


def usage_level(count: int, cap: int | None, *, warn_ratio: float, stop_ratio: float) -> UsageLevel:
    """Classify a monthly count against its free cap."""
    if cap is None:
        return "ok"
    if count >= cap * stop_ratio:
        return "stop"
    if count >= cap * warn_ratio:
        return "warn"
    return "ok"


def meter_call(
    session: Session,
    tier: FreeTier,
    sku: str,
    *,
    warn_ratio: float,
    stop_ratio: float,
    units: int = 1,
    now: datetime | None = None,
) -> SkuUsage:
    """Count ``units`` billable calls for ``sku``, or refuse if that would cross the stop ratio.

    Args:
        session: DB session; the caller commits.
        tier: Free-tier caps from ``config/defaults.yaml``.
        sku: SKU key, e.g. ``"places_text_search_pro"``.
        warn_ratio: Share of the cap at which usage is reported as ``warn``.
        stop_ratio: Share of the cap at which calls are refused.
        units: Billable events in this request (a route matrix bills per element).
        now: Override for tests.

    Returns:
        The SKU's usage after counting this call.

    Raises:
        UnknownSkuError: If ``sku`` is not configured.
        FreeTierExceededError: If the call would exceed ``cap * stop_ratio``.
    """
    if sku not in tier.monthly_free:
        raise UnknownSkuError(sku)
    cap = tier.monthly_free[sku]
    month = billing_month(tier, now)
    row = session.scalar(select(ApiUsage).where(ApiUsage.month == month, ApiUsage.sku == sku))
    if row is None:
        row = ApiUsage(month=month, sku=sku, count=0)
        session.add(row)
    if cap is not None and row.count + units > cap * stop_ratio:
        raise FreeTierExceededError(sku, row.count, cap)
    row.count += units
    session.flush()
    level = usage_level(row.count, cap, warn_ratio=warn_ratio, stop_ratio=stop_ratio)
    if level == "warn":
        logger.warning("Google %s usage at %d/%s this month", sku, row.count, cap)
    return SkuUsage(sku=sku, count=row.count, cap=cap, level=level)


def month_usage(
    session: Session,
    tier: FreeTier,
    *,
    warn_ratio: float,
    stop_ratio: float,
    now: datetime | None = None,
) -> tuple[str, list[SkuUsage]]:
    """Return this billing month and every configured SKU's usage (zero for unused SKUs)."""
    month = billing_month(tier, now)
    rows = session.scalars(select(ApiUsage).where(ApiUsage.month == month))
    counts = {row.sku: row.count for row in rows}
    return month, [
        SkuUsage(
            sku=sku,
            count=counts.get(sku, 0),
            cap=cap,
            level=usage_level(counts.get(sku, 0), cap, warn_ratio=warn_ratio, stop_ratio=stop_ratio),
        )
        for sku, cap in tier.monthly_free.items()
    ]


def make_meter(session: Session, tier: FreeTier, *, warn_ratio: float, stop_ratio: float) -> Callable[[str], None]:
    """Return a meter that counts each call in ``session`` and commits right away.

    Committing per call keeps calls that Google already billed even if the caller fails later. It uses the
    caller's session because SQLite allows one writer: a second connection would wait on the caller's lock.
    The commit also persists the caller's pending writes, which every caller here tolerates.
    """

    def meter(sku: str) -> None:
        meter_call(session, tier, sku, warn_ratio=warn_ratio, stop_ratio=stop_ratio)
        session.commit()

    return meter
