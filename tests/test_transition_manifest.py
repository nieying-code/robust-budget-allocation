"""Explicit engineering-only supersessions; frozen scientific evidence stays intact."""

import json

from robust_budget_allocation.io.hashing import sha256_file
from robust_budget_allocation.pilot.configuration import ROOT
from robust_budget_allocation.pilot.storage import safe_relative

SUPERSEDED = {
    "scripts/n6_pilot.py",
    "src/robust_budget_allocation/pilot/replay.py",
    "src/robust_budget_allocation/pilot/restart.py",
    "tests/test_n6_evidence.py",
}
ADDED = {
    "src/robust_budget_allocation/reproducibility/test_evidence.py",
    "tests/test_transition_audit_hardening.py",
    "tests/test_transition_production_entry.py",
    "tests/test_transition_manifest.py",
    "docs/TRANSITION_ENGINEERING_REPORT.md",
}


def test_exact_transition_inventory_and_current_hashes():
    manifest = json.loads((ROOT / "docs/TRANSITION_ENGINEERING_MANIFEST.json").read_text())
    assert manifest["base_commit"] == "17994d9467cb265e032b5aee1b5dc843b9ae3f7c"
    assert manifest["base_tree"] == "905d7b6d733f1a38a491bfa8662720de98058911"
    assert manifest["scientific_runs"] == 0
    assert set(manifest["superseded_engineering_files"]) == SUPERSEDED
    assert set(manifest["added_files"]) == ADDED
    historical = dict(line.split("  ", 1)[::-1] for line in
        (ROOT / "docs/N6_PILOT_HASHES.sha256").read_text().splitlines() if line)
    for path, row in manifest["superseded_engineering_files"].items():
        assert row["n6_sha256"] == historical[path]
    current = {p: r["current_sha256"] for p, r in manifest["superseded_engineering_files"].items()}
    current.update(manifest["added_files"])
    for path, digest in current.items():
        assert safe_relative(path) == path
        target = ROOT / path
        assert target.is_file() and not target.is_symlink()
        assert sha256_file(target) == digest
    assert "docs/TRANSITION_ENGINEERING_MANIFEST.json" not in current
