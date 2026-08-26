from pathlib import Path

from robust_budget_allocation.io.hashing import sha256_file


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs" / "N1_MIGRATION_HASHES.sha256"


def test_n1_migration_hash_manifest() -> None:
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        expected, relative = line.split("  ", maxsplit=1)
        assert sha256_file(ROOT / relative) == expected, relative
