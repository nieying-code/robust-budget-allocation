"""Recompute the persisted development evidence without a solver/license."""

import json
from pathlib import Path

import pytest

from robust_budget_allocation.data.model_data import BudgetAllocationData
from robust_budget_allocation.io.hashing import canonical_json_sha256, sha256_file


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = json.loads((ROOT / "docs/evidence/N2_M0_CORRECTNESS.json").read_text(encoding="utf-8"))
FIXTURE = json.loads((ROOT / EVIDENCE["fixture_path"]).read_text(encoding="utf-8"))
EXPECTED = {case["id"]: case for case in FIXTURE["cases"]}
# Frozen N2 inventory, not the expanding N3+ package. Every original SHA check
# below remains in force; new modules do not retroactively alter N2 evidence.
N2_SOURCE_PATHS = frozenset({
    "pyproject.toml", "requirements.txt", "scripts/n2_m0_correctness.py",
    "tests/fixtures/n2_m0_hand_cases.json",
    "src/robust_budget_allocation/__init__.py",
    "src/robust_budget_allocation/data/__init__.py",
    "src/robust_budget_allocation/data/model_data.py",
    "src/robust_budget_allocation/environment.py",
    "src/robust_budget_allocation/io/__init__.py",
    "src/robust_budget_allocation/io/atomic.py",
    "src/robust_budget_allocation/io/hashing.py",
    "src/robust_budget_allocation/io/locking.py",
    "src/robust_budget_allocation/models/__init__.py",
    "src/robust_budget_allocation/models/m0.py",
    "src/robust_budget_allocation/reproducibility/__init__.py",
    "src/robust_budget_allocation/reproducibility/git_state.py",
    "src/robust_budget_allocation/reproducibility/manifests.py",
    "src/robust_budget_allocation/runtime/__init__.py",
    "src/robust_budget_allocation/runtime/environment.py",
    "src/robust_budget_allocation/runtime/solver.py",
    "src/robust_budget_allocation/runtime/status.py",
    "src/robust_budget_allocation/statistics/__init__.py",
    "src/robust_budget_allocation/statistics/bootstrap.py",
    "src/robust_budget_allocation/statistics/cvar.py",
    "src/robust_budget_allocation/statistics/multiple_testing.py",
})


def checked_digest(payload, field):
    return canonical_json_sha256({key: value for key, value in payload.items() if key != field}) == payload[field]


def test_development_evidence_integrity_and_case_completeness():
    assert EVIDENCE["classification"] == "development/correctness_evidence"
    assert EVIDENCE["status"] == "PASS"
    assert EVIDENCE["case_count"] == len(EXPECTED) == len(EVIDENCE["cases"]) == 11
    assert {row["id"] for row in EVIDENCE["cases"]} == set(EXPECTED)
    assert all(case["data"]["shortage_penalty"] > 0 for case in FIXTURE["cases"])
    assert all(row["result"]["audit"]["data"]["shortage_penalty"] > 0
               for row in EVIDENCE["cases"])
    assert checked_digest(EVIDENCE, "evidence_sha256")
    assert sha256_file(ROOT / EVIDENCE["fixture_path"]) == EVIDENCE["fixture_sha256"]
    assert EVIDENCE["source_gate"]["tracked_dirty"] is False
    assert EVIDENCE["source_gate"]["untracked_scientific_paths"] == []


@pytest.mark.parametrize("row", EVIDENCE["cases"], ids=lambda row: row["id"])
def test_saved_case_matches_source_inputs_hand_values_and_physical_balances(row):
    expected = EXPECTED[row["id"]]
    result = row["result"]
    data = BudgetAllocationData.from_dict(expected["data"])
    assert row["status"] == "PASS" and all(row["checks"].values())
    assert row["expected"] == expected["expected"]
    assert result["status"] == "optimal"
    assert result["classification"] == EVIDENCE["classification"]
    assert checked_digest(result, "result_sha256")
    for name, value in expected["expected"].items():
        assert result[name] == pytest.approx(value)
    assert result["objective"] == pytest.approx(result["C_Q"] + result["worst_loss"])
    assert result["C_Q"] <= data.budget + 1e-7
    for w in data.scenarios:
        assert result["x"][w] + result["u"][w] == pytest.approx(data.demand[w])
        received = sum(data.base_fulfillment[w][j] * result["q"][j] for j in data.suppliers)
        assert result["x"][w] + result["h"][w] == pytest.approx(received)
        assert result["u"][w] >= 0 and result["h"][w] >= 0
    audit = result["audit"]
    assert audit["data"] == data.to_dict()
    assert audit["data_sha256"] == data.data_sha256
    assert audit["scenario_sha256"] == data.scenario_sha256
    assert audit["solver_config_sha256"] == canonical_json_sha256(audit["solver_config"])
    assert audit["solver_outcome"]["status"] == "optimal"
    env = audit["environment"]
    for name, value in {"python": "3.12.10", "pyomo": "6.10.1", "gurobipy": "13.0.2",
                        "gurobi_optimizer": "13.0.2", "solver_interface": "gurobi_direct",
                        "threads": 1, "license_available": True, "status": "PASS"}.items():
        assert env[name] == value
    source = audit["source"]
    assert checked_digest(source, "manifest_sha256")
    for key in ("commit_sha", "tree_sha"):
        assert source["git"][key] == EVIDENCE["source_gate"][key]
    assert source["git"]["tracked_dirty"] is False
    listed_paths = [entry["path"] for entry in source["inputs"]]
    assert len(listed_paths) == len(set(listed_paths))
    assert set(listed_paths) == N2_SOURCE_PATHS
    for entry in source["inputs"]:
        assert sha256_file(ROOT / entry["path"]) == entry["sha256"]
