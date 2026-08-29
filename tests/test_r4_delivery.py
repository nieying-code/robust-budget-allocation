"""R4 delivery replay and hash-inventory checks."""

import json
from pathlib import Path

from robust_budget_allocation.algorithms.qfr_a1_verification import validate_r4_evidence
from robust_budget_allocation.io.hashing import canonical_json_sha256, sha256_file


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs/evidence/R4_A1_INITIAL_MEMORY_TRAJECTORY_v2.json"
FINAL_EVIDENCE = ROOT / "docs/evidence/R4_EF_A0_A1_CORRECTNESS_FINAL_v2.json"
HASHES = ROOT / "docs/R4_CORRECTNESS_HASHES.sha256"


def test_r4_initial_memory_trajectory_is_preserved_with_original_seal():
    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    seal = evidence.pop("evidence_sha256")
    assert seal == "4a9f14e1a5c4b98bf2611e3b68a0385d90a1d906603d321f4aaa5a84fe739123"
    assert seal == canonical_json_sha256(evidence)
    assert evidence["source"]["git"]["commit_sha"] == "4ff6c15c75a07787a8e2fa6cf4be5ce67687350a"
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


def test_r4_final_correctness_evidence_replays():
    evidence = json.loads(FINAL_EVIDENCE.read_text(encoding="utf-8"))
    result = validate_r4_evidence(ROOT, evidence)
    assert result["status"] == "PASS"
    assert result["memory_decision"] == "MEMORY_VALUE_NOT_IDENTIFIED_NONBLOCKING"
    assert evidence["source"]["git"]["commit_sha"] == "14f99cccd46871f46ea10e36b15412cadb70bddf"
