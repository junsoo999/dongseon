from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from dongseon import __version__
from dongseon.core.config import REPO_ROOT, Settings, get_settings
from dongseon.db.models import JobLog
from dongseon.db.session import get_engine, session_scope, upgrade_schema
from dongseon.main import app, mount_frontend


def _settings(**kwargs: object) -> Settings:
    return Settings(_env_file=None, **kwargs)  # pyright: ignore[reportCallIssue]


def test_health_ok() -> None:
    resp = TestClient(app).get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["version"] == __version__
    assert set(body["keys"]) == {"google_maps_server", "google_maps_js", "google_map_id"}
    assert all(isinstance(v, bool) for v in body["keys"].values())


def test_health_does_not_leak_keys() -> None:
    app.dependency_overrides[get_settings] = lambda: _settings(google_maps_server_key="AIza-secret-value")
    try:
        resp = TestClient(app).get("/api/health")
    finally:
        app.dependency_overrides.clear()
    assert "AIza-secret-value" not in resp.text
    assert resp.json()["keys"]["google_maps_server"] is True


def test_relative_paths_resolve_from_repo_root() -> None:
    assert _settings(database_path="data/x.db").database_file == REPO_ROOT / "data" / "x.db"


def test_absolute_paths_are_kept(tmp_path: Path) -> None:
    db = tmp_path / "y.db"
    assert _settings(database_path=str(db)).database_file == db


def test_default_ports_do_not_clash_with_jipsa() -> None:
    s = _settings()
    assert (s.dongseon_port, s.dongseon_dev_port) == (8100, 8101)


def test_health_reports_last_successful_daily(tmp_path: Path) -> None:
    db = tmp_path / "h.db"
    upgrade_schema(db)
    with session_scope(get_engine(db)) as s:
        s.add(JobLog(job="daily", key="", status="ok", rows=0, ran_at=datetime(2026, 11, 1, tzinfo=UTC)))
        s.add(JobLog(job="daily", key="x", status="error", rows=0, ran_at=datetime(2026, 11, 2, tzinfo=UTC)))
    app.dependency_overrides[get_settings] = lambda: _settings(database_path=str(db))
    try:
        body = TestClient(app).get("/api/health").json()
    finally:
        app.dependency_overrides.clear()
    assert body["database_exists"] is True
    assert body["last_daily_at"].startswith("2026-11-01")


def test_spa_fallback_serves_index_but_not_for_api(tmp_path: Path) -> None:
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<html>spa</html>")
    (tmp_path / "assets" / "app.js").write_text("console.log(1)")
    (tmp_path / "manifest.webmanifest").write_text('{"name": "dongseon"}')
    spa = FastAPI()
    mount_frontend(spa, tmp_path)
    c = TestClient(spa)
    assert c.get("/itinerary/3").text == "<html>spa</html>"
    assert c.get("/assets/app.js").text == "console.log(1)"
    assert c.get("/manifest.webmanifest").headers["content-type"].startswith("application/manifest+json")
    assert c.get("/api/nope").status_code == 404
    assert c.get("/../pyproject.toml").text == "<html>spa</html>"


def test_startup_creates_schema_so_usage_works_on_a_fresh_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = tmp_path / "fresh.db"
    monkeypatch.setenv("DATABASE_PATH", str(db))
    get_settings.cache_clear()
    try:
        with TestClient(app) as client:
            resp = client.get("/api/usage")
    finally:
        get_settings.cache_clear()
    assert resp.status_code == 200
    assert db.exists()
