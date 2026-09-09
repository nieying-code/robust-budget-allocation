"""Complete finite-scenario exact recourse oracle for Q-F-R v2 R3."""

from __future__ import annotations

from dataclasses import replace
import math
from time import perf_counter
from typing import Any, Mapping

import pyomo.environ as pyo

from robust_budget_allocation.data.qfr_data import QFRData
from robust_budget_allocation.io.hashing import canonical_json_sha256
from .qfr_protocol import (
    ExactSolveOutcome,
    accepted_outcome,
    canonical_scenarios,
    require_close,
    scenario_identities,
    scenario_identity,
    solve_exact,
    tolerance,
)
from .qfr_numerical_validation import (
    VALIDATION_ABSOLUTE_TOLERANCE,
    family_violation_is_acceptable,
)
from .qfr_state import QFRFirstStage, first_stage_cost, validate_first_stage


def _fulfillable(
    data: QFRData,
    decision: QFRFirstStage,
    item: str,
    scenario: str,
) -> float:
    return sum(
        (
            1
            - (1 - data.reliability_mitigation[item][level])
            * data.disruption[scenario][item]
        )
        * decision.f[item][level]
        for level in decision.reliability_levels
    )


def _available_q(data: QFRData, decision: QFRFirstStage, item: str, scenario: str) -> float:
    return (
        data.retention[item]
        * data.q_availability[scenario][item]
        * decision.q[item]
    )


def _physical_nonnegative(value: float) -> float:
    """Map only absolute-tolerance solver residue to physical zero."""

    numeric = float(value)
    if -VALIDATION_ABSOLUTE_TOLERANCE <= numeric < 0:
        return 0.0
    return numeric


def build_exact_recourse(
    data: QFRData,
    decision: QFRFirstStage,
    scenario: str,
) -> pyo.ConcreteModel:
    """Build the exact second-stage LP for one fixed first-stage decision."""

    pre = validate_first_stage(data, decision)
    if scenario not in data.scenarios:
        raise ValueError(f"unknown scenario: {scenario!r}")
    # A validated first stage may exceed the budget by absolute floating-point
    # residue.  Do not present that residue as a negative RHS to the recourse LP.
    effective_pre = min(pre, data.budget) if pre > data.budget else pre
    model = pyo.ConcreteModel(name=f"Q-F-R v2 exact recourse {decision.model_kind} {scenario}")
    model._qfr_kind = decision.model_kind
    model._qfr_data_sha256 = data.data_sha256
    model._qfr_scenario_sha256 = data.scenario_sha256
    model._qfr_first_stage_sha256 = decision.sha256
    model._qfr_scenario_identity = scenario_identity(data, scenario)
    model._qfr_raw_first_stage_cost = pre
    model._qfr_effective_first_stage_cost = effective_pre
    model.I = pyo.Set(initialize=data.items, ordered=True)
    model.u = pyo.Var(model.I, domain=pyo.NonNegativeReals)
    if decision.model_kind == "M0":
        model.exercise_cost = pyo.Expression(expr=0.0)
        model.demand_balance = pyo.Constraint(
            model.I,
            rule=lambda m, item: (
                _available_q(data, decision, item, scenario) + m.u[item]
                >= data.demand[scenario][item]
            ),
        )
    else:
        model.x = pyo.Var(model.I, domain=pyo.NonNegativeReals)
        model.exercise_limit = pyo.Constraint(
            model.I,
            rule=lambda m, item: m.x[item]
            <= _physical_nonnegative(_fulfillable(data, decision, item, scenario)),
        )
        model.exercise_cost = pyo.Expression(
            expr=sum(data.exercise_cost[item] * model.x[item] for item in model.I)
        )
        model.fixed_total_budget = pyo.Constraint(
            expr=effective_pre + model.exercise_cost <= data.budget
        )
        model.demand_balance = pyo.Constraint(
            model.I,
            rule=lambda m, item: (
                _available_q(data, decision, item, scenario) + m.x[item] + m.u[item]
                >= data.demand[scenario][item]
            ),
        )
    model.shortage_loss = pyo.Expression(
        expr=sum(data.shortage_cost[item] * model.u[item] for item in model.I)
    )
    model.total_cost = pyo.Objective(
        expr=model.exercise_cost + model.shortage_loss, sense=pyo.minimize
    )
    return model


def _is_numerical_solve_failure(outcome: ExactSolveOutcome) -> bool:
    """Conservatively identify failures eligible for an equivalent scaled retry."""

    if outcome.status not in {"failed", "solver_error"}:
        return False
    text = " ".join(
        value for value in (outcome.solver_status, outcome.termination, outcome.message) if value
    ).lower()
    numerical_markers = (
        "numerical",
        "solverfailure",
        "internal solver",
        "internalerror",
        "internal error",
        "unable to retrieve attribute",
    )
    return any(marker in text for marker in numerical_markers)


def _is_solver_infeasible(outcome: ExactSolveOutcome) -> bool:
    """Identify an explicit solver infeasibility result, not a generic failure."""

    return outcome.status == "failed" and outcome.termination.strip().lower() == "infeasible"


def _original_semantic_feasibility_witness(
    data: QFRData,
    decision: QFRFirstStage,
    scenario: str,
) -> dict[str, Any]:
    """Validate a conservative recourse witness solely as an infeasible-retry gate.

    The witness fixes exercise to zero and assigns shortage to cover any demand not
    met by available pre-positioned supply.  It proves only that a feasible recourse
    point exists under the original model semantics.  It has no objective and can
    never serve as an exact solution or certificate.
    """

    pre = validate_first_stage(data, decision)
    if scenario not in data.scenarios:
        raise ValueError(f"unknown scenario: {scenario!r}")
    exercise = {item: 0.0 for item in data.items}
    shortage = {
        item: max(
            0.0,
            data.demand[scenario][item]
            - _available_q(data, decision, item, scenario),
        )
        for item in data.items
    }
    checks: list[dict[str, Any]] = []

    def record(
        family: str,
        violation: float,
        *scale_values: float,
        absolute_only: bool = False,
    ) -> None:
        acceptable = (
            float(violation) <= VALIDATION_ABSOLUTE_TOLERANCE
            if absolute_only
            else family_violation_is_acceptable(family, violation, *scale_values)
        )
        checks.append(
            {
                "family": family,
                "violation": max(0.0, float(violation)),
                "acceptable": acceptable,
            }
        )

    for item in data.items:
        record("nonnegativity", -exercise[item], absolute_only=True)
        record("nonnegativity", -shortage[item], absolute_only=True)
        available = _available_q(data, decision, item, scenario)
        coverage = available + exercise[item] + shortage[item]
        record(
            "quantity_flow",
            data.demand[scenario][item] - coverage,
            data.demand[scenario][item],
            available,
            exercise[item],
            shortage[item],
        )
        if decision.model_kind != "M0":
            fulfillment = _fulfillable(data, decision, item, scenario)
            record(
                "fulfillment_capacity",
                exercise[item] - fulfillment,
                exercise[item],
                fulfillment,
            )
    exercise_cost = sum(
        data.exercise_cost[item] * exercise[item] for item in data.items
    )
    record("budget", pre + exercise_cost - data.budget, data.budget, pre, exercise_cost)
    return {
        "role": "INFEASIBLE_RETRY_GATE_ONLY_NOT_OPTIMUM_OR_CERTIFICATE",
        "feasible": all(check["acceptable"] for check in checks),
        "exercise": exercise,
        "shortage": shortage,
        "checks": checks,
    }


def _solve_scaled_exact_recourse(
    model: pyo.ConcreteModel,
    data: QFRData,
    decision: QFRFirstStage,
    scenario: str,
    retry_reason: str = "RECOGNIZED_NUMERICAL_FAILURE",
) -> ExactSolveOutcome:
    """Retry an algebraically equivalent clone and map its solution back."""

    model.scaling_factor = pyo.Suffix(direction=pyo.Suffix.EXPORT)
    quantity_reference = {
        item: max(
            1.0,
            abs(data.demand[scenario][item]),
            abs(_available_q(data, decision, item, scenario)),
            abs(_fulfillable(data, decision, item, scenario)),
        )
        for item in data.items
    }
    for item in data.items:
        quantity = quantity_reference[item]
        model.scaling_factor[model.u[item]] = 1.0 / quantity
        model.scaling_factor[model.demand_balance[item]] = 1.0 / quantity
        if decision.model_kind != "M0":
            model.scaling_factor[model.x[item]] = 1.0 / quantity
            model.scaling_factor[model.exercise_limit[item]] = 1.0 / quantity
    if decision.model_kind != "M0":
        model.scaling_factor[model.fixed_total_budget] = 1.0 / max(
            1.0, abs(data.budget)
        )
    objective_reference = max(
        1.0,
        sum(
            max(data.exercise_cost[item], data.shortage_cost[item])
            * data.demand[scenario][item]
            for item in data.items
        ),
    )
    objective_factor = 1.0 / objective_reference
    model.scaling_factor[model.total_cost] = objective_factor
    transformation = pyo.TransformationFactory("core.scale_model")
    scaled_model = transformation.create_using(model, rename=False)
    outcome = solve_exact(scaled_model)
    if outcome.status != "optimal":
        return outcome
    transformation.propagate_solution(scaled_model, model)
    return replace(
        outcome,
        objective=float(outcome.objective) / objective_factor,
        lower_bound=float(outcome.lower_bound) / objective_factor,
        message=(
            "SCALED_RETRY_MAPPED_BACK_FOR_ORIGINAL_SEMANTIC_VALIDATION"
            if retry_reason == "RECOGNIZED_NUMERICAL_FAILURE"
            else "WITNESS_GATED_INFEASIBLE_SCALED_RETRY_MAPPED_BACK_FOR_"
            "ORIGINAL_SEMANTIC_VALIDATION"
        ),
    )


def solve_exact_recourse(
    data: QFRData,
    decision: QFRFirstStage,
    scenario: str,
) -> dict[str, Any]:
    model = build_exact_recourse(data, decision, scenario)
    outcome = solve_exact(model)
    if _is_numerical_solve_failure(outcome):
        outcome = _solve_scaled_exact_recourse(model, data, decision, scenario)
    elif _is_solver_infeasible(outcome):
        witness = _original_semantic_feasibility_witness(
            data, decision, scenario
        )
        if witness["feasible"]:
            outcome = _solve_scaled_exact_recourse(
                model,
                data,
                decision,
                scenario,
                "WITNESS_GATED_SOLVER_INFEASIBLE",
            )
    result: dict[str, Any] = {
        "scenario_id": scenario,
        "scenario_identity": scenario_identity(data, scenario),
        "data_sha256": data.data_sha256,
        "scenario_sha256": data.scenario_sha256,
        "first_stage_sha256": decision.sha256,
        "solver": outcome.to_dict(),
        "loss": None,
        "exercise": None,
        "shortage": None,
        "exercise_cost": None,
        "shortage_loss": None,
        "unused_cash": None,
        "maximum_feasibility_violation": None,
    }
    if outcome.status != "optimal":
        return result
    exercise = {
        item: 0.0
        if decision.model_kind == "M0"
        else float(pyo.value(model.x[item]))
        for item in data.items
    }
    shortage = {item: float(pyo.value(model.u[item])) for item in data.items}
    exercise_cost = sum(data.exercise_cost[item] * exercise[item] for item in data.items)
    shortage_loss = sum(data.shortage_cost[item] * shortage[item] for item in data.items)
    loss = exercise_cost + shortage_loss
    pre = first_stage_cost(data, decision)
    violations: list[float] = [0.0]
    for item in data.items:
        violations.extend((-exercise[item], -shortage[item]))
        available = _available_q(data, decision, item, scenario)
        coverage = available + exercise[item] + shortage[item]
        violations.append(data.demand[scenario][item] - coverage)
        if decision.model_kind != "M0":
            fulfillment = _fulfillable(data, decision, item, scenario)
            violations.append(exercise[item] - fulfillment)
    budget_violation = pre + exercise_cost - data.budget
    violations.append(budget_violation)
    maximum_violation = max(0.0, *violations)
    require_close(loss, float(outcome.objective), "exact recourse objective")
    result.update(
        loss=loss,
        exercise=exercise,
        shortage=shortage,
        exercise_cost=exercise_cost,
        shortage_loss=shortage_loss,
        unused_cash=data.budget - pre - exercise_cost,
        maximum_feasibility_violation=maximum_violation,
    )
    validate_recourse_result(data, decision, result)
    return result


def validate_recourse_result(
    data: QFRData,
    decision: QFRFirstStage,
    result: Mapping[str, Any],
) -> None:
    required = {
        "scenario_id",
        "scenario_identity",
        "data_sha256",
        "scenario_sha256",
        "first_stage_sha256",
        "solver",
        "loss",
        "exercise",
        "shortage",
        "exercise_cost",
        "shortage_loss",
        "unused_cash",
        "maximum_feasibility_violation",
    }
    if set(result) != required:
        raise ValueError("exact-recourse fields are incomplete or unexpected")
    validate_first_stage(data, decision)
    scenario = result["scenario_id"]
    if scenario not in data.scenarios:
        raise ValueError("exact-recourse scenario is not in complete Omega")
    if (
        result["scenario_identity"] != scenario_identity(data, scenario)
        or result["data_sha256"] != data.data_sha256
        or result["scenario_sha256"] != data.scenario_sha256
        or result["first_stage_sha256"] != decision.sha256
    ):
        raise ValueError("exact-recourse scientific identity mismatch")
    accepted_outcome(result["solver"])
    exercise = {item: float(result["exercise"][item]) for item in data.items}
    shortage = {item: float(result["shortage"][item]) for item in data.items}
    if set(result["exercise"]) != set(data.items) or set(result["shortage"]) != set(data.items):
        raise ValueError("exact-recourse item coverage mismatch")
    violations = [0.0]
    family_violations: list[tuple[str, float, tuple[float, ...]]] = []
    for item in data.items:
        if not math.isfinite(exercise[item]) or not math.isfinite(shortage[item]):
            raise ValueError("exact-recourse values must be finite")
        violations.extend((-exercise[item], -shortage[item]))
        if (
            exercise[item] < -VALIDATION_ABSOLUTE_TOLERANCE
            or shortage[item] < -VALIDATION_ABSOLUTE_TOLERANCE
        ):
            raise ValueError("exact recourse violates nonnegativity")
        available = _available_q(data, decision, item, scenario)
        coverage = available + exercise[item] + shortage[item]
        flow_violation = data.demand[scenario][item] - coverage
        violations.append(flow_violation)
        family_violations.append(
            (
                "quantity_flow",
                flow_violation,
                (data.demand[scenario][item], available, exercise[item], shortage[item]),
            )
        )
        if decision.model_kind == "M0":
            require_close(exercise[item], 0, f"M0 exercise[{item}]")
        else:
            fulfillment = _fulfillable(data, decision, item, scenario)
            fulfillment_violation = exercise[item] - fulfillment
            violations.append(fulfillment_violation)
            family_violations.append(
                (
                    "fulfillment_capacity",
                    fulfillment_violation,
                    (exercise[item], fulfillment),
                )
            )
    exercise_cost = sum(data.exercise_cost[item] * exercise[item] for item in data.items)
    shortage_loss = sum(data.shortage_cost[item] * shortage[item] for item in data.items)
    loss = exercise_cost + shortage_loss
    pre = first_stage_cost(data, decision)
    budget_violation = pre + exercise_cost - data.budget
    violations.append(budget_violation)
    family_violations.append(
        ("budget", budget_violation, (data.budget, pre, exercise_cost))
    )
    maximum_violation = max(0.0, *violations)
    require_close(float(result["exercise_cost"]), exercise_cost, "exercise cost")
    require_close(float(result["shortage_loss"]), shortage_loss, "shortage loss")
    require_close(float(result["loss"]), loss, "recourse loss")
    require_close(float(result["solver"]["objective"]), loss, "recourse solver objective")
    require_close(float(result["unused_cash"]), data.budget - pre - exercise_cost, "unused cash")
    require_close(
        float(result["maximum_feasibility_violation"]),
        maximum_violation,
        "recourse maximum feasibility violation",
    )
    if any(
        not family_violation_is_acceptable(family, violation, *scale_values)
        for family, violation, scale_values in family_violations
    ):
        raise ValueError("exact recourse violates Q-F-R constraints")


def exact_oracle(
    data: QFRData,
    decision: QFRFirstStage,
    theta: float,
) -> dict[str, Any]:
    """Evaluate all finite scenarios exactly in deterministic canonical order."""

    validate_first_stage(data, decision)
    theta_value = float(theta)
    if not math.isfinite(theta_value):
        raise ValueError("master theta must be finite")
    started = perf_counter()
    ordered = canonical_scenarios(data)
    identities = scenario_identities(data)
    results = [solve_exact_recourse(data, decision, scenario) for scenario in ordered]
    if any(row["solver"]["status"] != "optimal" for row in results):
        return {
            "status": "partial_failure",
            "data_sha256": data.data_sha256,
            "scenario_sha256": data.scenario_sha256,
            "first_stage_sha256": decision.sha256,
            "canonical_scenarios": list(ordered),
            "scenario_identities": identities,
            "results": results,
            "worst_scenario": None,
            "worst_scenario_identity": None,
            "worst_loss": None,
            "theta": theta_value,
            "violation": None,
            "evaluations": len(results),
            "complete": False,
            "runtime_seconds": perf_counter() - started,
        }
    worst_loss = max(float(row["loss"]) for row in results)
    worst_scenario = min(
        row["scenario_id"] for row in results if float(row["loss"]) == worst_loss
    )
    oracle = {
        "status": "complete",
        "data_sha256": data.data_sha256,
        "scenario_sha256": data.scenario_sha256,
        "first_stage_sha256": decision.sha256,
        "canonical_scenarios": list(ordered),
        "scenario_identities": identities,
        "results": results,
        "worst_scenario": worst_scenario,
        "worst_scenario_identity": identities[worst_scenario],
        "worst_loss": worst_loss,
        "theta": theta_value,
        "violation": max(0.0, worst_loss - theta_value),
        "evaluations": len(results),
        "complete": True,
        "runtime_seconds": perf_counter() - started,
    }
    oracle["oracle_sha256"] = canonical_json_sha256(oracle)
    validate_oracle(data, decision, oracle)
    return oracle


def validate_oracle(
    data: QFRData,
    decision: QFRFirstStage,
    oracle: Mapping[str, Any],
) -> None:
    required = {
        "status",
        "data_sha256",
        "scenario_sha256",
        "first_stage_sha256",
        "canonical_scenarios",
        "scenario_identities",
        "results",
        "worst_scenario",
        "worst_scenario_identity",
        "worst_loss",
        "theta",
        "violation",
        "evaluations",
        "complete",
        "runtime_seconds",
        "oracle_sha256",
    }
    if set(oracle) != required:
        raise ValueError("oracle fields are incomplete or unexpected")
    bare = dict(oracle)
    sealed = bare.pop("oracle_sha256")
    if sealed != canonical_json_sha256(bare):
        raise ValueError("oracle seal mismatch")
    if oracle["status"] != "complete" or oracle["complete"] is not True:
        raise ValueError("oracle is not complete")
    validate_first_stage(data, decision)
    ordered = canonical_scenarios(data)
    identities = scenario_identities(data)
    if (
        oracle["data_sha256"] != data.data_sha256
        or oracle["scenario_sha256"] != data.scenario_sha256
        or oracle["first_stage_sha256"] != decision.sha256
        or oracle["canonical_scenarios"] != list(ordered)
        or oracle["scenario_identities"] != identities
        or oracle["evaluations"] != len(ordered)
        or len(oracle["results"]) != len(ordered)
    ):
        raise ValueError("oracle completeness or identity mismatch")
    for expected, result in zip(ordered, oracle["results"], strict=True):
        if result["scenario_id"] != expected:
            raise ValueError("oracle scenario order mismatch")
        validate_recourse_result(data, decision, result)
    worst_loss = max(float(row["loss"]) for row in oracle["results"])
    worst = min(row["scenario_id"] for row in oracle["results"] if float(row["loss"]) == worst_loss)
    if oracle["worst_scenario"] != worst or oracle["worst_scenario_identity"] != identities[worst]:
        raise ValueError("oracle deterministic exact-worst tie rule mismatch")
    require_close(float(oracle["worst_loss"]), worst_loss, "oracle worst loss")
    violation = max(0.0, worst_loss - float(oracle["theta"]))
    require_close(float(oracle["violation"]), violation, "oracle violation")
    runtime = float(oracle["runtime_seconds"])
    if not math.isfinite(runtime) or runtime < 0:
        raise ValueError("oracle runtime must be finite and nonnegative")
