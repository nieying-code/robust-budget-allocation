"""Complete finite-scenario exact recourse oracle for Q-F-R v2 R3."""

from __future__ import annotations

import math
from time import perf_counter
from typing import Any, Mapping

import pyomo.environ as pyo

from robust_budget_allocation.data.qfr_data import QFRData
from robust_budget_allocation.io.hashing import canonical_json_sha256
from .qfr_protocol import (
    accepted_outcome,
    canonical_scenarios,
    require_close,
    scenario_identities,
    scenario_identity,
    solve_exact,
    tolerance,
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


def build_exact_recourse(
    data: QFRData,
    decision: QFRFirstStage,
    scenario: str,
) -> pyo.ConcreteModel:
    """Build the exact second-stage LP for one fixed first-stage decision."""

    pre = validate_first_stage(data, decision)
    if scenario not in data.scenarios:
        raise ValueError(f"unknown scenario: {scenario!r}")
    model = pyo.ConcreteModel(name=f"Q-F-R v2 exact recourse {decision.model_kind} {scenario}")
    model._qfr_kind = decision.model_kind
    model._qfr_data_sha256 = data.data_sha256
    model._qfr_scenario_sha256 = data.scenario_sha256
    model._qfr_first_stage_sha256 = decision.sha256
    model._qfr_scenario_identity = scenario_identity(data, scenario)
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
            <= _fulfillable(data, decision, item, scenario),
        )
        model.exercise_cost = pyo.Expression(
            expr=sum(data.exercise_cost[item] * model.x[item] for item in model.I)
        )
        model.fixed_total_budget = pyo.Constraint(
            expr=pre + model.exercise_cost <= data.budget
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


def solve_exact_recourse(
    data: QFRData,
    decision: QFRFirstStage,
    scenario: str,
) -> dict[str, Any]:
    model = build_exact_recourse(data, decision, scenario)
    outcome = solve_exact(model)
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
        coverage = _available_q(data, decision, item, scenario) + exercise[item] + shortage[item]
        violations.append(data.demand[scenario][item] - coverage)
        if decision.model_kind != "M0":
            violations.append(exercise[item] - _fulfillable(data, decision, item, scenario))
    violations.append(pre + exercise_cost - data.budget)
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
    for item in data.items:
        if not math.isfinite(exercise[item]) or not math.isfinite(shortage[item]):
            raise ValueError("exact-recourse values must be finite")
        violations.extend((-exercise[item], -shortage[item]))
        coverage = _available_q(data, decision, item, scenario) + exercise[item] + shortage[item]
        violations.append(data.demand[scenario][item] - coverage)
        if decision.model_kind == "M0":
            require_close(exercise[item], 0, f"M0 exercise[{item}]")
        else:
            violations.append(exercise[item] - _fulfillable(data, decision, item, scenario))
    exercise_cost = sum(data.exercise_cost[item] * exercise[item] for item in data.items)
    shortage_loss = sum(data.shortage_cost[item] * shortage[item] for item in data.items)
    loss = exercise_cost + shortage_loss
    pre = first_stage_cost(data, decision)
    violations.append(pre + exercise_cost - data.budget)
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
    if maximum_violation > tolerance(maximum_violation, 0):
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
