from __future__ import annotations

import hashlib
from pathlib import Path


def test_frozen_n0_design_hashes() -> None:
    docs = Path(__file__).resolve().parents[1] / "docs"
    manifest = docs / "N0_DESIGN_HASHES.sha256"
    for line in manifest.read_text(encoding="utf-8").splitlines():
        expected, filename = line.split(maxsplit=1)
        actual = hashlib.sha256((docs / filename).read_bytes()).hexdigest()
        assert actual == expected, filename
