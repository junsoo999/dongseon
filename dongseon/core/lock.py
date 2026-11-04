"""Per-job file locks so the same ingest job never runs twice concurrently."""

import fcntl
import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


class JobLockedError(RuntimeError):
    """Raised when another process already holds the job lock."""


@contextmanager
def job_lock(lock_dir: Path, name: str) -> Iterator[None]:
    """Hold an exclusive, non-blocking lock for ``name`` while the block runs.

    The lock is released automatically if the process dies, so stale lock files are harmless.

    Args:
        lock_dir: Directory holding lock files (created if missing).
        name: Job name, e.g. ``"ingest-trades"``.

    Raises:
        JobLockedError: If the lock is already held.
    """
    lock_dir.mkdir(parents=True, exist_ok=True)
    fd = os.open(lock_dir / f"{name}.lock", os.O_CREAT | os.O_RDWR, 0o644)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as e:
            raise JobLockedError(name) from e
        try:
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def is_locked(lock_dir: Path, name: str) -> bool:
    """Whether another process currently holds the lock for ``name``."""
    path = lock_dir / f"{name}.lock"
    if not path.exists():
        return False
    fd = os.open(path, os.O_RDWR)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        fcntl.flock(fd, fcntl.LOCK_UN)
        return False
    finally:
        os.close(fd)
