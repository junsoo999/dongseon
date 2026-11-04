"""Google API usage per SKU for the current billing month."""

from datetime import date
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from dongseon.api.deps import SessionDep, SettingsDep
from dongseon.core.defaults import load_defaults
from dongseon.core.usage import month_usage

router = APIRouter(tags=["usage"])


class SkuUsageOut(BaseModel):
    """One SKU's calls this month against its free cap (``cap`` is null when Google sets none)."""

    sku: str
    count: int
    cap: int | None
    level: Literal["ok", "warn", "stop"]


class UsageResponse(BaseModel):
    """This billing month's Google usage."""

    month: str
    warn_ratio: float
    stop_ratio: float
    caps_as_of: date
    caps_source_url: str
    skus: list[SkuUsageOut]


@router.get("/usage", response_model=UsageResponse)
def usage(session: SessionDep, settings: SettingsDep) -> UsageResponse:
    """Return every configured SKU's call count for the current billing month."""
    tier = load_defaults(settings.defaults_file).google_free_tier
    warn, stop = settings.google_free_tier_warn_ratio, settings.google_free_tier_stop_ratio
    month, rows = month_usage(session, tier, warn_ratio=warn, stop_ratio=stop)
    return UsageResponse(
        month=month,
        warn_ratio=warn,
        stop_ratio=stop,
        caps_as_of=tier.as_of,
        caps_source_url=tier.source_url,
        skus=[SkuUsageOut(sku=r.sku, count=r.count, cap=r.cap, level=r.level) for r in rows],
    )
