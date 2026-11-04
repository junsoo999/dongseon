from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from dongseon.core.config import Settings, get_settings
from dongseon.core.defaults import FreeTier, load_defaults
from dongseon.core.usage import (
    FreeTierExceededError,
    UnknownSkuError,
    billing_month,
    meter_call,
    month_usage,
    usage_level,
)
from dongseon.db.session import session_scope, upgrade_schema
from dongseon.main import app

from .conftest import DEFAULTS

NOW = datetime(2026, 11, 15, 12, tzinfo=UTC)
TIER = FreeTier(
    as_of=date(2026, 11, 4),
    source_url="https://example.com/pricing",
    billing_timezone="America/Los_Angeles",
    monthly_free={"details_pro": 10, "ids_only": None},
)


def _meter(session, sku: str, units: int = 1, now: datetime = NOW):
    return meter_call(session, TIER, sku, warn_ratio=0.8, stop_ratio=1.0, units=units, now=now)


def test_usage_level_thresholds() -> None:
    assert usage_level(7, 10, warn_ratio=0.8, stop_ratio=1.0) == "ok"
    assert usage_level(8, 10, warn_ratio=0.8, stop_ratio=1.0) == "warn"
    assert usage_level(10, 10, warn_ratio=0.8, stop_ratio=1.0) == "stop"
    assert usage_level(10**9, None, warn_ratio=0.8, stop_ratio=1.0) == "ok"


def test_billing_month_uses_google_timezone() -> None:
    # 2026-12-01 03:00 UTC is still November in Pacific time
    assert billing_month(TIER, datetime(2026, 12, 1, 3, tzinfo=UTC)) == "2026-11"


def test_meter_counts_until_cap_then_blocks(engine: Engine) -> None:
    with session_scope(engine) as s:
        for _ in range(7):
            assert _meter(s, "details_pro").level == "ok"
        assert _meter(s, "details_pro").level == "warn"
        _meter(s, "details_pro")
        assert _meter(s, "details_pro").level == "stop"  # the 10th call is still within the cap
        with pytest.raises(FreeTierExceededError):
            _meter(s, "details_pro")
    with session_scope(engine) as s:
        _, rows = month_usage(s, TIER, warn_ratio=0.8, stop_ratio=1.0, now=NOW)
    assert {r.sku: r.count for r in rows} == {"details_pro": 10, "ids_only": 0}


def test_meter_blocks_multi_unit_request_that_would_cross_cap(engine: Engine) -> None:
    with session_scope(engine) as s:
        _meter(s, "details_pro", units=6)
        with pytest.raises(FreeTierExceededError):
            _meter(s, "details_pro", units=5)
        assert _meter(s, "details_pro", units=4).count == 10


def test_meter_resets_each_month_and_never_blocks_uncapped(engine: Engine) -> None:
    with session_scope(engine) as s:
        _meter(s, "details_pro", units=10)
        assert _meter(s, "details_pro", now=datetime(2026, 12, 15, tzinfo=UTC)).count == 1
        assert _meter(s, "ids_only", units=100_000).level == "ok"


def test_meter_rejects_unknown_sku(engine: Engine) -> None:
    with session_scope(engine) as s, pytest.raises(UnknownSkuError):
        _meter(s, "nope")


def test_repo_defaults_parse() -> None:
    tier = load_defaults(DEFAULTS).google_free_tier
    assert tier.monthly_free["places_text_search_ids_only"] is None
    assert all(cap is None or cap > 0 for cap in tier.monthly_free.values())


def test_usage_endpoint_lists_every_sku(tmp_path: Path) -> None:
    db = tmp_path / "u.db"
    upgrade_schema(db)
    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None, database_path=str(db))  # pyright: ignore[reportCallIssue]
    try:
        body = TestClient(app).get("/api/usage").json()
    finally:
        app.dependency_overrides.clear()
    assert body["warn_ratio"] == 0.8
    skus = {r["sku"]: r for r in body["skus"]}
    assert skus["places_details_pro"] == {"sku": "places_details_pro", "count": 0, "cap": 5000, "level": "ok"}
