"""R4 delivery replay and hash-inventory checks."""

import json
from pathlib import Path

from robust_budget_allocation.algorithms.qfr_a1_verification import validate_r4_evidence
from robust_budget_allocation.io.hashing import sha256_file


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs/evidence/R4_A1_INITIAL_MEMORY_TRAJECTORY_v2.json"
HASHES = ROOT / "docs/R4_CORRECTNESS_HASHES.sha256"


def test_r4_final_evidence_replays_and_applies_memory_rule():
    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    result = validate_r4_evidence(ROOT, evidence)
    assert result["status"] == "PASS"
    assert result["memory_decision"] == "MEMORY_VALUE_NOT_IDENTIFIED_NONBLOCKING"
    assert evidence["summary"]["memory_opportunities"] == 0
    assert evidence["summary"]["memory_hits"] == 0


def test_r4_hash_inventory_is_complete_and_valid():
    rows = []
    for line in HASHES.read_text(encoding="utf-8").splitlines():
        digest, relative = line.split("  ", 1)
        rows.append((digest, relative))
    assert len(rows) == len({relative for _, relative in rows})
    for digest, relative in rows:
        assert len(digest) == 64
        assert sha256_file(ROOT / relative) == digest
