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


PLACES_FIXTURES = FIXTURES / "google_places"


def places_fixture(name: str) -> dict:
    import json

    return json.loads((PLACES_FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


@pytest.fixture
def api(tmp_path: Path) -> Iterator["ApiHarness"]:
    from fastapi.testclient import TestClient

    from dongseon.core.config import Settings, get_settings
    from dongseon.main import app

    db = tmp_path / "api.db"
    upgrade_schema(db)
    settings = Settings(
        _env_file=None,  # pyright: ignore[reportCallIssue]
        database_path=str(db),
        lock_dir=str(tmp_path / "locks"),
        profile_path=str(EXAMPLE_PROFILE),  # never the household's real profile
        google_maps_server_key="test-key",
    )
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        yield ApiHarness(TestClient(app), settings, db)
    finally:
        app.dependency_overrides.clear()


class ApiHarness:
    """Test client plus the settings and DB it uses."""

    def __init__(self, client, settings, db: Path) -> None:
        self.client = client
        self.settings = settings
        self.db = db

    def create_trip(self, **overrides: object) -> dict:
        body: dict[str, object] = {
            "title": "테스트 여행",
            "city_key": "tokyo",
            "start_date": "2030-12-28",
            "end_date": "2031-01-01",
        }
        body.update(overrides)
        resp = self.client.post("/api/trips", json=body)
        assert resp.status_code == 201, resp.text
        return resp.json()
