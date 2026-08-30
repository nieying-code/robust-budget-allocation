import json
import os
from pathlib import Path

import pytest

from robust_budget_allocation.io.hashing import canonical_json_sha256, sha256_file
from robust_budget_allocation.pilot.qfr_r5 import validate_r5_evidence


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs/evidence/R5_QFR_PILOT_RESULTS_v2.json"
MANIFEST = ROOT / "docs/R5_DELIVERY_MANIFEST.json"
HASHES = ROOT / "docs/R5_PILOT_HASHES.sha256"


def test_r5_evidence_and_manifest_bind_the_completed_matrix():
    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    bare = dict(evidence)
    seal = bare.pop("evidence_sha256")
    assert seal == canonical_json_sha256(bare)
    assert manifest["evidence"]["file_sha256"] == sha256_file(EVIDENCE)
    assert manifest["evidence"]["evidence_sha256"] == seal
    assert manifest["pilot_matrix"]["case_count"] == len(evidence["cases"]) == 9
    assert manifest["execution_counts"] == {
        "pilot_batches": 1,
        "pilot_cases": 9,
        "formal_experiment_runs": 0,
        "oos_runs": 0,
        "a1_changes": 0,
    }


def test_r5_delivery_hash_inventory_is_complete_and_valid():
    rows = [line.split("  ", 1) for line in HASHES.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == len({path for _, path in rows})
    for digest, relative in rows:
        assert len(digest) == 64 and digest == digest.lower()
        assert sha256_file(ROOT / relative) == digest


def test_r5_final_evidence_replays_against_registered_workbook():
    value = os.environ.get("R5_WFP_WORKBOOK")
    if not value:
        pytest.skip("R5_WFP_WORKBOOK is required for local source-workbook replay")
    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    replay = validate_r5_evidence(ROOT, Path(value), evidence)
    assert replay["status"] == "PASS"
    assert replay["case_count"] == 9
