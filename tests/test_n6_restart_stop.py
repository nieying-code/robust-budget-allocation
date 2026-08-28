"""Read-only stop-evidence checks; do not repair or relaunch the blocked entry."""

from copy import deepcopy
import hashlib
import json
from types import SimpleNamespace
import xml.etree.ElementTree as ET

import pytest

from robust_budget_allocation.io.hashing import canonical_json_sha256
from robust_budget_allocation.pilot.configuration import ROOT, PROTOCOL_SHA, CONFIG_SHA
from robust_budget_allocation.pilot.replay import load_bundle, verify_source
from robust_budget_allocation.pilot.storage import check_seal
from robust_budget_allocation.pilot import source_archive, restart

PROOF = load_bundle(ROOT / "docs/evidence/N6_RESTART_STOP.json.gz")


def test_prelaunch_stop_is_not_a_completed_scientific_batch():
    check_seal(PROOF, "evidence_sha256")
    assert PROOF["state"] == "N6_BLOCKED"
    assert PROOF["actual_scientific_runs"] == PROOF["paired_runs"] == PROOF["retries"] == 0
    assert PROOF["planned_runs"] == PROOF["unattempted_runs"] == 80
    assert PROOF["launch_invocations"] == PROOF["entry_failures"] == 1
    assert PROOF["batch_directory_created"] is False
    assert PROOF["n7_authorized"] is False
    assert PROOF["governance"]["scientific_approval"] is False


def test_gate_source_and_all_raw_xml_are_authenticated():
    gate = PROOF["gates"]
    check_seal(gate)
    assert gate["status"] == "PASS" and gate["source"] == PROOF["intended_source"]
    assert gate["protocol_sha256"] == PROTOCOL_SHA and gate["config_sha256"] == CONFIG_SHA
    raw = PROOF["gate_files"]
    assert hashlib.sha256(raw["gates.json"].encode()).hexdigest() == PROOF["gate_file_sha256"]
    assert json.loads(raw["gates.json"]) == gate
    assert set(raw) == {"gates.json", "solver-free.xml", "licensed.xml", "windows-stress.xml"}
    for name, row in gate["suites"].items():
        xml = raw[name+".xml"]
        assert hashlib.sha256(xml.encode()).hexdigest() == row["xml_sha256"]
        suites = list(ET.fromstring(xml).iter("testsuite"))
        for key in ("tests", "failures", "errors", "skipped"):
            assert sum(int(s.attrib.get(key, 0)) for s in suites) == row[key]
        assert row["returncode"] == row["failures"] == row["errors"] == row["skipped"] == 0
    assert {k: v["tests"] for k, v in gate["suites"].items()} == {
        "solver-free": 572, "licensed": 100, "windows-stress": 4}


def test_historical_tuple_list_failure_is_preserved_without_relaunch():
    gate = PROOF["gates"]
    in_memory = deepcopy(gate["source"])
    in_memory["git"]["untracked_paths"] = tuple(in_memory["git"]["untracked_paths"])
    assert in_memory != gate["source"]
    assert canonical_json_sha256(in_memory) == canonical_json_sha256(gate["source"])
    # Preserve the old failure, but do not claim old gates validate repaired code.
    assert PROOF["exception"]["message"] == "restart gate/source mismatch"
    assert restart.same_content(in_memory, gate["source"])


def test_intended_source_proof_in_shallow_checkout(monkeypatch):
    monkeypatch.setattr(source_archive.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=1))
    source = PROOF["intended_source"]
    assert source["git"]["commit_sha"] == "14da8abb5b0735bd5e180f1387d9b32f249fbb1d"
    assert source["git"]["tree_sha"] == "113ad6ffdfb59507b0c9064204adfbb0edf944a5"
    verify_source(source)
