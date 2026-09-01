import json
from pathlib import Path

from robust_budget_allocation.io.hashing import canonical_json_sha256, sha256_file


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs/R6_C_DELIVERY_MANIFEST.json"
HASHES = ROOT / "docs/R6_C_HASHES.sha256"


def test_r6c_manifest_is_identity_bound_and_zero_run():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    authority = manifest["authoritative_specification"]
    ready = json.loads((ROOT / authority["formal_ready_data_path"]).read_text(encoding="utf-8"))
    config = json.loads((ROOT / authority["matrix_config_path"]).read_text(encoding="utf-8"))
    matrix = json.loads((ROOT / authority["expanded_matrix_path"]).read_text(encoding="utf-8"))
    revision = json.loads((ROOT / authority["revision_config_path"]).read_text(encoding="utf-8"))
    assert manifest["status"] == "R6_C_READY_FOR_INDEPENDENT_REVIEW"
    assert authority["formal_ready_data_sha256"] == ready["data_sha256"]
    assert authority["scenario_sha256"] == ready["scenario_sha256"]
    assert authority["revision_config_identity_sha256"] == canonical_json_sha256(revision)
    assert authority["matrix_config_identity_sha256"] == canonical_json_sha256(config)
    assert authority["expanded_matrix_identity_sha256"] == matrix["matrix_sha256"]
    assert authority["human_spec_sha256"] == sha256_file(ROOT / authority["human_spec_path"])
    assert set(manifest["execution_counts"].values()) == {0}
    assert manifest["open_scientific_decisions"] == manifest["deviations"] == manifest["identity_mismatches"] == []


def test_r6c_hash_inventory_is_unique_and_valid():
    rows = [line.split("  ", 1) for line in HASHES.read_text(encoding="utf-8").splitlines()]
    assert rows and len(rows) == len({path for _, path in rows})
    for digest, relative in rows:
        assert len(digest) == 64 and digest == digest.lower()
        assert sha256_file(ROOT / relative) == digest
