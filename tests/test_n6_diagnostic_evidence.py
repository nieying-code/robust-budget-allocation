"""Replay the one authorized diagnostic without launching another worker/solver."""

from copy import deepcopy
import json
from types import SimpleNamespace

import pytest

from robust_budget_allocation.io.hashing import sha256_file
from robust_budget_allocation.pilot.configuration import ROOT
from robust_budget_allocation.pilot.diagnostic import (
    PARENT_ARCHIVE, PARENT_ARCHIVE_SHA, REASON, replay_diagnostic,
)
from robust_budget_allocation.pilot.replay import load_bundle
from robust_budget_allocation.pilot.storage import seal
from robust_budget_allocation.pilot import source_archive

PATH = ROOT / "docs/evidence/N6_EF_DIAGNOSTIC_RETRY.json.gz"
EVIDENCE = load_bundle(PATH)
PARENT = json.loads(EVIDENCE["parent"]["files"]["record.json"])
RETRY = json.loads(EVIDENCE["retry"]["files"]["record.json"])


def test_single_diagnostic_pass_does_not_complete_pilot():
    assert replay_diagnostic(EVIDENCE) == dict(
        diagnostic_status="PASS", run_id="n6diagnostic01-ef-retry",
        parent_run_id="n6pilot01-00-ef", run_status="success/certified",
        parent_status="incomplete", scientific_group=False, paired_runs=0,
        n6_stage_complete=False, n7_authorized=False,
    )
    assert PARENT["certified"] is False and RETRY["certified"] is True
    assert RETRY["watchdog"]["exit_code"] == 0
    assert RETRY["watchdog"]["cleanup"]["success"] is True
    assert sha256_file(ROOT / PARENT_ARCHIVE) == PARENT_ARCHIVE_SHA


def test_same_inputs_distinct_source_and_prevalidated_code():
    assert RETRY["binding"] == PARENT["binding"]
    assert RETRY["source"]["git"]["commit_sha"] != PARENT["source"]["git"]["commit_sha"]
    assert RETRY["retry_reason"] == REASON
    validation = json.loads((ROOT / "docs/evidence/N6_HARNESS_VALIDATION.json").read_text())
    assert validation["source_input_hashes"] == RETRY["source"]["inputs"]
    assert validation["solver_free_passed"] == 550
    assert validation["licensed_passed"] == 100
    assert len(validation["windows_stress"]) == 3
    assert all(row["exit_code"] == 0 and row["lock_released"]
               for row in validation["windows_stress"])


@pytest.mark.parametrize("key,value", [
    ("scientific_group", True), ("paired_runs", 1),
    ("full_pilot_resume_authorized", True), ("n7_authorized", True),
])
def test_resealed_diagnostic_promotion_rejected(key, value):
    forged = deepcopy(EVIDENCE)
    forged[key] = value
    forged.pop("evidence_sha256")
    with pytest.raises(ValueError, match="cannot authorize"):
        replay_diagnostic(seal(forged, "evidence_sha256"))


@pytest.mark.parametrize("fault", ["reason", "parent", "lineage"])
def test_resealed_retry_lineage_forgery_rejected(fault):
    forged = deepcopy(EVIDENCE)
    if fault == "lineage":
        forged["lineage"]["parent_commit_sha"] = RETRY["source"]["git"]["commit_sha"]
    else:
        claim = forged["authorization_claim"]
        claim["retry_reason" if fault == "reason" else "parent_run_id"] = "unauthorized"
        claim.pop("sha256")
        forged["authorization_claim"] = seal(claim)
    forged.pop("evidence_sha256")
    with pytest.raises(ValueError):
        replay_diagnostic(seal(forged, "evidence_sha256"))


@pytest.mark.parametrize("record", [PARENT, RETRY], ids=["old-source", "repair-source"])
def test_both_source_proofs_work_without_git_history(monkeypatch, record):
    monkeypatch.setattr(source_archive.subprocess, "run",
                        lambda *a, **k: SimpleNamespace(returncode=1))
    git = record["source"]["git"]
    actual = source_archive.authenticate_inputs(git["commit_sha"], git["tree_sha"])
    assert actual == {row["path"]: row["sha256"] for row in record["source"]["inputs"]}


def test_diagnostic_manifest_matches_immutable_archive():
    manifest = json.loads((ROOT / "docs/evidence/N6_DIAGNOSTIC_MANIFEST.json").read_text())
    assert manifest["archive_sha256"] == sha256_file(PATH)
    assert manifest["archive_bytes"] == PATH.stat().st_size
    assert manifest["execution_commit"] == RETRY["source"]["git"]["commit_sha"]
    assert manifest["execution_tree"] == RETRY["source"]["git"]["tree_sha"]
    assert manifest["summary"] == replay_diagnostic(EVIDENCE)
