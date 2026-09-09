"""Regression checks for the witness-gated exact-oracle numerical hotfix."""

from __future__ import annotations

import json
from pathlib import Path

import pyomo.environ as pyo
import pytest

import robust_budget_allocation.algorithms.qfr_exact_oracle as oracle_module
from robust_budget_allocation.algorithms.qfr_exact_oracle import (
    _original_semantic_feasibility_witness,
    solve_exact_recourse,
)
from robust_budget_allocation.algorithms.qfr_final_a1 import (
    FINAL_A1_IDENTITY,
    FINAL_A1_IMPLEMENTATION_REVISION,
)
from robust_budget_allocation.algorithms.qfr_numerical_validation import (
    VALIDATION_ABSOLUTE_TOLERANCE,
    VALIDATION_RELATIVE_TOLERANCE,
)
from robust_budget_allocation.algorithms.qfr_protocol import (
    ExactSolveOutcome,
    static_data_sha256,
)
from robust_budget_allocation.algorithms.qfr_state import QFRFirstStage, levels_for_kind
from robust_budget_allocation.data.qfr_data import QFRData


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = json.loads(
    (ROOT / "tests/fixtures/r3_correctness_v2.json").read_text(encoding="utf-8")
)


@pytest.fixture
def data() -> QFRData:
    return QFRData.from_dict(FIXTURE["cases"][0]["data"])


def zero_decision(data: QFRData, kind: str = "M2") -> QFRFirstStage:
    levels = levels_for_kind(kind)
    return QFRFirstStage(
        model_kind=kind,
        reliability_levels=levels,
        data_sha256=data.data_sha256,
        scenario_sha256=data.scenario_sha256,
        static_data_sha256=static_data_sha256(data),
        q={item: 0.0 for item in data.items},
        f={item: {level: 0.0 for level in levels} for item in data.items},
        z={item: {level: 0 for level in levels} for item in data.items},
    )


def outcome(status: str, termination: str, *, objective: float | None = None):
    return ExactSolveOutcome(
        status=status,
        solver_status="ok" if status == "optimal" else "warning",
        termination=termination,
        objective=objective,
        lower_bound=objective,
        runtime_seconds=0.0,
    )


def load_witness_solution(model, data: QFRData, scenario: str) -> float:
    for item in data.items:
        if hasattr(model, "x"):
            model.x[item].set_value(0.0)
        model.u[item].set_value(data.demand[scenario][item])
    return float(pyo.value(model.total_cost))


def test_optimal_does_not_trigger_retry(data, monkeypatch):
    decision = zero_decision(data)

    def solve(model):
        objective = load_witness_solution(model, data, "c_peak")
        return outcome("optimal", "optimal", objective=objective)

    monkeypatch.setattr(oracle_module, "solve_exact", solve)
    monkeypatch.setattr(
        oracle_module,
        "_solve_scaled_exact_recourse",
        lambda *args: pytest.fail("an optimal production solve must not retry"),
    )
    assert solve_exact_recourse(data, decision, "c_peak")["solver"]["status"] == "optimal"


def test_infeasible_with_feasible_witness_triggers_scaled_retry(data, monkeypatch):
    decision = zero_decision(data)
    calls = []
    monkeypatch.setattr(
        oracle_module,
        "solve_exact",
        lambda model: outcome("failed", "infeasible"),
    )

    def scaled(model, actual_data, actual_decision, scenario, reason):
        calls.append(reason)
        objective = load_witness_solution(model, actual_data, scenario)
        return outcome("optimal", "optimal", objective=objective)

    monkeypatch.setattr(oracle_module, "_solve_scaled_exact_recourse", scaled)
    result = solve_exact_recourse(data, decision, "c_peak")
    assert calls == ["WITNESS_GATED_SOLVER_INFEASIBLE"]
    assert result["solver"]["status"] == "optimal"


def test_recognized_numerical_failure_keeps_existing_scaled_retry(data, monkeypatch):
    decision = zero_decision(data)
    monkeypatch.setattr(
        oracle_module,
        "solve_exact",
        lambda model: ExactSolveOutcome(
            "solver_error",
            "error",
            "RuntimeError",
            None,
            None,
            0.0,
            message="numerical failure while loading solution",
        ),
    )
    calls = []

    def scaled(model, actual_data, actual_decision, scenario):
        calls.append("recognized_numerical_failure")
        objective = load_witness_solution(model, actual_data, scenario)
        return outcome("optimal", "optimal", objective=objective)

    monkeypatch.setattr(oracle_module, "_solve_scaled_exact_recourse", scaled)
    result = solve_exact_recourse(data, decision, "c_peak")
    assert calls == ["recognized_numerical_failure"]
    assert result["solver"]["status"] == "optimal"


def test_infeasible_with_failed_witness_does_not_retry(data, monkeypatch):
    decision = zero_decision(data)
    monkeypatch.setattr(
        oracle_module,
        "solve_exact",
        lambda model: outcome("failed", "infeasible"),
    )
    monkeypatch.setattr(
        oracle_module,
        "_original_semantic_feasibility_witness",
        lambda *args: {"feasible": False},
    )
    monkeypatch.setattr(
        oracle_module,
        "_solve_scaled_exact_recourse",
        lambda *args: pytest.fail("a failed witness must not enable retry"),
    )
    result = solve_exact_recourse(data, decision, "c_peak")
    assert result["solver"]["status"] == "failed"
    assert result["solver"]["termination"] == "infeasible"


def test_witness_gated_retry_fails_closed_when_scaled_solve_fails(data, monkeypatch):
    decision = zero_decision(data)
    monkeypatch.setattr(
        oracle_module,
        "solve_exact",
        lambda model: outcome("failed", "infeasible"),
    )
    monkeypatch.setattr(
        oracle_module,
        "_solve_scaled_exact_recourse",
        lambda *args: outcome("failed", "infeasible"),
    )
    result = solve_exact_recourse(data, decision, "c_peak")
    assert result["solver"]["status"] == "failed"
    assert result["loss"] is None


def test_invalid_mapped_back_result_is_rejected(data, monkeypatch):
    decision = zero_decision(data)
    monkeypatch.setattr(
        oracle_module,
        "solve_exact",
        lambda model: outcome("failed", "infeasible"),
    )

    def invalid_scaled(model, actual_data, actual_decision, scenario, reason):
        for item in actual_data.items:
            model.x[item].set_value(0.0)
            model.u[item].set_value(0.0)
        return outcome("optimal", "optimal", objective=0.0)

    monkeypatch.setattr(oracle_module, "_solve_scaled_exact_recourse", invalid_scaled)
    with pytest.raises(ValueError, match="violates Q-F-R constraints"):
        solve_exact_recourse(data, decision, "c_peak")


def test_witness_is_retry_gate_only_and_has_no_objective(data):
    witness = _original_semantic_feasibility_witness(
        data, zero_decision(data), "c_peak"
    )
    assert witness["feasible"] is True
    assert witness["role"] == "INFEASIBLE_RETRY_GATE_ONLY_NOT_OPTIMUM_OR_CERTIFICATE"
    assert "objective" not in witness
    assert "loss" not in witness
    assert "solver" not in witness


def test_tolerances_and_final_no_memory_identity_are_unchanged():
    assert VALIDATION_ABSOLUTE_TOLERANCE == 1e-7
    assert VALIDATION_RELATIVE_TOLERANCE == 1e-12
    assert FINAL_A1_IDENTITY == "A1_FINAL_NO_MEMORY_V1"
    assert FINAL_A1_IMPLEMENTATION_REVISION == (
        "A1_FINAL_NO_MEMORY_V1_R1_WITNESS_GATED_INFEASIBLE_RETRY"
    )
    source = (
        ROOT / "src/robust_budget_allocation/algorithms/qfr_final_a1.py"
    ).read_text(encoding="utf-8")
    assert "qfr_a1_memory" not in source
    assert "memory_hits" not in source


def test_engineering_replay_evidence_is_complete_and_scientifically_isolated():
    evidence = json.loads(
        (
            ROOT
            / "docs/evidence/FINAL_A1_SPURIOUS_INFEASIBILITY_HOTFIX_REPLAY_v1.json"
        ).read_text(encoding="utf-8")
    )
    assert evidence["algorithm_identity"] == FINAL_A1_IDENTITY
    assert evidence["implementation_revision"] == FINAL_A1_IMPLEMENTATION_REVISION
    assert evidence["failure_population"] == {
        "certified": 205,
        "first_stage_identity_invariant": 205,
        "status_counts": {"certified": 205},
        "tested": 205,
    }
    fallback = evidence["numerical_fallback"]
    assert fallback["authorized_diagnostic_production_infeasible"] == 284
    assert fallback["witness_triggered_full_certificate_retries"] == 284
    assert fallback["scaled_retry_optimal"] == 284
    assert fallback["mapped_back_original_validation_pass"] == 284
    assert fallback["full_exact_certification_pass"] == 205
    assert set(evidence["previously_certified_controls"].values()) == {8}
    assert evidence["guardrails"] == {
        "E2_B_runs": 0,
        "E2_C_runs": 0,
        "E2_D_runs": 0,
        "engineering_regression_only": True,
        "formal_E2A_recertification": False,
        "memory_reintroduced": False,
        "model_changed": False,
        "scientific_design_changed": False,
        "scientific_optimization_runs": 0,
        "scientific_parameters_changed": False,
        "scientific_results_promoted_or_modified": False,
        "tolerance_changed": False,
    }
