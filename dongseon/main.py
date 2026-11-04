"""FastAPI application factory."""

import mimetypes
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from dongseon import __version__
from dongseon.api.routes import flights, health, jobs, places, prices, scout, stays, trips, usage
from dongseon.core.config import REPO_ROOT, get_settings
from dongseon.core.usage import FreeTierExceededError
from dongseon.db.session import upgrade_schema
from dongseon.sources.google_places import PlacesAuthError, PlacesError

FRONTEND_DIST = REPO_ROOT / "frontend" / "dist"
mimetypes.add_type("application/manifest+json", ".webmanifest")


def mount_frontend(app: FastAPI, dist: Path) -> None:
    """Serve the built SPA: static assets plus ``index.html`` for every non-API path."""
    index = dist / "index.html"
    if not index.exists():
        return
    if (dist / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        if path.startswith("api/"):
            raise HTTPException(status_code=404)
        candidate = (dist / path).resolve()
        if path and candidate.is_file() and dist.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(index)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Bring the database schema up to date before serving (the API writes trips, pins and edits)."""
    upgrade_schema(get_settings().database_file)
    yield


def add_error_handlers(app: FastAPI) -> None:
    """Translate external-service errors into short Korean messages."""

    @app.exception_handler(FreeTierExceededError)
    def _free_tier(_req: Request, exc: FreeTierExceededError) -> JSONResponse:
        return JSONResponse(
            status_code=429,
            content={
                "detail": f"Google 무료 한도에 가까워 호출을 막았습니다 ({exc.sku}, 이번 달 {exc.count}/{exc.cap})"
            },
        )

    @app.exception_handler(PlacesAuthError)
    def _auth(_req: Request, _exc: PlacesAuthError) -> JSONResponse:
        return JSONResponse(status_code=502, content={"detail": "Google 서버 키가 거부되었습니다 (키·API 제한 확인)"})

    @app.exception_handler(PlacesError)
    def _places(_req: Request, exc: PlacesError) -> JSONResponse:
        return JSONResponse(status_code=502, content={"detail": f"Google Places 오류 ({exc.status_code})"})


def create_app() -> FastAPI:
    """Create the API application with all routers mounted under ``/api``."""
    app = FastAPI(title="dongseon", version=__version__, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5174", "http://127.0.0.1:5174"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router, prefix="/api")
    app.include_router(usage.router, prefix="/api")
    app.include_router(trips.router, prefix="/api")
    app.include_router(places.router, prefix="/api")
    app.include_router(stays.router, prefix="/api")
    app.include_router(flights.router, prefix="/api")
    app.include_router(scout.router, prefix="/api")
    app.include_router(prices.router, prefix="/api")
    app.include_router(jobs.router, prefix="/api")
    add_error_handlers(app)
    mount_frontend(app, FRONTEND_DIST)  # after the API routes so /api wins
    return app


app = create_app()
