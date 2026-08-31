import json
from pathlib import Path

from robust_budget_allocation.io.hashing import sha256_file


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs/R6_DATA_DELIVERY_MANIFEST.json"
HASHES = ROOT / "docs/R6_DATA_HASHES.sha256"


def test_r6_delivery_manifest_stops_before_scientific_execution():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["status"] == "R6_DATA_STAGE_READY_FOR_REVIEW"
    assert manifest["scenario_reconstruction"] == {
        "hurricanes": 15,
        "scenarios": 51,
        "single": 15,
        "combined": 35,
        "no_hurricane": 1,
        "probability_sum": 1.0,
        "rawls_yang_cross_check": "PASS",
    }
    assert set(manifest["execution_counts"].values()) == {0}
    assert manifest["stage_gates"] == {
        "r6_b_started": False,
        "r7_started": False,
        "merge_authorized": False,
    }
    assert manifest["open_scientific_blocks"] == []


def test_r6_hash_inventory_is_unique_and_valid():
    rows = [line.split("  ", 1) for line in HASHES.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == len({path for _, path in rows})
    assert len(rows) == 12
    for digest, relative in rows:
        assert len(digest) == 64 and digest == digest.lower()
        assert sha256_file(ROOT / relative) == digest
