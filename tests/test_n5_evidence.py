"""Solver-free replays of all N5 saved phase, certificate and provenance records."""

from copy import deepcopy
import json
from pathlib import Path, PurePosixPath, PureWindowsPath

import pytest

from robust_budget_allocation.algorithms.a1_verification import verify_a1, verify_three
from robust_budget_allocation.algorithms.common import PROTOCOL_PATH, PROTOCOL_SHA256
from robust_budget_allocation.algorithms.memory_guided_ccg import A1_PROTOCOL_PATH, A1_PROTOCOL_SHA256, a1_settings
from robust_budget_allocation.data.mechanism_data import OptionData
from robust_budget_allocation.io.hashing import canonical_json_sha256, sha256_file

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = json.loads((ROOT / "docs/evidence/N5_EF_A0_A1_CORRECTNESS.json").read_text(encoding="utf-8"))
FIXTURE = json.loads((ROOT / "tests/fixtures/n5_correctness.json").read_text(encoding="utf-8"))
CASES = {c["id"]: c for c in FIXTURE["cases"]}
NEW_ALGORITHMS = ("a1_memory.py", "a1_candidates.py", "memory_guided_ccg.py", "a1_verification.py")
SOURCE_PATHS = frozenset({
    PROTOCOL_PATH, A1_PROTOCOL_PATH, "pyproject.toml", "requirements.txt",
    "scripts/n5_a1_correctness.py", "tests/fixtures/n5_correctness.json",
    *["src/robust_budget_allocation/algorithms/"+p for p in
      ("__init__.py", "common.py", "extensive_form.py", "exact_oracle.py", "standard_ccg.py", "verification.py", *NEW_ALGORITHMS)],
    *["src/robust_budget_allocation/"+p for p in (
        "__init__.py", "environment.py", "data/__init__.py", "data/model_data.py", "data/mechanism_data.py",
        "models/__init__.py", "models/m0.py", "models/m1.py", "models/m2.py", "models/mechanism_support.py",
        "io/__init__.py", "io/atomic.py", "io/hashing.py", "io/locking.py",
        "reproducibility/__init__.py", "reproducibility/git_state.py", "reproducibility/manifests.py",
        "runtime/__init__.py", "runtime/environment.py", "runtime/solver.py", "runtime/status.py",
        "statistics/__init__.py", "statistics/bootstrap.py", "statistics/cvar.py", "statistics/multiple_testing.py",
    )],
})
N5_PATHS = frozenset({A1_PROTOCOL_PATH, "docs/N5_A1_CORRECTNESS_REPORT.md", "docs/evidence/N5_EF_A0_A1_CORRECTNESS.json",
                      "scripts/n5_a1_correctness.py", "tests/fixtures/n5_correctness.json",
                      "tests/test_n5_a1.py", "tests/test_n5_evidence.py",
                      *["src/robust_budget_allocation/algorithms/"+p for p in NEW_ALGORITHMS]})


def digest(value, field):
    assert canonical_json_sha256({k: v for k, v in value.items() if k != field}) == value[field]


def test_n5_evidence_complete_and_both_protocols_unchanged():
    digest(EVIDENCE, "evidence_sha256")
    assert EVIDENCE["status"] == "PASS" and EVIDENCE["classification"] == "development/correctness_evidence"
    assert EVIDENCE["expected_case_count"] == EVIDENCE["case_count"] == len(CASES) == len(EVIDENCE["cases"]) == 16
    assert {r["id"] for r in EVIDENCE["cases"]} == set(CASES)
    previous = json.loads((ROOT / "tests/fixtures/n4_correctness.json").read_text(encoding="utf-8"))["cases"]
    assert FIXTURE["cases"][:len(previous)] == previous
    assert EVIDENCE["fixture_sha256"] == sha256_file(ROOT / EVIDENCE["fixture_path"])
    assert EVIDENCE["protocol_hashes"] == {PROTOCOL_PATH: PROTOCOL_SHA256, A1_PROTOCOL_PATH: A1_PROTOCOL_SHA256}
    for path, sha in EVIDENCE["protocol_hashes"].items(): assert sha256_file(ROOT / path) == sha
    assert EVIDENCE["source_gate"]["tracked_dirty"] is False and EVIDENCE["source_gate"]["untracked_scientific_paths"] == []
    for key, value in EVIDENCE["maxima"].items(): assert value == max(r["checks"][key] for r in EVIDENCE["cases"])
    for key, value in EVIDENCE["diagnostics"].items(): assert value == sum(r["A1"][key] for r in EVIDENCE["cases"])


@pytest.mark.parametrize("row", EVIDENCE["cases"], ids=lambda r: r["id"])
def test_saved_three_way_phases_and_sources(row):
    d = OptionData.from_dict(CASES[row["id"]]["data"])
    assert verify_three(d, row["EF"], row["A0"], row["A1"]) == row["checks"]
    for name in ("EF", "A0", "A1"):
        result = row[name]
        digest(result, "result_sha256")
        assert result["classification"] == EVIDENCE["classification"]
        audit = result["audit"]
        assert audit["data"] == d.to_dict() and audit["data_sha256"] == d.data_sha256
        assert audit["scenario_order"] == list(d.base.scenarios) and audit["scenario_sha256"] == d.scenario_sha256
        assert audit["config_sha256"] == canonical_json_sha256(audit["config"])
        assert audit["config"]["MIPGap"] == audit["config"]["MIPGapAbs"] == 0
        if name == "A1":
            assert audit["a1_protocol_sha256"] == A1_PROTOCOL_SHA256
            for key, value in a1_settings().items(): assert audit["config"][key] == value
            assert result["trace"][0]["memory_before"] == []
        for key, expected in dict(python="3.12.10", pyomo="6.10.1", gurobipy="13.0.2", gurobi_optimizer="13.0.2",
                                   solver_interface="gurobi_direct", threads=1, license_available=True, status="PASS").items():
            assert audit["environment"][key] == expected
        source = audit["source"]
        digest(source, "manifest_sha256")
        assert source["git"]["tracked_dirty"] is False
        for key in ("commit_sha", "tree_sha"): assert source["git"][key] == EVIDENCE["source_gate"][key]
        paths = [e["path"] for e in source["inputs"]]
        assert len(paths) == len(set(paths)) and set(paths) == SOURCE_PATHS
        for entry in source["inputs"]: assert sha256_file(ROOT / entry["path"]) == entry["sha256"]


@pytest.mark.parametrize("fault", ["memory_ub", "candidate_ub", "skip_exact", "fake_certified", "future_memory",
                                  "score", "ranking", "partial_oracle", "wrong_incumbent", "call_counter"])
def test_saved_replay_rejects_forged_shortcuts(fault):
    case_id = "three_round_cross_failures" if fault in ("candidate_ub", "score", "ranking") else "history_after_buffered_candidate_miss"
    saved = next(r for r in EVIDENCE["cases"] if r["id"] == case_id)
    result = deepcopy(saved["A1"])
    if fault == "memory_ub": result["trace"][1]["UB"] = 1
    if fault == "candidate_ub": result["trace"][0]["candidate_UB"] = 1
    if fault == "skip_exact": result["trace"][-1]["phase_iii_called"] = False
    if fault == "fake_certified": result["trace"][1]["certified"] = True
    if fault == "future_memory": result["trace"][0]["memory_before"] = result["trace"][1]["memory_before"]
    if fault == "score": result["trace"][0]["phase_ii"]["scores"]["b_first_fails"] = 999
    if fault == "ranking": result["trace"][0]["phase_ii"]["ranking"].reverse()
    if fault == "partial_oracle": result["trace"][-1]["phase_iii"]["scenarios"].pop()
    if fault == "wrong_incumbent": result["incumbent"]["iteration"] = 1
    if fault == "call_counter": result["phase_iii_calls"] = 0
    with pytest.raises(ValueError): verify_a1(OptionData.from_dict(CASES[case_id]["data"]), result)


def test_n5_exact_file_hash_inventory():
    entries = [line.split("  ") for line in (ROOT / "docs/N5_A1_HASHES.sha256").read_text(encoding="utf-8").splitlines()]
    assert all(len(e) == 2 for e in entries)
    paths = [path for _, path in entries]
    assert len(paths) == len(set(paths)) and set(paths) == N5_PATHS
    for sha, path in entries:
        assert not PurePosixPath(path).is_absolute() and not PureWindowsPath(path).drive
        assert ".." not in PurePosixPath(path).parts and "\\" not in path
        target = ROOT / path
        assert target.is_file() and not target.is_symlink() and sha256_file(target) == sha
