"""Database engine, sessions, and schema migration helpers."""

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from typing import Any

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from dongseon.core.config import REPO_ROOT

ALEMBIC_INI = REPO_ROOT / "alembic.ini"


def make_engine(db_file: Path) -> Engine:
    """Create a SQLite engine with WAL mode, a busy timeout, and foreign keys enabled.

    Args:
        db_file: SQLite file path; parent directories are created if missing.

    Returns:
        The engine.
    """
    db_file.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{db_file}")

    @event.listens_for(engine, "connect")
    def _set_pragmas(dbapi_conn: Any, _record: Any) -> None:
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA busy_timeout=10000")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    return engine


@lru_cache
def get_engine(db_file: Path) -> Engine:
    """Return a process-wide engine for ``db_file`` (one per path)."""
    return make_engine(db_file)


def upgrade_schema(db_file: Path) -> None:
    """Apply all Alembic migrations to the given database.

    Args:
        db_file: SQLite file path.
    """
    db_file.parent.mkdir(parents=True, exist_ok=True)
    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("script_location", str(REPO_ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_file}")
    cfg.attributes["skip_logging_config"] = True  # keep the app's logging setup
    command.upgrade(cfg, "head")


@contextmanager
def session_scope(engine: Engine) -> Iterator[Session]:
    """Yield a session that commits on success and rolls back on error."""
    factory = sessionmaker(engine, expire_on_commit=False)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
