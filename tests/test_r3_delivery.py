import json
from pathlib import Path

from robust_budget_allocation.io.hashing import sha256_file


ROOT = Path(__file__).resolve().parents[1]
HASHES = ROOT / "docs/R3_CORRECTNESS_HASHES.sha256"
MANIFEST = ROOT / "docs/R3_DELIVERY_MANIFEST.json"
REVISION_HASHES = ROOT / "docs/QFR_AVAILABILITY_HASHES_v2_1.sha256"


def test_r3_delivery_hash_inventory_is_complete_and_valid():
    rows = []
    for line in HASHES.read_text(encoding="utf-8").splitlines():
        digest, relative = line.split("  ", 1)
        rows.append((digest, relative))
    assert len(rows) == len({relative for _, relative in rows})
    assert all(len(digest) == 64 and digest == digest.lower() for digest, _ in rows)
    revision = {
        relative: digest
        for digest, relative in (
            line.split("  ", 1)
            for line in REVISION_HASHES.read_text(encoding="utf-8").splitlines()
        )
    }
    for digest, relative in rows:
        actual = sha256_file(ROOT / relative)
        assert actual == digest or revision.get(relative) == actual


def test_r3_manifest_preserves_governance_and_scope_counts():
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert payload["base"] == {
        "commit": "d5484adff21040bdaa0aaa3e727c9d341b342e47",
        "tree": "30d3e0ed261b794de8420bd9bd1c0d9873ee4e29",
    }
    assert payload["r1_classification_counts_unchanged"] == {
        "DIRECT_REUSE": 39,
        "REUSE_WITH_MODIFICATION": 29,
        "HISTORICAL_ONLY": 85,
        "REWRITE_REQUIRED": 4,
    }
    assert payload["scope_mapping"]["DIRECT_REUSE_MODIFIED"] == []
    assert payload["scope_mapping"]["HISTORICAL_ONLY_MODIFIED"] == []
    assert payload["scope_mapping"]["REWRITE_REQUIRED_MODEL_FILES_MODIFIED"] == []
    assert payload["correctness"]["accepted_comparisons"] == 3
    assert payload["execution_counts"] == {
        "scientific_runs": 0,
        "pilot_runs": 0,
        "formal_experiments": 0,
        "a1_new_implemented": False,
    }
