from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import Engine

from dongseon.core.config import REPO_ROOT
from dongseon.db.session import make_engine, upgrade_schema

FIXTURES = Path(__file__).parent / "fixtures"
EXAMPLE_PROFILE = REPO_ROOT / "config" / "profile.example.yaml"
DEFAULTS = REPO_ROOT / "config" / "defaults.yaml"
CITIES = REPO_ROOT / "config" / "cities"


@pytest.fixture
def engine(tmp_path: Path) -> Iterator[Engine]:
    db = tmp_path / "test.db"
    upgrade_schema(db)
    eng = make_engine(db)
    yield eng
    eng.dispose()
