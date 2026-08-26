"""Cross-platform atomic text, JSON, and CSV writes."""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path
from time import sleep
from typing import Any, Iterable, Mapping, Sequence
from uuid import uuid4


ATOMIC_REPLACE_MAX_ATTEMPTS = 20
ATOMIC_REPLACE_RETRY_SECONDS = 0.05


def _temporary_path(destination: Path) -> Path:
    return destination.with_name(f".{destination.name}.tmp-{os.getpid()}-{uuid4().hex}")


def _replace_with_retry(temporary: Path, destination: Path) -> None:
    for attempt in range(ATOMIC_REPLACE_MAX_ATTEMPTS):
        try:
            os.replace(temporary, destination)
            return
        except PermissionError:
            if attempt + 1 == ATOMIC_REPLACE_MAX_ATTEMPTS:
                raise
            sleep(ATOMIC_REPLACE_RETRY_SECONDS)


def _cleanup(path: Path) -> None:
    if path.exists():
        try:
            path.unlink()
        except OSError:
            pass


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = _temporary_path(path)
    try:
        temporary.write_text(text, encoding="utf-8", newline="\n")
        _replace_with_retry(temporary, path)
    finally:
        _cleanup(temporary)


def atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    text = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
        allow_nan=False,
    )
    atomic_write_text(path, text + "\n")


def atomic_write_csv(
    path: Path,
    fieldnames: Sequence[str],
    rows: Iterable[Mapping[str, Any]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = _temporary_path(path)
    try:
        with temporary.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
        _replace_with_retry(temporary, path)
    finally:
        _cleanup(temporary)
