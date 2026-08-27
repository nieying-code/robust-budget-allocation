"""M0-only full finite-scenario LP and auditable development solve interface.

This is not a generic extensive-form framework, scenario oracle, or bound engine.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import math
from pathlib import Path
from typing import Any, Iterable

import pyomo.environ as pyo

from robust_budget_allocation.data.model_data import BudgetAllocationData
from robust_budget_allocation.io.atomic import atomic_write_json
from robust_budget_allocation.io.hashing import canonical_json_sha256
from robust_budget_allocation.reproducibility.manifests import build_source_manifest
from robust_budget_allocation.runtime.environment import ensure_preflight_once
from robust_budget_allocation.runtime.solver import (
    SolverConfiguration, solve_model, validate_solver_configuration,
)


DEVELOPMENT_SCOPE = "development/correctness_evidence"
# Development checks only: these do not freeze the N4 E1 acceptance rules.
N2_ABSOLUTE_TOLERANCE = 1e-7
N2_RELATIVE_TOLERANCE = 1e-9


def build_m0(data: BudgetAllocationData) -> pyo.ConcreteModel:
    data.validate()
    model = pyo.ConcreteModel(name="M0 Quantity Baseline")
    model.J = pyo.Set(initialize=data.suppliers, ordered=True)
    model.Omega = pyo.Set(initialize=data.scenarios, ordered=True)
    model.q = pyo.Var(model.J, domain=pyo.NonNegativeReals,
                      bounds=lambda _m, j: (0, data.procurement_limit[j]))
    model.theta = pyo.Var(domain=pyo.NonNegativeReals)
    model.x = pyo.Var(model.Omega, domain=pyo.NonNegativeReals)
    model.u = pyo.Var(model.Omega, domain=pyo.NonNegativeReals)
    model.h = pyo.Var(model.Omega, domain=pyo.NonNegativeReals)
    model.C_Q = pyo.Expression(expr=sum(data.unit_cost[j] * model.q[j] for j in model.J))
    model.delivered = pyo.Expression(model.Omega, rule=lambda m, w: sum(
        data.base_fulfillment[w][j] * m.q[j] for j in m.J
    ))
    model.cash_budget = pyo.Constraint(expr=model.C_Q <= data.budget)
    model.demand_balance = pyo.Constraint(
        model.Omega, rule=lambda m, w: m.x[w] + m.u[w] == data.demand[w],
    )
    model.resource_balance = pyo.Constraint(
        model.Omega, rule=lambda m, w: m.x[w] + m.h[w] == m.delivered[w],
    )
    model.worst_loss = pyo.Constraint(
        model.Omega, rule=lambda m, w: m.theta >= data.shortage_penalty * m.u[w],
    )
    model.total_cost = pyo.Objective(expr=model.C_Q + model.theta, sense=pyo.minimize)
    return model


@dataclass(frozen=True)
class M0Result:
    status: str
    termination_condition: str
    runtime_seconds: float
    objective: float | None = None
    C_Q: float | None = None
    q: dict[str, float] = field(default_factory=dict)
    worst_scenario: str | None = None
    worst_loss: float | None = None
    x: dict[str, float] = field(default_factory=dict)
    u: dict[str, float] = field(default_factory=dict)
    h: dict[str, float] = field(default_factory=dict)
    delivered: dict[str, float] = field(default_factory=dict)
    unused_budget: float | None = None
    raw_solution: dict[str, Any] = field(default_factory=dict)
    diagnostics: tuple[str, ...] = ()
    audit: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["classification"] = DEVELOPMENT_SCOPE
        result["result_sha256"] = canonical_json_sha256(result)
        return result

    def write_json(self, path: Path) -> None:
        atomic_write_json(path, self.to_dict())


def _extract_solution(data: BudgetAllocationData, model: pyo.ConcreteModel) -> dict[str, Any]:
    """Validate the loaded LP solution and report a maximal-service representative.

    Non-worst scenario allocations need not be unique in the epigraph LP.
    Reporting min(demand, delivered) only selects a feasible optimal representative
    at the same q; no secondary objective or additional solver/oracle is introduced.
    Raw LP values are retained, including any non-worst scenario allocation slack.
    """
    raw = {
        "q": {j: float(pyo.value(model.q[j])) for j in data.suppliers},
        "theta": float(pyo.value(model.theta)),
        "objective": float(pyo.value(model.total_cost)),
        **{name: {w: float(pyo.value(getattr(model, name)[w])) for w in data.scenarios}
           for name in ("x", "u", "h")},
    }
    numbers = [raw["theta"], raw["objective"]]
    for name in ("q", "x", "u", "h"):
        numbers.extend(raw[name].values())
    if not all(math.isfinite(v) for v in numbers):
        raise ValueError("nonfinite loaded M0 solution")

    def close(a: float, b: float) -> bool:
        return math.isclose(a, b, abs_tol=N2_ABSOLUTE_TOLERANCE, rel_tol=N2_RELATIVE_TOLERANCE)

    def at_most(a: float, b: float, label: str) -> None:
        if a > b and not close(a, b):
            raise ValueError(f"M0 invariant failed: {label}")

    def equal(a: float, b: float, label: str) -> None:
        if not close(a, b):
            raise ValueError(f"M0 invariant failed: {label}")

    at_most(0, raw["theta"], "theta nonnegative")
    for j in data.suppliers:
        at_most(0, raw["q"][j], "q nonnegative")
        at_most(raw["q"][j], data.procurement_limit[j], "procurement upper bound")
    raw_cost = sum(data.unit_cost[j] * raw["q"][j] for j in data.suppliers)
    at_most(raw_cost, data.budget, "cash budget")
    equal(raw["objective"], raw_cost + raw["theta"], "raw objective")
    for w in data.scenarios:
        received = sum(data.base_fulfillment[w][j] * raw["q"][j] for j in data.suppliers)
        for name in ("x", "u", "h"):
            at_most(0, raw[name][w], f"{name} nonnegative")
        equal(raw["x"][w] + raw["u"][w], data.demand[w], "demand balance")
        equal(raw["x"][w] + raw["h"][w], received, "resource balance")
        at_most(data.shortage_penalty * raw["u"][w], raw["theta"], "epigraph")

    # Only round bound violations already accepted within the development tolerance.
    q = {j: min(data.procurement_limit[j], max(0.0, raw["q"][j])) for j in data.suppliers}
    cost = sum(data.unit_cost[j] * q[j] for j in data.suppliers)
    delivered = {w: sum(data.base_fulfillment[w][j] * q[j] for j in data.suppliers)
                 for w in data.scenarios}
    x = {w: min(data.demand[w], delivered[w]) for w in data.scenarios}
    u = {w: data.demand[w] - x[w] for w in data.scenarios}
    h = {w: delivered[w] - x[w] for w in data.scenarios}
    losses = {w: data.shortage_penalty * u[w] for w in data.scenarios}
    worst = max(data.scenarios, key=lambda w: losses[w])
    equal(raw["theta"], losses[worst], "worst shortage loss")
    equal(raw["objective"], cost + losses[worst], "objective closure")
    at_most(cost, data.budget, "reported cash budget")
    return dict(objective=cost + losses[worst], C_Q=cost, q=q,
                worst_scenario=worst, worst_loss=losses[worst], x=x, u=u, h=h,
                delivered=delivered, unused_budget=max(0.0, data.budget - cost), raw_solution=raw)


def solve_m0(
    data: BudgetAllocationData,
    *,
    project_root: Path | None = None,
    config: SolverConfiguration = SolverConfiguration(),
    audit_inputs: Iterable[Path] = (),
) -> M0Result:
    data.validate()
    validate_solver_configuration(config)
    environment = ensure_preflight_once().to_dict()
    root = (project_root or Path(__file__).resolve().parents[3]).resolve()
    source_inputs = sorted((root / "src" / "robust_budget_allocation").rglob("*.py"))
    source_inputs.extend(root / name for name in ("pyproject.toml", "requirements.txt"))
    source_inputs.extend(audit_inputs)
    source = build_source_manifest(root, input_paths=source_inputs)
    audit = {
        "classification": DEVELOPMENT_SCOPE,
        "source": source,
        "environment": environment,
        "data": data.to_dict(),
        "data_sha256": data.data_sha256,
        "scenario_sha256": data.scenario_sha256,
        "solver_config": asdict(config),
        "solver_config_sha256": canonical_json_sha256(asdict(config)),
        "numerical_checks": {"absolute_tolerance": N2_ABSOLUTE_TOLERANCE,
                             "relative_tolerance": N2_RELATIVE_TOLERANCE,
                             "scope": "N2 development only; not N4 E1"},
        "allocation_reporting": "maximal-service representative at unchanged q; raw LP retained",
        "worst_label_rule": "first maximizer in declared scenario order; reporting only",
    }
    model = build_m0(data)
    outcome = solve_model(model, config=config)
    audit["solver_outcome"] = asdict(outcome)
    common = dict(termination_condition=outcome.termination_condition,
                  runtime_seconds=outcome.runtime_seconds, audit=audit)
    if outcome.status != "optimal":
        return M0Result(status=outcome.status,
                        diagnostics=(outcome.message or "no exact optimal solution",), **common)
    try:
        solution = _extract_solution(data, model)
    except (ValueError, TypeError, ArithmeticError) as exc:
        return M0Result(status="numerical_invalid", diagnostics=(str(exc),), **common)
    return M0Result(status="optimal", **solution, **common)
