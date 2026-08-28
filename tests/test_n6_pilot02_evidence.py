"""Replay completed fresh pilot evidence without executing any scientific solve."""

from copy import deepcopy
from datetime import datetime
import hashlib
import json
from types import SimpleNamespace
import xml.etree.ElementTree as ET

import pytest

from robust_budget_allocation.io.hashing import sha256_file
from robust_budget_allocation.pilot.configuration import ROOT, registration, execution_order
from robust_budget_allocation.pilot import restart, source_archive
from robust_budget_allocation.pilot.replay import load_bundle, verify_source, anchored_inputs
from robust_budget_allocation.pilot.storage import check_seal, seal
from robust_budget_allocation.pilot.summary import summarize

DIRECTORY = ROOT / "docs/evidence"
BUNDLE = load_bundle(DIRECTORY / "N6_PILOT02_EVIDENCE.json.gz")
PROOF = load_bundle(DIRECTORY / "N6_PILOT02_PRELAUNCH.json.gz")
MANIFEST = json.loads((DIRECTORY / "N6_PILOT02_MANIFEST.json").read_text(encoding="utf-8"))
SUMMARY = json.loads((DIRECTORY / "N6_PILOT02_SUMMARY.json").read_text(encoding="utf-8"))
COMMIT = "ec6bbfc55e333483efa41f866c0e8f26d13cd18f"
TREE = "1856c203917fa3cc234f5aee83e2a4403abe472d"


@pytest.fixture(autouse=True)
def source_object_store(monkeypatch):
    # New proof is independent; do not overwrite old historical source archives.
    # This supplies raw Git objects for shallow CI, not trusted hashes/validation.
    original = source_archive.archive_objects()
    objects = {**original, **PROOF["git_objects"]["objects"]}
    monkeypatch.setattr(source_archive, "archive_objects", lambda: objects)
    anchored_inputs.cache_clear()
    yield
    anchored_inputs.cache_clear()


def test_complete_fresh_batch_disk_replay():
    assert restart.replay_restart(BUNDLE) == MANIFEST["replay"] == dict(
        status="PASS", runs=80, pairs=16, successes=80, failures=0, max_pair_difference=0.0)
    assert BUNDLE["failure"] is None
    assert BUNDLE["source"]["git"]["commit_sha"] == COMMIT
    assert BUNDLE["source"]["git"]["tree_sha"] == TREE
    assert not BUNDLE["source"]["git"]["tracked_dirty"]


def test_actual_prelaunch_files_xml_and_roundtrip_proof(tmp_path, monkeypatch):
    check_seal(PROOF, "evidence_sha256")
    assert PROOF["source"] == BUNDLE["source"]
    raw = PROOF["gate_files"]
    assert set(raw) == {"gates.json", "roundtrip.json", "negative-source.json",
                        "solver-free.xml", "windows-only.xml", "licensed.xml", "windows-stress.xml"}
    # Restore actual bytes; validation below exercises the production validator
    # against archived source, not a claim that the current checkout ran gates.
    for name, text in raw.items():
        (tmp_path / name).write_bytes(text.encode("utf-8"))
    gate = json.loads((tmp_path / "gates.json").read_text(encoding="utf-8"))
    report = json.loads((tmp_path / "roundtrip.json").read_text(encoding="utf-8"))
    assert gate == BUNDLE["gates"] and report == BUNDLE["roundtrip"]
    assert sha256_file(tmp_path / "gates.json") == report["gate_file_sha256"]
    assert sha256_file(tmp_path / "negative-source.json") == report["negative_file_sha256"]
    assert report["raw_python_source_equal"] is False
    assert report["canonical_source_equal"] is report["changed_source_rejected"] is True
    assert report["saved_untracked_type"] == "list" and report["live_untracked_type"] == "tuple"
    assert datetime.fromisoformat(report["finished_utc"]) < datetime.fromisoformat(BUNDLE["batch_start"]["started_utc"])
    expected = {"solver-free": 602, "windows-only": 4, "licensed": 100, "windows-stress": 3}
    for name, suite in gate["suites"].items():
        assert hashlib.sha256(raw[name+".xml"].encode()).hexdigest() == suite["xml_sha256"]
        xml = ET.fromstring(raw[name+".xml"])
        for key in ("tests", "failures", "errors", "skipped"):
            assert sum(int(x.attrib.get(key, 0)) for x in xml.iter("testsuite")) == suite[key]
        assert suite["tests"] == expected[name]
        assert suite["returncode"] == suite["failures"] == suite["errors"] == suite["skipped"] == 0
    live = deepcopy(gate["source"])
    live["git"]["untracked_paths"] = tuple(live["git"]["untracked_paths"])
    monkeypatch.setattr(restart, "manifest", lambda: live)
    monkeypatch.setattr(restart, "GATES", tmp_path)
    monkeypatch.setattr(restart, "GATE_FILE", tmp_path / "gates.json")
    assert restart.validate_prelaunch() == (gate, report)
    forged = json.loads((tmp_path / "negative-source.json").read_text(encoding="utf-8"))
    check_seal(forged)
    check_seal(forged["source"], "manifest_sha256")
    with pytest.raises(ValueError, match="restart gate/source mismatch"):
        restart.validate_gates(forged)


def test_new_source_is_authenticated_without_local_git_history(monkeypatch):
    monkeypatch.setattr(source_archive.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=1))
    assert PROOF["git_objects"]["commits"] == [COMMIT]
    verify_source(BUNDLE["source"])  # Native object IDs, commit/tree, full input inventory.
    forged = deepcopy(BUNDLE["source"])
    forged["inputs"][0]["sha256"] = "0" * 64
    forged.pop("manifest_sha256")
    with pytest.raises(ValueError, match="source hash mismatch"):
        verify_source(seal(forged, "manifest_sha256"))


def test_manifest_frozen_order_and_all_artifact_hashes():
    check_seal(MANIFEST)
    assert MANIFEST["execution_commit"] == COMMIT and MANIFEST["execution_tree"] == TREE
    assert MANIFEST["actual_runs"] == MANIFEST["successes"] == MANIFEST["expected_runs"] == 80
    assert MANIFEST["completed_pairs"] == 16 and MANIFEST["failures"] == 0
    assert not any(MANIFEST[k] for k in ("n7_authorized", "formal_results", "history_reused", "automatic_retries"))
    for artifact in MANIFEST["artifacts"]:
        path = ROOT / artifact["path"]
        assert sha256_file(path) == artifact["sha256"] and path.stat().st_size == artifact["bytes"]
    expected = [(f"n6pilot02-{i:02d}-{m.lower()}", c, m)
                for i, c in enumerate(registration()["configs"]) for m in execution_order(i)]
    for row, saved, (run_id, config, method) in zip(MANIFEST["runs"], BUNDLE["runs"], expected, strict=True):
        record = json.loads(saved["files"]["record.json"])
        assert row["run_id"] == record["run_id"] == run_id
        assert row["method"] == record["method"] == method
        assert row["binding"] == record["binding"] and record["binding"]["config"] == config
        assert row["source_manifest_sha256"] == MANIFEST["source_manifest_sha256"]
        assert row["output_sha256"] == record["output_sha256"]
        assert row["trace_sha256"] == record["trace_sha256"]
        assert row["raw_file_manifest_sha256"] == saved["manifest"]["sha256"]
        assert row["status"] == "success/certified" and row["certified"]
        assert row["objective"] == record["metrics"]["objective"]
    assert MANIFEST["run_file_bytes"] == sum(sum(f["bytes"] for f in r["manifest"]["files"]) for r in BUNDLE["runs"])


def test_summary_recomputed_with_nonactivation_warnings_and_capacity():
    check_seal(SUMMARY)
    assert SUMMARY == seal(summarize(BUNDLE))
    assert SUMMARY["state"] == "N6_READY_FOR_PR_REVIEW"
    assert not SUMMARY["model_severe_risk"] and not SUMMARY["algorithm_severe_risk"]
    assert len(SUMMARY["narrow_coverage_warnings"]) == 2
    observations = SUMMARY["observations"]
    assert sum(o["paid_suppliers"] > 0 for o in observations) == 12
    assert all(o["y_F"] == 0 and o["delta_option"] == 0 for o in observations)
    assert SUMMARY["per_method"]["A0"]["totals"]["scenario_evaluations"] == 576
    assert SUMMARY["per_method"]["A1"]["totals"]["scenario_evaluations"] == 258
    assert set(SUMMARY["projection"]) == {"100_pairs", "1000_pairs"}


def test_memory_inactivity_explained_by_actual_trace_not_only_hit_count():
    rows = [t for saved in BUNDLE["runs"]
            if json.loads(saved["files"]["record.json"])["method"] == "A1"
            for t in json.loads(saved["files"]["result.json"])["engine"]["trace"]]
    assert len(rows) == 42
    assert all(t["first_stage"]["y_F"] == 0 for t in rows)
    assert all(t["phase_i"]["ranking"] == t["phase_i"]["evaluations"] == [] for t in rows)
    assert all(t["phase_iii_called"] == t["certified"] for t in rows)
    assert sum(t["phase_ii"]["hit"] for t in rows) == 26
    assert sum(t["phase_iii_called"] for t in rows) == 16
    assert sum(len(t["phase_ii"]["evaluations"]) for t in rows) == 42
    for t in rows:
        assert all(e["scenario"] in t["active_scenarios"] for e in t["memory_before"])
    assert MANIFEST["mechanism_trace"]["memory_evaluations"] == 0


def test_governance_and_all_old_evidence_preserved():
    assert PROOF["governance"] == MANIFEST["governance"]
    assert MANIFEST["governance"]["merge_commit"] == "ce12e391f503ca877605f860256a1f86e11d59d8"
    assert MANIFEST["governance"]["state_at_merge"] == "N6_BLOCKED"
    assert not MANIFEST["governance"]["scientific_approval"]
    for name, digest in PROOF["historical_hashes"].items():
        if name.startswith("docs/"):
            assert sha256_file(ROOT / name) == digest
    assert not PROOF["diagnostic_retry_enabled"]


@pytest.mark.parametrize("fault", ["order", "missing", "source", "roundtrip", "gate", "history"])
def test_forged_full_batch_cannot_pass_even_with_resealed_envelope(fault):
    forged = deepcopy(BUNDLE)
    if fault == "order":
        forged["runs"][0], forged["runs"][1] = forged["runs"][1], forged["runs"][0]
    elif fault == "missing":
        forged["runs"].pop()
    elif fault == "source":
        forged["source"]["packages"]["Pyomo"] = "forged"
        forged["source"].pop("manifest_sha256")
        forged["source"] = seal(forged["source"], "manifest_sha256")
    elif fault == "roundtrip":
        forged["roundtrip"]["changed_source_rejected"] = False
        forged["roundtrip"].pop("sha256")
        forged["roundtrip"] = seal(forged["roundtrip"])
    elif fault == "gate":
        forged["gates"]["suites"]["licensed"]["skipped"] = 1
        forged["gates"].pop("sha256")
        forged["gates"] = seal(forged["gates"])
    else:
        old = load_bundle(DIRECTORY / "N6_PILOT_EVIDENCE.json.gz")
        forged["runs"][0] = old["runs"][0]
    forged.pop("evidence_sha256")
    with pytest.raises(ValueError):
        restart.replay_restart(seal(forged, "evidence_sha256"))
