"""Authenticate new tests-only evidence without invoking gates or pilot."""

import hashlib
from types import SimpleNamespace
import xml.etree.ElementTree as ET

from robust_budget_allocation.io.hashing import sha256_file
from robust_budget_allocation.pilot.configuration import ROOT
from robust_budget_allocation.pilot.replay import load_bundle, verify_source, anchored_inputs
from robust_budget_allocation.pilot import source_archive
from robust_budget_allocation.pilot.storage import check_seal

PROOF = load_bundle(ROOT / "docs/evidence/N6_SOURCE_COMPARISON_VALIDATION.json.gz")


def test_new_validation_is_tests_only_and_xml_counts_match():
    check_seal(PROOF, "evidence_sha256")
    assert PROOF["stage_state"] == "N6_BLOCKED"
    assert PROOF["new_scientific_runs"] == 0
    for key in ("pilot_relaunch_authorized", "n7_authorized", "actual_pilot_batch_exists",
                "old_gates_used_as_repair_validation", "licensed_tests_run_this_validation"):
        assert PROOF[key] is False
    suite = PROOF["suite"]
    assert hashlib.sha256(suite["raw_xml"].encode()).hexdigest() == suite["xml_sha256"]
    root = ET.fromstring(suite["raw_xml"])
    for key in ("tests", "failures", "errors", "skipped"):
        assert sum(int(row.attrib.get(key, 0)) for row in root.iter("testsuite")) == suite[key]
    assert suite["tests"] == 601 and suite["deselected"] == 100
    assert suite["failures"] == suite["errors"] == suite["skipped"] == 0
    cases = [row for row in root.iter("testcase")
             if row.attrib["classname"] == "tests.test_n6_restart"]
    assert len(cases) == PROOF["restart_integration_test_count"] == 35


def test_repair_source_proof_is_independent_of_old_gate_and_git_history(monkeypatch):
    source = PROOF["tested_source"]
    assert source["git"]["commit_sha"] == "5bef2fc11630defac829835d0bc4775be0d1b92c"
    assert source["git"]["tree_sha"] == "ba9e6fd8757d01e244565c94e9f50e09681b6418"
    old = load_bundle(ROOT / "docs/evidence/N6_RESTART_STOP.json.gz")
    assert source["git"]["commit_sha"] != old["gates"]["source"]["git"]["commit_sha"]
    monkeypatch.setattr(source_archive.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=1))
    monkeypatch.setattr(source_archive, "archive_objects", lambda: PROOF["git_objects"]["objects"])
    anchored_inputs.cache_clear()
    verify_source(source)  # Real Git-object ID, seal and complete inventory verification.


def test_all_historical_archives_remain_byte_identical():
    for name, digest in PROOF["historical_hashes"].items():
        if name.startswith("docs/"):
            assert sha256_file(ROOT / name) == digest
    old = load_bundle(ROOT / "docs/evidence/N6_RESTART_STOP.json.gz")
    assert PROOF["historical_hashes"]["outputs/harness-validation/n6pilot02/gates.json"] == old["gate_file_sha256"]
