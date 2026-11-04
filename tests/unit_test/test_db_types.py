from datetime import UTC, datetime, timedelta, timezone

import pytest
from sqlalchemy import Engine

from dongseon.db.models import JobLog
from dongseon.db.session import session_scope


def test_datetimes_round_trip_as_utc_aware(engine: Engine) -> None:
    tokyo = timezone(timedelta(hours=9))
    with session_scope(engine) as s:
        s.add(JobLog(job="x", key="", status="ok", rows=0, ran_at=datetime(2030, 12, 28, 9, 0, tzinfo=tokyo)))
    with session_scope(engine) as s:
        row = s.query(JobLog).one()
        assert row.ran_at == datetime(2030, 12, 28, 0, 0, tzinfo=UTC)
        assert row.ran_at.tzinfo is not None


def test_naive_datetimes_are_rejected(engine: Engine) -> None:
    with pytest.raises(Exception, match="naive"), session_scope(engine) as s:
        s.add(JobLog(job="x", key="", status="ok", rows=0, ran_at=datetime(2030, 1, 1)))  # noqa: DTZ001
        s.flush()
