"""Engineering promotion checks for A1_FINAL_NO_MEMORY_V1."""

from __future__ import annotations

import json
from pathlib import Path

import pyomo.environ as pyo
import pytest

import robust_budget_allocation.algorithms.qfr_exact_oracle as oracle_module
from robust_budget_allocation.algorithms.qfr_exact_oracle import (
    _is_numerical_solve_failure,
    build_exact_recourse,
    solve_exact_recourse,
)
from robust_budget_allocation.algorithms.qfr_extensive_form import solve_qfr_extensive_form
from robust_budget_allocation.algorithms.qfr_final_a1 import (
    FINAL_A1_IDENTITY,
    final_a1_settings,
    solve_qfr_final_a1,
)
from robust_budget_allocation.algorithms.qfr_numerical_validation import (
    VALIDATION_ABSOLUTE_TOLERANCE,
    VALIDATION_RELATIVE_TOLERANCE,
    family_feasibility_threshold,
    family_reference_scale,
    family_violation_is_acceptable,
)
from robust_budget_allocation.algorithms.qfr_protocol import (
    ExactSolveOutcome,
    solve_exact,
    static_data_sha256,
)
from robust_budget_allocation.algorithms.qfr_standard_ccg import solve_qfr_standard_ccg
from robust_budget_allocation.algorithms.qfr_state import QFRFirstStage, levels_for_kind
from robust_budget_allocation.algorithms.qfr_state import validate_first_stage
from robust_budget_allocation.data.qfr_data import QFRData
from robust_budget_allocation.io.hashing import sha256_file


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = json.loads(
    (ROOT / "tests/fixtures/r3_correctness_v2.json").read_text(encoding="utf-8")
)


@pytest.fixture
def data() -> QFRData:
    return QFRData.from_dict(FIXTURE["cases"][0]["data"])


def zero_decision(data: QFRData, kind: str) -> QFRFirstStage:
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


def _optimal_outcome(objective: float, *, message: str | None = None) -> ExactSolveOutcome:
    return ExactSolveOutcome(
        status="optimal",
        solver_status="ok",
        termination="optimal",
        objective=objective,
        lower_bound=objective,
        runtime_seconds=0.0,
        message=message,
    )


def test_final_identity_source_and_schema_are_state_reuse_free():
    source = (
        ROOT / "src/robust_budget_allocation/algorithms/qfr_final_a1.py"
    ).read_text(encoding="utf-8")
    assert FINAL_A1_IDENTITY == "A1_FINAL_NO_MEMORY_V1"
    assert "qfr_a1_memory" not in source
    assert "QFRScenarioMemory" not in source
    assert "memory_hits" not in source
    assert final_a1_settings()["structure"] == (
        "CANDIDATE_SEARCH_THEN_FULL_EXACT_CERTIFICATION"
    )
    assert final_a1_settings()["formal_ub_source"] == (
        "FULL_EXACT_FINITE_SCENARIO_CERTIFICATION_ONLY"
    )


def test_engineering_provenance_hashes_and_frozen_sample_identity():
    evidence = json.loads(
        (ROOT / "docs/evidence/FINAL_A1_ENGINEERING_PROMOTION_v1.json").read_text(
            encoding="utf-8"
        )
    )
    assert evidence["scientific_optimization_runs"] == 0
    assert evidence["final_algorithm"]["identity"] == FINAL_A1_IDENTITY
    assert evidence["final_algorithm"]["memory_in_execution_path"] is False
    expected_sample = "ac617befc8fbb7510e1b64b617c7e0339ea948ca519d0d18131f3b8048c131e0"
    design = json.loads(
        (ROOT / "configs/final_formal_scientific_design_v1.json").read_text(
            encoding="utf-8"
        )
    )
    assert design["E1"]["sample_table_sha256"] == expected_sample
    assert evidence["frozen_scientific_design"]["e1_sample_sha256"] == expected_sample
    rows = [
        line.split("  ", 1)
        for line in (
            ROOT / "docs/FINAL_A1_ENGINEERING_HASHES_v1.sha256"
        ).read_text(encoding="utf-8").splitlines()
    ]
    assert len(rows) == len({relative for _, relative in rows})
    for digest, relative in rows:
        assert sha256_file(ROOT / relative) == digest


def test_family_specific_scale_rule_and_isolation():
    assert VALIDATION_ABSOLUTE_TOLERANCE == 1e-7
    assert VALIDATION_RELATIVE_TOLERANCE == 1e-12
    assert family_reference_scale("budget", 100.0, 99.0, 1.0) == 100.0
    assert family_reference_scale("quantity_flow", 1e12, 4.0) == 1e12
    budget_threshold = family_feasibility_threshold("budget", 100.0, 99.0, 1.0)
    flow_threshold = family_feasibility_threshold("quantity_flow", 1e12, 4.0)
    assert budget_threshold == pytest.approx(1e-7 + 1e-12 * 100.0)
    assert flow_threshold == pytest.approx(1e-7 + 1.0)
    assert not family_violation_is_acceptable(
        "budget", 1e-4, 100.0, 99.0, 1.0
    )
    assert family_violation_is_acceptable(
        "quantity_flow", 1e-4, 1e12, 4.0
    )
    with pytest.raises(ValueError, match="unknown"):
        family_reference_scale("global", 1e12)


@pytest.mark.parametrize(
    ("outcome", "expected"),
    [
        (_optimal_outcome(0.0), False),
        (
            ExactSolveOutcome("failed", "warning", "infeasible", None, None, 0.0),
            False,
        ),
        (
            ExactSolveOutcome("failed", "warning", "maxTimeLimit", None, None, 0.0),
            False,
        ),
        (
            ExactSolveOutcome("failed", "warning", "numericalFailure", None, None, 0.0),
            True,
        ),
        (
            ExactSolveOutcome(
                "solver_error",
                "error",
                "RuntimeError",
                None,
                None,
                0.0,
                message="numerical failure while loading solution",
            ),
            True,
        ),
        (
            ExactSolveOutcome(
                "solver_error",
                "error",
                "RuntimeError",
                None,
                None,
                0.0,
                message="license unavailable",
            ),
            False,
        ),
    ],
)
def test_scaled_retry_eligibility_is_numerical_only(outcome, expected):
    assert _is_numerical_solve_failure(outcome) is expected


def test_normal_exact_solve_is_first_and_does_not_use_scaled_retry(data, monkeypatch):
    decision = zero_decision(data, "M0")
    calls = []

    def fake_normal(model):
        calls.append("production")
        for item in data.items:
            model.u[item].set_value(data.demand["c_peak"][item])
        objective = float(pyo.value(model.total_cost))
        return _optimal_outcome(objective)

    monkeypatch.setattr(oracle_module, "solve_exact", fake_normal)
    monkeypatch.setattr(
        oracle_module,
        "_solve_scaled_exact_recourse",
        lambda *args: pytest.fail("scaled retry must not run after a normal optimum"),
    )
    result = solve_exact_recourse(data, decision, "c_peak")
    assert result["solver"]["status"] == "optimal"
    assert result["solver"]["message"] is None
    assert calls == ["production"]


def test_invalid_mapped_back_solution_is_rejected(data, monkeypatch):
    decision = zero_decision(data, "M0")
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
    monkeypatch.setattr(
        oracle_module,
        "_solve_scaled_exact_recourse",
        lambda *args: _optimal_outcome(0.0, message="invalid mapped result"),
    )
    with pytest.raises((ValueError, TypeError)):
        solve_exact_recourse(data, decision, "c_peak")


def test_tight_budget_residue_is_canonicalized_but_real_violation_is_rejected(data):
    decision = zero_decision(data, "M2")
    item = data.items[0]
    unit_cost = data.q_unit_cost[item] + data.storage_cost[item] * data.tau
    payload = decision.to_dict()
    payload["q"][item] = (data.budget + 5e-8) / unit_cost
    residue = QFRFirstStage.from_dict(payload)
    validate_first_stage(data, residue)
    model = build_exact_recourse(data, residue, "c_peak")
    assert model._qfr_raw_first_stage_cost > data.budget
    assert model._qfr_effective_first_stage_cost == data.budget

    payload["q"][item] = (data.budget + 1e-4) / unit_cost
    with pytest.raises(ValueError, match="cash exceeds"):
        validate_first_stage(data, QFRFirstStage.from_dict(payload))


def test_tiny_negative_fulfillment_residue_is_only_canonicalized_at_absolute_tol(data):
    decision = zero_decision(data, "M2")
    payload = decision.to_dict()
    payload["f"][data.items[0]]["0"] = -5e-8
    residue = QFRFirstStage.from_dict(payload)
    validate_first_stage(data, residue)
    model = build_exact_recourse(data, residue, "c_peak")
    assert pyo.value(model.exercise_limit[data.items[0]].upper) == pytest.approx(0.0)

    payload["f"][data.items[0]]["0"] = -2e-7
    with pytest.raises(ValueError, match="invalid F/z"):
        validate_first_stage(data, QFRFirstStage.from_dict(payload))


@pytest.mark.gurobi
def test_scaled_retry_maps_back_and_passes_original_semantic_validation(data, monkeypatch):
    decision = zero_decision(data, "M2")
    production_solve = solve_exact
    calls = 0

    def fail_once_then_solve(model):
        nonlocal calls
        calls += 1
        if calls == 1:
            return ExactSolveOutcome(
                "solver_error",
                "error",
                "RuntimeError",
                None,
                None,
                0.0,
                message="numerical failure while loading solution",
            )
        return production_solve(model)

    monkeypatch.setattr(oracle_module, "solve_exact", fail_once_then_solve)
    result = solve_exact_recourse(data, decision, "c_peak")
    assert calls == 2
    assert result["solver"]["status"] == "optimal"
    assert result["solver"]["message"] == (
        "SCALED_RETRY_MAPPED_BACK_FOR_ORIGINAL_SEMANTIC_VALIDATION"
    )


@pytest.mark.gurobi
@pytest.mark.parametrize("model_kind", ["M0", "M1", "M2"])
def test_final_a1_matches_a0_and_ef_with_full_exact_certificate(data, model_kind):
    ef = solve_qfr_extensive_form(data, model_kind)
    a0 = solve_qfr_standard_ccg(data, model_kind)
    final = solve_qfr_final_a1(data, model_kind)
    assert final["status"] == "certified"
    assert final["algorithm_identity"] == FINAL_A1_IDENTITY
    assert final["complete_full_exact_certification_calls"] >= 1
    assert final["incumbent"]["oracle"]["complete"] is True
    assert final["objective"] == pytest.approx(a0["objective"], rel=1e-9, abs=1e-7)
    assert final["objective"] == pytest.approx(ef["objective"], rel=1e-9, abs=1e-7)
    assert "memory_hits" not in final


@pytest.mark.gurobi
def test_historical_state_artifact_mutation_cannot_affect_final_path(data, monkeypatch):
    import robust_budget_allocation.algorithms.qfr_a1_memory as historical_state

    class PoisonedArtifact:
        def __init__(self, *args, **kwargs):
            raise AssertionError("historical state artifact was invoked")

    monkeypatch.setattr(historical_state, "QFRScenarioMemory", PoisonedArtifact)
    result = solve_qfr_final_a1(data, "M0")
    assert result["status"] == "certified"
