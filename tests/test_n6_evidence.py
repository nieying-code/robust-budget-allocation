"""Preserve the BLOCKED N6 outcome; do not relabel raw solver success as run success."""

from copy import deepcopy
import json

import pytest

from robust_budget_allocation.io.hashing import sha256_file, canonical_json_sha256
from robust_budget_allocation.pilot.configuration import ROOT, generate, PROTOCOL_SHA, CONFIG_SHA
from robust_budget_allocation.pilot.measurement import verify_engine
from robust_budget_allocation.pilot.replay import load_bundle, replay_bundle, replay_run
from robust_budget_allocation.pilot.storage import seal, safe_relative, check_seal
from robust_budget_allocation.pilot.summary import summarize

EVIDENCE_PATH = ROOT / "docs/evidence/N6_PILOT_EVIDENCE.json.gz"
EVIDENCE = load_bundle(EVIDENCE_PATH)
N6_PATHS = frozenset({
    "configs/pilot/n6_candidates.json", "docs/N6_PILOT_PROTOCOL.md",
    "docs/N6_PILOT_REPORT.md", "docs/N6_SCIENTIFIC_DIAGNOSIS.md",
    "docs/evidence/N6_PRELAUNCH_DIAGNOSTIC.md", "docs/evidence/N6_PILOT_EVIDENCE.json.gz",
    "docs/evidence/N6_PILOT_MANIFEST.json", "scripts/n6_pilot.py",
    "tests/test_n6_pilot.py", "tests/test_n6_evidence.py",
    "tests/test_n6_harness_repair.py", "docs/N6_HARNESS_REPAIR_AUTHORIZATION.md",
    "docs/N6_HARNESS_REPAIR_REPORT.md", "docs/evidence/N6_SOURCE_OBJECTS.json.gz",
    "docs/evidence/N6_HARNESS_VALIDATION.json",
    "docs/evidence/N6_EF_DIAGNOSTIC_RETRY.json.gz",
    "docs/evidence/N6_DIAGNOSTIC_MANIFEST.json", "tests/test_n6_diagnostic_evidence.py",
    "docs/N6_FRESH_RESTART_AUTHORIZATION.md", "tests/test_n6_restart.py",
    "docs/N6_FRESH_RESTART_REPORT.md", "docs/evidence/N6_RESTART_STOP.json.gz",
    "tests/test_n6_restart_stop.py",
    "docs/N6_SOURCE_COMPARISON_FIX_REPORT.md",
    "docs/evidence/N6_SOURCE_COMPARISON_VALIDATION.json.gz",
    "tests/test_n6_source_comparison_validation.py",
    "docs/N6_PRELAUNCH_REVALIDATION_v2.md",
    "docs/evidence/N6_PILOT02_EVIDENCE.json.gz",
    "docs/evidence/N6_PILOT02_PRELAUNCH.json.gz",
    "docs/evidence/N6_PILOT02_MANIFEST.json",
    "docs/evidence/N6_PILOT02_SUMMARY.json",
    "tests/test_n6_pilot02_evidence.py",
    "tests/test_n6_shallow_cli_replay.py", "docs/N6_READONLY_REPLAY_REPAIR.md",
    *["src/robust_budget_allocation/pilot/"+name+".py" for name in (
        "__init__", "configuration", "execution", "measurement", "replay", "storage", "summary",
        "heartbeat", "diagnostic", "source_archive", "restart")]
})


def test_failed_batch_integrity_is_not_success():
    assert replay_bundle(EVIDENCE) == dict(status="FAIL", runs=3, pairs=0, successes=2,
                                         failures=1, max_pair_difference=None)
    assert EVIDENCE["protocol_sha256"] == PROTOCOL_SHA
    assert EVIDENCE["config_sha256"] == CONFIG_SHA
    assert EVIDENCE["source_gate"]["commit_sha"] == "2ae53f0f608d4457eda1150540f5eb3b618048f3"
    assert EVIDENCE["source_gate"]["tree_sha"] == "fe4ebee47c12a1aea1540e00619ec448c4854176"
    assert EVIDENCE["failure"] == dict(run_id="n6pilot01-00-ef", status="incomplete")


@pytest.mark.parametrize("index", range(3))
def test_saved_run_and_raw_certificate(index):
    saved = EVIDENCE["runs"][index]
    decoded = replay_run(saved)
    result = json.loads(saved["files"]["result.json"])
    record = decoded["record"]
    assert verify_engine(generate(record["binding"]["config"]), result["engine"])
    if index == 2:
        assert decoded["replay"] == "FAILURE_RETAINED"
        assert record["certified"] is False
        assert record["status"] == "incomplete"
        assert record["watchdog"]["diagnostic"] == "PermissionError(13, 'Permission denied')"
        assert result["status"] == "success/certified"  # raw != accepted supervised run


def test_no_diagnosis_or_projection_fabricated():
    result = summarize(EVIDENCE)
    assert result["state"] == "N6_BLOCKED"
    assert result["observations"] == [] and result["projection"] == {}
    assert result["completed_pairs"] == 0
    assert set(result["per_method"]) == {"M0", "M1"}


@pytest.mark.parametrize("fault", ["success", "missing_run", "duplicate_run", "pair_claim"])
def test_forged_batch_claim_rejected(fault):
    forged = deepcopy(EVIDENCE)
    if fault == "success":
        forged["status"] = "PASS"
    elif fault == "missing_run":
        # Reclassification as a complete batch must not be possible.
        forged["runs"].pop()
        forged["status"] = "PASS"
    elif fault == "duplicate_run":
        forged["runs"].append(deepcopy(forged["runs"][0]))
    else:
        forged["pair_checks"]["invented"] = {"status": "PASS"}
    forged.pop("evidence_sha256")
    forged = seal(forged, "evidence_sha256")
    with pytest.raises(ValueError):
        replay_bundle(forged)


def test_compact_manifest_anchors_and_run_hashes():
    manifest = json.loads((ROOT / "docs/evidence/N6_PILOT_MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["archive_sha256"] == sha256_file(EVIDENCE_PATH)
    assert manifest["archive_bytes"] == EVIDENCE_PATH.stat().st_size
    assert manifest["status"] == "N6_BLOCKED"
    assert manifest["expected_runs"] == 80 and manifest["attempted_runs"] == 3
    assert manifest["unattempted_runs"] == 77 and manifest["completed_pairs"] == 0
    for row, saved in zip(manifest["runs"], EVIDENCE["runs"], strict=True):
        record = json.loads(saved["files"]["record.json"])
        assert row["run_id"] == record["run_id"]
        assert row["status"] == record["status"]
        assert row["output_sha256"] == record["output_sha256"]
        assert row["raw_file_manifest_sha256"] == saved["manifest"]["sha256"]


def test_n6_hash_inventory_complete_and_regular():
    lines = (ROOT / "docs/N6_PILOT_HASHES.sha256").read_text(encoding="utf-8").splitlines()
    pairs = [line.split("  ", 1) for line in lines if line]
    paths = [safe_relative(path) for digest, path in pairs]
    assert len(paths) == len(set(paths)) and set(paths) == N6_PATHS
    # N6's frozen list remains historical. Explicit transition supersessions
    # bind the original digest and the independently committed current digest.
    transition = json.loads((ROOT / "docs/TRANSITION_ENGINEERING_MANIFEST.json").read_text(encoding="utf-8"))
    superseded = transition["superseded_engineering_files"]
    for digest, path in pairs:
        target = ROOT / path
        assert target.is_file() and not target.is_symlink()
        if path in superseded:
            assert superseded[path]["n6_sha256"] == digest
            assert sha256_file(target) == superseded[path]["current_sha256"]
        else:
            assert sha256_file(target) == digest
    assert "docs/N6_PILOT_HASHES.sha256" not in N6_PATHS
