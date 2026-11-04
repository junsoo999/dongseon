"""FastAPI application factory."""

import mimetypes
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from dongseon import __version__
from dongseon.api.routes import health, usage
from dongseon.core.config import REPO_ROOT, get_settings
from dongseon.db.session import upgrade_schema

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
    mount_frontend(app, FRONTEND_DIST)  # after the API routes so /api wins
    return app


app = create_app()
