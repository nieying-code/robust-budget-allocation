"""Solver-preserving diagnostics for retained Formal E2-A failures."""

from __future__ import annotations

from collections import Counter
import math
from typing import Any, Mapping

import pyomo.environ as pyo

from robust_budget_allocation.algorithms.qfr_exact_oracle import (
    _is_numerical_solve_failure,
    _solve_scaled_exact_recourse,
    build_exact_recourse,
    validate_recourse_result,
)
from robust_budget_allocation.algorithms.qfr_numerical_validation import (
    VALIDATION_ABSOLUTE_TOLERANCE,
    VALIDATION_RELATIVE_TOLERANCE,
    family_feasibility_threshold,
)
from robust_budget_allocation.algorithms.qfr_protocol import scenario_identity, solve_exact
from robust_budget_allocation.algorithms.qfr_state import (
    QFRFirstStage,
    first_stage_cost,
    validate_first_stage,
)
from robust_budget_allocation.data.qfr_data import QFRData
from robust_budget_allocation.io.hashing import canonical_json_sha256


def available_q(data: QFRData, decision: QFRFirstStage, item: str, scenario: str) -> float:
    return data.retention[item] * data.q_availability[scenario][item] * decision.q[item]


def fulfillable_f(data: QFRData, decision: QFRFirstStage, item: str, scenario: str) -> float:
    return sum(
        (1 - (1 - data.reliability_mitigation[item][level]) * data.disruption[scenario][item])
        * decision.f[item][level]
        for level in decision.reliability_levels
    )


def first_stage_evidence(data: QFRData, decision: QFRFirstStage) -> dict[str, Any]:
    validation_error = None
    try:
        validate_first_stage(data, decision)
    except Exception as error:  # evidence only; never suppress in the solver path
        validation_error = f"{type(error).__name__}: {error}"
    cost = first_stage_cost(data, decision)
    violation = max(0.0, cost - data.budget)
    threshold = family_feasibility_threshold("budget", data.budget, cost)
    result = {
        "first_stage_sha256": decision.sha256,
        "Q": decision.q,
        "F": {item: {str(level): value for level, value in levels.items()} for item, levels in decision.f.items()},
        "z": {item: {str(level): value for level, value in levels.items()} for item, levels in decision.z.items()},
        "first_stage_cost": cost,
        "budget": data.budget,
        "first_stage_cost_minus_B": cost - data.budget,
        "budget_violation": violation,
        "budget_reference_scale": max(1.0, abs(cost), abs(data.budget)),
        "budget_tolerance": threshold,
        "validation_pass": validation_error is None,
        "validation_error": validation_error,
    }
    result["evidence_sha256"] = canonical_json_sha256(result)
    return result


def conservative_witness(data: QFRData, decision: QFRFirstStage, scenario: str) -> dict[str, Any]:
    """Build x=0 and exact residual shortage; do not optimize or certify."""

    families: dict[str, dict[str, Any]] = {}
    maximums = {"nonnegativity": 0.0, "quantity_flow": 0.0, "fulfillment_capacity": 0.0}
    scales = {"nonnegativity": 1.0, "quantity_flow": 1.0, "fulfillment_capacity": 1.0}
    items: dict[str, Any] = {}
    for item in data.items:
        q = available_q(data, decision, item, scenario)
        capacity = fulfillable_f(data, decision, item, scenario)
        x = 0.0
        u = max(0.0, data.demand[scenario][item] - q)
        coverage = q + x + u
        violations = {
            "nonnegativity": max(0.0, -x, -u),
            "quantity_flow": max(0.0, data.demand[scenario][item] - coverage),
            "fulfillment_capacity": max(0.0, x - capacity),
        }
        references = {
            "nonnegativity": max(1.0, abs(x), abs(u)),
            "quantity_flow": max(1.0, abs(data.demand[scenario][item]), abs(q), abs(x), abs(u)),
            "fulfillment_capacity": max(1.0, abs(x), abs(capacity)),
        }
        for family in maximums:
            maximums[family] = max(maximums[family], violations[family])
            scales[family] = max(scales[family], references[family])
        items[item] = {
            "demand": data.demand[scenario][item],
            "available_Q": q,
            "fulfillable_F": capacity,
            "x": x,
            "u": u,
            "coverage": coverage,
            "violations": violations,
        }
    pre = first_stage_cost(data, decision)
    maximums["budget"] = max(0.0, pre - data.budget)
    scales["budget"] = max(1.0, abs(pre), abs(data.budget))
    for family, violation in maximums.items():
        if family == "nonnegativity":
            tolerance = VALIDATION_ABSOLUTE_TOLERANCE
        else:
            tolerance = family_feasibility_threshold(family, scales[family])
        families[family] = {
            "feasible": violation <= tolerance,
            "maximum_violation": violation,
            "reference_scale": scales[family],
            "applicable_tolerance": tolerance,
        }
    witness = {
        "identity": "DIAGNOSTIC_X_ZERO_RESIDUAL_SHORTAGE_WITNESS_V1",
        "not_an_optimum_or_certificate": True,
        "scenario_id": scenario,
        "first_stage_sha256": decision.sha256,
        "items": items,
        "constraint_families": families,
        "original_semantic_feasible": all(value["feasible"] for value in families.values()),
    }
    witness["witness_sha256"] = canonical_json_sha256(witness)
    return witness


def _mapped_result(data: QFRData, decision: QFRFirstStage, scenario: str, model, outcome) -> dict[str, Any]:
    exercise = {item: float(pyo.value(model.x[item])) for item in data.items}
    shortage = {item: float(pyo.value(model.u[item])) for item in data.items}
    exercise_cost = sum(data.exercise_cost[item] * exercise[item] for item in data.items)
    shortage_loss = sum(data.shortage_cost[item] * shortage[item] for item in data.items)
    loss = exercise_cost + shortage_loss
    pre = first_stage_cost(data, decision)
    violations = [0.0]
    for item in data.items:
        violations.extend((-exercise[item], -shortage[item]))
        violations.append(data.demand[scenario][item] - available_q(data, decision, item, scenario) - exercise[item] - shortage[item])
        violations.append(exercise[item] - fulfillable_f(data, decision, item, scenario))
    violations.append(pre + exercise_cost - data.budget)
    return {
        "scenario_id": scenario,
        "scenario_identity": scenario_identity(data, scenario),
        "data_sha256": data.data_sha256,
        "scenario_sha256": data.scenario_sha256,
        "first_stage_sha256": decision.sha256,
        "solver": outcome.to_dict(),
        "loss": loss,
        "exercise": exercise,
        "shortage": shortage,
        "exercise_cost": exercise_cost,
        "shortage_loss": shortage_loss,
        "unused_cash": data.budget - pre - exercise_cost,
        "maximum_feasibility_violation": max(0.0, *violations),
    }


def scenario_diagnostic(data: QFRData, decision: QFRFirstStage, scenario: str) -> tuple[dict[str, Any], dict[str, Any] | None]:
    model = build_exact_recourse(data, decision, scenario)
    production = solve_exact(model)
    production_status = production.to_dict()
    scaled_attempted = production.status != "optimal"
    scaled_status = None
    scaled_semantic_status = "NOT_ATTEMPTED"
    scaled_objective = None
    if scaled_attempted:
        scaled_model = build_exact_recourse(data, decision, scenario)
        scaled = _solve_scaled_exact_recourse(scaled_model, data, decision, scenario)
        scaled_status = scaled.to_dict()
        if scaled.status == "optimal":
            mapped = _mapped_result(data, decision, scenario, scaled_model, scaled)
            try:
                validate_recourse_result(data, decision, mapped)
                scaled_semantic_status = "PASS"
            except Exception as error:
                scaled_semantic_status = f"FAIL:{type(error).__name__}:{error}"
            scaled_objective = mapped["loss"]
        else:
            scaled_semantic_status = "NO_SOLUTION"
    witness = conservative_witness(data, decision, scenario) if production.termination == "infeasible" else None
    row = {
        "scenario_id": scenario,
        "scenario_identity": scenario_identity(data, scenario),
        "production_status": production.status,
        "production_solver_status": production.solver_status,
        "production_termination": production.termination,
        "production_objective": production.objective,
        "production_scaled_retry_triggered": _is_numerical_solve_failure(production),
        "diagnostic_scaled_retry_attempted": scaled_attempted,
        "scaled_status": None if scaled_status is None else scaled_status["status"],
        "scaled_solver_status": None if scaled_status is None else scaled_status["solver_status"],
        "scaled_termination": None if scaled_status is None else scaled_status["termination"],
        "scaled_objective": scaled_objective,
        "scaled_original_semantic_validation": scaled_semantic_status,
        "witness_feasible": None if witness is None else witness["original_semantic_feasible"],
        "witness_sha256": None if witness is None else witness["witness_sha256"],
    }
    row["scenario_diagnostic_sha256"] = canonical_json_sha256(row)
    return row, witness


def classify_scenario(row: Mapping[str, Any]) -> str:
    if row["production_termination"] == "infeasible":
        if row["witness_feasible"] is not True:
            return "E_ORIGINAL_WITNESS_NOT_FEASIBLE"
        if row["scaled_status"] != "optimal" or row["scaled_original_semantic_validation"] != "PASS":
            return "D_SCALED_RETRY_FAILURE"
        return "A_SOLVER_INFEASIBLE_BUT_ORIGINAL_WITNESS_FEASIBLE"
    if row["production_status"] != "optimal":
        return "C_NUMERICAL_SOLVE_FAILURE"
    return "OPTIMAL"


def taxonomy_counts(rows: list[Mapping[str, Any]]) -> dict[str, int]:
    return dict(Counter(classify_scenario(row) for row in rows))
