import json
from pathlib import Path

from robust_budget_allocation.io.hashing import canonical_json_sha256, sha256_file


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs/R6_B_DELIVERY_MANIFEST.json"
HASHES = ROOT / "docs/R6_B_HASHES.sha256"
CONFIG = ROOT / "configs/r6_formal_experiment_matrix_v1.json"
EXPANDED = ROOT / "configs/r6_formal_experiment_matrix_expanded_v1.json"


def test_r6b_delivery_is_bound_and_stops_before_r7():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    expanded = json.loads(EXPANDED.read_text(encoding="utf-8"))
    assert manifest["status"] == "R6_B_READY_FOR_INDEPENDENT_REVIEW"
    assert manifest["base"]["formal_ready_data_sha256"] == config["formal_ready_data_sha256"]
    assert manifest["authoritative_specification"]["config_identity_sha256"] == canonical_json_sha256(config)
    assert manifest["authoritative_specification"]["matrix_identity_sha256"] == expanded["matrix_sha256"]
    assert set(manifest["execution_counts"].values()) == {0}
    assert manifest["stage_gates"] == {
        "r6_b_design_frozen": True,
        "independent_review_pending": True,
        "r7_started": False,
        "merge_authorized": False,
    }
    assert manifest["open_scientific_decisions"] == []


def test_r6b_hash_inventory_is_unique_and_valid():
    rows = [line.split("  ", 1) for line in HASHES.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == len({path for _, path in rows})
    assert len(rows) == 10
    for digest, relative in rows:
        assert len(digest) == 64 and digest == digest.lower()
        assert sha256_file(ROOT / relative) == digest
