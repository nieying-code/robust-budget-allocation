"""Independent, solver-free recomputation of persisted N3 correctness evidence."""

import json
import math
from pathlib import Path, PurePosixPath, PureWindowsPath

import pytest

from robust_budget_allocation.data.mechanism_data import OptionData, ReliabilityData
from robust_budget_allocation.data.model_data import BudgetAllocationData
from robust_budget_allocation.io.hashing import canonical_json_sha256, sha256_file

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = json.loads((ROOT / "docs/evidence/N3_M1_M2_CORRECTNESS.json").read_text(encoding="utf-8"))
FIXTURES = json.loads((ROOT / "tests/fixtures/n3_mechanisms.json").read_text(encoding="utf-8"))["cases"]
OLD_FIXTURES = json.loads((ROOT / "tests/fixtures/n2_m0_hand_cases.json").read_text(encoding="utf-8"))["cases"]
CASES = {case["id"]: case for case in FIXTURES}
OLD_CASES = {case["id"]: case for case in OLD_FIXTURES}
SOURCE_PATHS = frozenset({
    "pyproject.toml", "requirements.txt", "scripts/n3_mechanism_correctness.py",
    "tests/fixtures/n2_m0_hand_cases.json", "tests/fixtures/n3_mechanisms.json",
    *["src/robust_budget_allocation/" + path for path in (
        "__init__.py", "environment.py", "data/__init__.py", "data/model_data.py", "data/mechanism_data.py",
        "models/__init__.py", "models/m0.py", "models/m1.py", "models/m2.py", "models/mechanism_support.py",
        "io/__init__.py", "io/atomic.py", "io/hashing.py", "io/locking.py",
        "reproducibility/__init__.py", "reproducibility/git_state.py", "reproducibility/manifests.py",
        "runtime/__init__.py", "runtime/environment.py", "runtime/solver.py", "runtime/status.py",
        "statistics/__init__.py", "statistics/bootstrap.py", "statistics/cvar.py", "statistics/multiple_testing.py",
    )],
})
N3_PATHS = frozenset({
    "src/robust_budget_allocation/data/mechanism_data.py",
    "src/robust_budget_allocation/models/m1.py",
    "src/robust_budget_allocation/models/m2.py",
    "src/robust_budget_allocation/models/mechanism_support.py",
    "scripts/n3_mechanism_correctness.py", "tests/fixtures/n3_mechanisms.json",
    "tests/test_n2_evidence.py", "tests/test_n3_schema.py", "tests/test_n3_models.py", "tests/test_n3_evidence.py",
    "docs/N3_M1_M2_IMPLEMENTATION_REPORT.md", "docs/evidence/N3_M1_M2_CORRECTNESS.json",
})


def digest(payload, key):
    assert canonical_json_sha256({k: v for k, v in payload.items() if k != key}) == payload[key]


def equal(actual, expected):
    if isinstance(expected, dict):
        assert set(actual) == set(expected)
        for key in expected:
            equal(actual[key], expected[key])
    elif isinstance(expected, (str, bool)) or expected is None:
        assert actual == expected
    else:
        assert actual == pytest.approx(expected, abs=1e-7, rel=1e-9)


def test_n3_evidence_completeness_and_integrity():
    digest(EVIDENCE, "evidence_sha256")
    assert EVIDENCE["classification"] == "development/correctness_evidence"
    assert EVIDENCE["status"] == "PASS"
    assert EVIDENCE["mechanism_count"] == EVIDENCE["degeneration_count"] == len(CASES) == 13
    assert EVIDENCE["m0_regression_count"] == len(OLD_CASES) == 11
    expected_ids = {case["id"] + "/" + kind for case in FIXTURES
                    for kind in ("m0", "m1_base", "m1", "m2_off")}
    expected_ids |= {case["id"] + "/m2" for case in FIXTURES if case["model"] == "M2"}
    expected_ids |= {"n2/" + case["id"] for case in OLD_FIXTURES}
    assert set(EVIDENCE["results"]) == expected_ids
    for group, expected in (("mechanisms", CASES), ("degenerations", CASES), ("m0_regressions", OLD_CASES)):
        ids = [r["id"] for r in EVIDENCE[group]]
        assert len(ids) == len(set(ids)) and set(ids) == set(expected)
        assert all(all(row["checks"].values()) for row in EVIDENCE[group])
    for path, sha in EVIDENCE["fixture_hashes"].items():
        assert sha256_file(ROOT / path) == sha
    assert EVIDENCE["source_gate"]["tracked_dirty"] is False
    assert EVIDENCE["source_gate"]["untracked_scientific_paths"] == []


@pytest.mark.parametrize("result_id", EVIDENCE["results"])
def test_saved_result_audit_and_accounting(result_id):
    result = EVIDENCE["results"][result_id]
    digest(result, "result_sha256")
    assert result["status"] == "optimal" and result["classification"] == EVIDENCE["classification"]
    audit = result["audit"]
    if result.get("model_kind") == "M2":
        data = OptionData.from_dict(audit["data"])
        base, rel = data.base, data.reliability
    elif result.get("model_kind") == "M1":
        data = ReliabilityData.from_dict(audit["data"])
        base, rel = data.base, data
    else:
        data = base = BudgetAllocationData.from_dict(audit["data"])
        rel = None
    assert audit["data_sha256"] == data.data_sha256
    assert audit["scenario_sha256"] == base.scenario_sha256
    assert audit["solver_config_sha256"] == canonical_json_sha256(audit["solver_config"])
    assert audit["solver_outcome"]["status"] == "optimal"
    env = audit["environment"]
    for key, value in dict(python="3.12.10", pyomo="6.10.1", gurobipy="13.0.2", gurobi_optimizer="13.0.2",
                           solver_interface="gurobi_direct", threads=1, license_available=True, status="PASS").items():
        assert env[key] == value
    source = audit["source"]
    digest(source, "manifest_sha256")
    assert source["git"]["tracked_dirty"] is False
    for key in ("commit_sha", "tree_sha"):
        assert source["git"][key] == EVIDENCE["source_gate"][key]
    paths = [entry["path"] for entry in source["inputs"]]
    assert len(paths) == len(set(paths)) and set(paths) == SOURCE_PATHS
    for entry in source["inputs"]:
        assert sha256_file(ROOT / entry["path"]) == entry["sha256"]
    equal(result["C_Q"], sum(base.unit_cost[j] * result["q"][j] for j in base.suppliers))
    cr, fee = 0, 0
    if rel is not None:
        cr = sum(rel.fixed_premium[j][result["reliability_choice"][j]] + sum(
            rel.unit_premium[j][k] * result["q_by_level"][j][k] for k in rel.levels[j]) for j in base.suppliers)
        equal(result["C_R"], cr)
        assert result["y_F"] in (0, 1)
        fee = data.option_fee * result["y_F"] if isinstance(data, OptionData) else 0
        equal(result["option_fee"], fee)
        for j in base.suppliers:
            equal(result["q"][j], sum(result["q_by_level"][j].values()))
            for k in rel.levels[j]:
                assert result["q_by_level"][j][k] >= 0
                if k != result["reliability_choice"][j]:
                    equal(result["q_by_level"][j][k], 0)
    first = result["C_Q"] + cr + fee
    losses = {}
    for j in base.suppliers:
        assert 0 <= result["q"][j] <= base.procurement_limit[j] + 1e-7
    for w in base.scenarios:
        g = result["g"][w] if rel else 0
        expenditure = data.emergency_price[w] * g if isinstance(data, OptionData) else 0
        if rel:
            equal(result["E"][w], expenditure)
            if result["y_F"] == 0:
                equal(g, 0)
            if isinstance(data, OptionData):
                assert expenditure <= data.option_cap * result["y_F"] + 1e-7
            received = sum(rel.fulfillment[w][j][k] * result["q_by_level"][j][k]
                           for j in base.suppliers for k in rel.levels[j])
        else:
            received = sum(base.base_fulfillment[w][j] * result["q"][j] for j in base.suppliers)
        equal(result["x"][w] + result["u"][w], base.demand[w])
        equal(result["x"][w] + result["h"][w], received + g)
        assert min(result["x"][w], result["u"][w], result["h"][w], g) >= 0
        assert first + expenditure <= base.budget + 1e-7
        equal(result["unused_budget"][w] if rel else result["unused_budget"], base.budget - first - expenditure)
        losses[w] = expenditure + base.shortage_penalty * result["u"][w]
    equal(result["worst_loss"], max(losses.values()))
    equal(result["objective"], first + max(losses.values()))
    assert result["worst_scenario"] == max(base.scenarios, key=losses.get)
    assert math.isfinite(result["objective"])


@pytest.mark.parametrize("row", EVIDENCE["mechanisms"], ids=lambda r: r["id"])
def test_saved_mechanism_hand_expectations(row):
    assert row["expected"] == CASES[row["id"]]["expected"]
    result = EVIDENCE["results"][row["result_id"]]
    for key, value in row["expected"].items():
        equal(result[key], value)
    if row["id"] == "expensive_emergency_no_exercise":
        equal(result["g"]["expensive"], 0)


@pytest.mark.parametrize("row", EVIDENCE["degenerations"], ids=lambda r: r["id"])
def test_saved_degeneration_equalities(row):
    zero, base, one, off = (EVIDENCE["results"][row["result_ids"][k]] for k in ("m0", "m1_base", "m1", "m2_off"))
    data = OptionData.from_dict(CASES[row["id"]]["data"])
    for result in (base, one, off):
        assert result["audit"]["base_data_sha256"] == zero["audit"]["data_sha256"] == data.base.data_sha256
    for key in ("objective", "C_Q", "q", "x", "u", "h", "worst_loss", "worst_scenario"):
        equal(base[key], zero[key])
    equal(base["C_R"], 0)
    for key in ("objective", "C_Q", "C_R", "q", "q_by_level", "reliability_choice", "x", "u", "h", "worst_loss", "worst_scenario", "unused_budget"):
        equal(off[key], one[key])
    assert off["y_F"] == 0
    assert all(v == 0 for v in (*off["g"].values(), *off["E"].values()))


@pytest.mark.parametrize("row", EVIDENCE["m0_regressions"], ids=lambda r: r["id"])
def test_saved_m0_regression_including_original_scenario_results(row):
    old = json.loads((ROOT / "docs/evidence/N2_M0_CORRECTNESS.json").read_text(encoding="utf-8"))
    previous = next(c["result"] for c in old["cases"] if c["id"] == row["id"])
    result = EVIDENCE["results"][row["result_id"]]
    assert row["expected"] == OLD_CASES[row["id"]]["expected"]
    for key, value in row["expected"].items():
        equal(result[key], value)
    for key in ("objective", "C_Q", "q", "x", "u", "h", "worst_loss", "worst_scenario", "unused_budget"):
        equal(result[key], previous[key])


def test_n3_hash_inventory_exact_and_all_files_match():
    entries = [line.split("  ") for line in (ROOT / "docs/N3_M1_M2_HASHES.sha256").read_text(encoding="utf-8").splitlines()]
    assert all(len(entry) == 2 for entry in entries)
    paths = [path for _, path in entries]
    assert len(paths) == len(set(paths)) and set(paths) == N3_PATHS
    for sha, path in entries:
        assert not PurePosixPath(path).is_absolute() and not PureWindowsPath(path).drive
        assert ".." not in PurePosixPath(path).parts and "\\" not in path
        target = ROOT / path
        assert target.is_file() and not target.is_symlink()
        assert sha256_file(target) == sha
