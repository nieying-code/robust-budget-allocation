import hashlib
import json
from pathlib import Path

import pytest

from robust_budget_allocation.io import atomic
from robust_budget_allocation.io.atomic import atomic_write_csv, atomic_write_json, atomic_write_text
from robust_budget_allocation.io.hashing import (
    canonical_json_bytes,
    canonical_json_sha256,
    sha256_file,
    sha256_lf_text_file,
)


def test_atomic_text_json_and_csv(tmp_path: Path) -> None:
    text_path = tmp_path / "nested" / "value.txt"
    atomic_write_text(text_path, "alpha\nbeta\n")
    assert text_path.read_bytes() == b"alpha\nbeta\n"

    json_path = tmp_path / "value.json"
    atomic_write_json(json_path, {"b": 2, "a": 1})
    assert json.loads(json_path.read_text(encoding="utf-8")) == {"a": 1, "b": 2}

    csv_path = tmp_path / "value.csv"
    atomic_write_csv(csv_path, ("x", "y"), ({"x": 1, "y": 2},))
    assert csv_path.read_bytes() == b"x,y\n1,2\n"


def test_interrupted_atomic_write_preserves_destination(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    destination = tmp_path / "value.txt"
    destination.write_text("old", encoding="utf-8")

    def fail_replace(_temporary: Path, _destination: Path) -> None:
        raise OSError("interrupted")

    monkeypatch.setattr(atomic, "_replace_with_retry", fail_replace)
    with pytest.raises(OSError, match="interrupted"):
        atomic_write_text(destination, "new")
    assert destination.read_text(encoding="utf-8") == "old"
    assert not tuple(tmp_path.glob(".*.tmp-*"))


def test_hashes_and_canonical_json_are_deterministic(tmp_path: Path) -> None:
    left = {"z": [2, 1], "a": "值"}
    right = {"a": "值", "z": [2, 1]}
    assert canonical_json_bytes(left) == canonical_json_bytes(right)
    assert canonical_json_sha256(left) == canonical_json_sha256(right)
    path = tmp_path / "data.txt"
    path.write_bytes(b"alpha\n")
    expected = hashlib.sha256(b"alpha\n").hexdigest()
    assert sha256_file(path) == expected
    assert sha256_lf_text_file(path) == expected
    path.write_bytes(b"alpha\r\n")
    with pytest.raises(ValueError, match="LF-only"):
        sha256_lf_text_file(path)
