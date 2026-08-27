"""Solver-free verification of N4 saved correctness, source and freeze evidence."""

from copy import deepcopy
import json
from pathlib import Path, PurePosixPath, PureWindowsPath

import pytest

from robust_budget_allocation.algorithms.common import PROTOCOL_PATH, PROTOCOL_SHA256
from robust_budget_allocation.algorithms.verification import verify_pair
from robust_budget_allocation.data.mechanism_data import OptionData
from robust_budget_allocation.io.hashing import canonical_json_sha256, sha256_file

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = json.loads((ROOT / "docs/evidence/N4_EF_A0_CORRECTNESS.json").read_text(encoding="utf-8"))
FIXTURES = json.loads((ROOT / "tests/fixtures/n4_correctness.json").read_text(encoding="utf-8"))["cases"]
CASES = {case["id"]: case for case in FIXTURES}
ALGORITHM_FILES = ("__init__.py", "common.py", "exact_oracle.py", "extensive_form.py", "standard_ccg.py", "verification.py")
SOURCE_PATHS = frozenset({
    PROTOCOL_PATH, "pyproject.toml", "requirements.txt", "scripts/n4_ef_a0_correctness.py",
    "tests/fixtures/n4_correctness.json",
    *["src/robust_budget_allocation/algorithms/"+p for p in ALGORITHM_FILES],
    *["src/robust_budget_allocation/"+p for p in (
        "__init__.py", "environment.py", "data/__init__.py", "data/model_data.py", "data/mechanism_data.py",
        "models/__init__.py", "models/m0.py", "models/m1.py", "models/m2.py", "models/mechanism_support.py",
        "io/__init__.py", "io/atomic.py", "io/hashing.py", "io/locking.py",
        "reproducibility/__init__.py", "reproducibility/git_state.py", "reproducibility/manifests.py",
        "runtime/__init__.py", "runtime/environment.py", "runtime/solver.py", "runtime/status.py",
        "statistics/__init__.py", "statistics/bootstrap.py", "statistics/cvar.py", "statistics/multiple_testing.py",
    )],
})
N4_PATHS = frozenset({
    PROTOCOL_PATH, "docs/N4_EF_A0_CORRECTNESS_REPORT.md", "docs/evidence/N4_EF_A0_CORRECTNESS.json",
    "scripts/n4_ef_a0_correctness.py", "tests/fixtures/n4_correctness.json",
    "tests/test_n4_correctness.py", "tests/test_n4_evidence.py",
    *["src/robust_budget_allocation/algorithms/"+p for p in ALGORITHM_FILES],
})


def digest(value, key):
    assert canonical_json_sha256({k: v for k, v in value.items() if k != key}) == value[key]


def test_n4_saved_evidence_complete_and_unchanged_protocol():
    digest(EVIDENCE, "evidence_sha256")
    assert EVIDENCE["status"] == "PASS"
    assert EVIDENCE["classification"] == "development/correctness_evidence"
    assert EVIDENCE["case_count"] == len(CASES) == len(EVIDENCE["cases"]) == 15
    assert {r["id"] for r in EVIDENCE["cases"]} == set(CASES)
    assert EVIDENCE["protocol_sha256"] == sha256_file(ROOT / PROTOCOL_PATH) == PROTOCOL_SHA256
    assert EVIDENCE["fixture_sha256"] == sha256_file(ROOT / EVIDENCE["fixture_path"])
    assert EVIDENCE["source_gate"]["tracked_dirty"] is False
    assert EVIDENCE["source_gate"]["untracked_scientific_paths"] == []
    for key, value in EVIDENCE["maxima"].items():
        assert value == max(r["checks"][key] for r in EVIDENCE["cases"])


@pytest.mark.parametrize("row", EVIDENCE["cases"], ids=lambda r: r["id"])
def test_saved_ef_a0_full_proofs_and_audit(row):
    case = CASES[row["id"]]
    data = OptionData.from_dict(case["data"])
    ef, a0 = row["EF"], row["A0"]
    assert verify_pair(data, ef, a0) == row["checks"]
    assert ef["eta"] == pytest.approx(ef["oracle"]["worst_loss"], abs=1e-7, rel=1e-9)
    for result in (ef, a0):
        digest(result, "result_sha256")
        audit = result["audit"]
        assert audit["data"] == data.to_dict()
        assert audit["data_sha256"] == data.data_sha256
        assert audit["scenario_sha256"] == data.scenario_sha256
        assert audit["scenario_order"] == list(data.base.scenarios)
        assert audit["protocol_sha256"] == PROTOCOL_SHA256
        assert audit["config_sha256"] == canonical_json_sha256(audit["config"])
        assert audit["config"]["MIPGap"] == audit["config"]["MIPGapAbs"] == 0
        env = audit["environment"]
        for key, expected in dict(python="3.12.10", pyomo="6.10.1", gurobipy="13.0.2", gurobi_optimizer="13.0.2",
                                   threads=1, solver_interface="gurobi_direct", license_available=True, status="PASS").items():
            assert env[key] == expected
        source = audit["source"]
        digest(source, "manifest_sha256")
        assert source["git"]["tracked_dirty"] is False
        for key in ("commit_sha", "tree_sha"):
            assert source["git"][key] == EVIDENCE["source_gate"][key]
        paths = [entry["path"] for entry in source["inputs"]]
        assert len(paths) == len(set(paths)) and set(paths) == SOURCE_PATHS
        for entry in source["inputs"]:
            assert sha256_file(ROOT / entry["path"]) == entry["sha256"]
    if "expected_objective" in case: assert ef["objective"] == pytest.approx(case["expected_objective"])
    if "expected_iterations" in case: assert a0["iterations"] == case["expected_iterations"]
    if "expected_worst" in case: assert a0["incumbent"]["oracle"]["worst_scenario"] == case["expected_worst"]
    if row["id"] == "three_round_cross_failures":
        assert a0["trace"][0]["candidate_UB"] == 42
        assert a0["trace"][1]["candidate_UB"] == 44
        assert a0["trace"][1]["UB"] == 42 and a0["trace"][1]["incumbent_iteration"] == 1


@pytest.mark.parametrize("fault", ["subset", "duplicate", "wrong_decision", "wrong_worst", "raw_budget", "local_status", "false_gap", "lost_incumbent"])
def test_saved_certification_rejects_corrupted_proofs(fault):
    row = next(r for r in EVIDENCE["cases"] if r["id"] == "three_round_cross_failures")
    ef, a0 = deepcopy(row["EF"]), deepcopy(row["A0"])
    oracle = a0["trace"][-1]["oracle"]
    if fault == "subset": oracle["scenarios"].pop()
    if fault == "duplicate": oracle["scenarios"][1] = deepcopy(oracle["scenarios"][0])
    if fault == "wrong_decision": oracle["first_stage_sha256"] = "0"*64
    if fault == "wrong_worst": oracle["worst_scenario"] = "c_second_fails"
    if fault == "raw_budget": oracle["scenarios"][0]["raw_solution"]["E"] = 100
    if fault == "local_status": oracle["scenarios"][0]["solver"]["termination"] = "locallyOptimal"
    if fault == "false_gap": a0["trace"][-1]["gap"] = 100
    if fault == "lost_incumbent": a0["incumbent"]["iteration"] = 1
    with pytest.raises(ValueError): verify_pair(OptionData.from_dict(CASES[row["id"]]["data"]), ef, a0)


def test_n4_exact_hash_inventory():
    lines = (ROOT / "docs/N4_CORRECTNESS_HASHES.sha256").read_text(encoding="utf-8").splitlines()
    entries = [line.split("  ") for line in lines]
    assert all(len(e) == 2 for e in entries)
    paths = [p for _, p in entries]
    assert len(paths) == len(set(paths)) and set(paths) == N4_PATHS
    for sha, path in entries:
        assert not PurePosixPath(path).is_absolute() and not PureWindowsPath(path).drive
        assert ".." not in PurePosixPath(path).parts and "\\" not in path
        target = ROOT / path
        assert target.is_file() and not target.is_symlink()
        assert sha256_file(target) == sha
