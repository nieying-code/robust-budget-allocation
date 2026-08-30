import json
from pathlib import Path

from robust_budget_allocation.algorithms.qfr_revision_suite import validate_revision_evidence
from robust_budget_allocation.io.hashing import sha256_file


ROOT = Path(__file__).resolve().parents[1]
HASHES = ROOT / "docs/QFR_AVAILABILITY_HASHES_v2_1.sha256"
MANIFEST = ROOT / "docs/QFR_AVAILABILITY_DELIVERY_MANIFEST_v2_1.json"
EVIDENCE = ROOT / "docs/evidence/QFR_AVAILABILITY_CORRECTNESS_FIRST_RUN_v2_1.json"


def test_revision_hash_inventory_is_complete_and_valid():
    rows = [line.split("  ", 1) for line in HASHES.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == len({path for _, path in rows})
    for digest, relative in rows:
        assert len(digest) == 64 and digest == digest.lower()
        assert sha256_file(ROOT / relative) == digest


def test_revision_manifest_preserves_scope_and_results():
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert payload["status"] == "READY_FOR_INDEPENDENT_REVIEW"
    assert payload["scientific_revision"]["fixed_budget_and_objective_changed"] is False
    assert payload["pilot_configuration"]["executed"] is False
    assert payload["correctness"]["maximum_feasibility_violation"] == 0.0
    assert payload["execution_counts"] == {
        "scientific_runs": 0,
        "pilot_runs": 0,
        "formal_experiments": 0,
        "oos_runs": 0,
    }


def test_revision_final_evidence_replays():
    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    result = validate_revision_evidence(ROOT, evidence)
    assert result["status"] == "PASS"
    assert result["case_count"] == 3
