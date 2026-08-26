"""Cross-process locks with bounded waiting and safe stale-file behavior."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from filelock import FileLock, Timeout


@contextmanager
def exclusive_file_lock(path: Path, *, timeout_seconds: float = 60.0) -> Iterator[None]:
    if timeout_seconds < 0:
        raise ValueError("lock timeout must be nonnegative")
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = FileLock(str(path), timeout=timeout_seconds)
    try:
        with lock:
            yield
    except Timeout as exc:
        raise TimeoutError(f"timed out waiting for lock: {path}") from exc
