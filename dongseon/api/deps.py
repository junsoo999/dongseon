"""Shared FastAPI dependencies."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from dongseon.core.config import Settings, get_settings
from dongseon.db.session import get_engine, session_scope


def get_session(settings: Annotated[Settings, Depends(get_settings)]) -> Iterator[Session]:
    """Yield a session on the configured database (commits on success)."""
    with session_scope(get_engine(settings.database_file)) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
