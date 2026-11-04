"""Shared FastAPI dependencies."""

from collections.abc import Iterator
from typing import Annotated

import httpx
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from dongseon.core.config import Settings, get_settings
from dongseon.core.defaults import Defaults, load_defaults
from dongseon.core.usage import make_meter
from dongseon.db.session import get_engine, session_scope
from dongseon.sources.google_places import GooglePlacesClient

HTTP_TIMEOUT_S = 15.0


def get_session(settings: Annotated[Settings, Depends(get_settings)]) -> Iterator[Session]:
    """Yield a session on the configured database (commits on success)."""
    with session_scope(get_engine(settings.database_file)) as session:
        yield session


def get_defaults(settings: Annotated[Settings, Depends(get_settings)]) -> Defaults:
    """Load ``config/defaults.yaml``."""
    return load_defaults(settings.defaults_file)


def get_http() -> Iterator[httpx.Client]:
    """Yield an HTTP client for outbound calls (overridden in tests)."""
    with httpx.Client(timeout=HTTP_TIMEOUT_S) as client:
        yield client


SessionDep = Annotated[Session, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
DefaultsDep = Annotated[Defaults, Depends(get_defaults)]
HttpDep = Annotated[httpx.Client, Depends(get_http)]


def get_places_client(
    session: SessionDep, settings: SettingsDep, defaults: DefaultsDep, http: HttpDep
) -> GooglePlacesClient:
    """Places client with free-tier metering; 503 when the server key is missing."""
    if not settings.google_maps_server_key:
        raise HTTPException(status_code=503, detail="GOOGLE_MAPS_SERVER_KEY가 설정되지 않았습니다")
    meter = make_meter(
        session,
        defaults.google_free_tier,
        warn_ratio=settings.google_free_tier_warn_ratio,
        stop_ratio=settings.google_free_tier_stop_ratio,
    )
    return GooglePlacesClient(http, settings.google_maps_server_key, meter)


PlacesDep = Annotated[GooglePlacesClient, Depends(get_places_client)]
