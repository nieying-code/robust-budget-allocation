"""N3 model results, accounting validation, and development provenance only."""

from dataclasses import asdict, dataclass, field
import math
from pathlib import Path
from time import perf_counter

import pyomo.environ as pyo

from robust_budget_allocation.io.atomic import atomic_write_json
from robust_budget_allocation.io.hashing import canonical_json_sha256
from robust_budget_allocation.reproducibility.manifests import build_source_manifest
from robust_budget_allocation.runtime.environment import ensure_preflight_once
from robust_budget_allocation.runtime.solver import (
    SolverConfiguration, SolveOutcome, create_solver, normalize_termination, validate_solver_configuration,
)
from .m0 import DEVELOPMENT_SCOPE, N2_ABSOLUTE_TOLERANCE as ATOL, N2_RELATIVE_TOLERANCE as RTOL


@dataclass(frozen=True)
class MechanismResult:
    model_kind: str
    status: str
    termination_condition: str
    runtime_seconds: float
    objective: float | None = None
    C_Q: float | None = None
    C_R: float | None = None
    option_fee: float | None = None
    y_F: int | None = None
    q: dict = field(default_factory=dict)
    q_by_level: dict = field(default_factory=dict)
    reliability_choice: dict = field(default_factory=dict)
    worst_scenario: str | None = None
    worst_loss: float | None = None
    x: dict = field(default_factory=dict)
    u: dict = field(default_factory=dict)
    h: dict = field(default_factory=dict)
    delivered: dict = field(default_factory=dict)
    g: dict = field(default_factory=dict)
    E: dict = field(default_factory=dict)
    unused_budget: dict = field(default_factory=dict)
    raw_solution: dict = field(default_factory=dict)
    diagnostics: tuple = ()
    audit: dict = field(default_factory=dict)

    def to_dict(self):
        payload = asdict(self)
        payload["classification"] = DEVELOPMENT_SCOPE
        payload["result_sha256"] = canonical_json_sha256(payload)
        return payload

    def write_json(self, path):
        atomic_write_json(path, self.to_dict())


def _solve_mip(model, config):
    """Use N1 construction/preflight/status; require zero MIP gap for N3 fixtures."""
    solver = create_solver(config)
    solver.options["MIPGap"] = 0.0
    solver.options["MIPGapAbs"] = 0.0
    start = perf_counter()
    try:
        result = solver.solve(model, load_solutions=False, tee=False)
        termination = result.solver.termination_condition
        status = normalize_termination(result.solver.status, termination)
        if status == "optimal":
            model.solutions.load_from(result)
        return SolveOutcome(status, config.interface, perf_counter() - start, str(termination))
    except Exception as exc:
        return SolveOutcome("solver_error", config.interface, perf_counter() - start, type(exc).__name__, str(exc))


def _extract(data, model, model_kind):
    option = model_kind == "M2"
    rel = data.reliability if option else data
    base = rel.base
    raw = {
        "z": {j: {k: float(pyo.value(model.z[j, k])) for k in rel.levels[j]} for j in base.suppliers},
        "q_by_level": {j: {k: float(pyo.value(model.q_level[j, k])) for k in rel.levels[j]} for j in base.suppliers},
        "y_F": float(pyo.value(model.y_F)) if option else 0.0,
        "g": {w: float(pyo.value(model.g[w])) if option else 0.0 for w in base.scenarios},
        "theta": float(pyo.value(model.theta)), "objective": float(pyo.value(model.total_cost)),
        **{name: {w: float(pyo.value(getattr(model, name)[w])) for w in base.scenarios} for name in ("x", "u", "h")},
    }

    def finite(value):
        if isinstance(value, dict):
            return all(finite(v) for v in value.values())
        return math.isfinite(value)

    def close(a, b):
        return math.isclose(a, b, abs_tol=ATOL, rel_tol=RTOL)

    def equal(a, b, label):
        if not close(a, b):
            raise ValueError(f"accounting violation: {label}")

    def upper(a, b, label):
        if a > b and not close(a, b):
            raise ValueError(f"accounting violation: {label}")

    if not finite(raw):
        raise ValueError("nonfinite solution")
    if option and model._n3_fixed_option is not None:
        equal(raw["y_F"], model._n3_fixed_option, "fixed Option decision")
    if model._n3_fixed_reliability is not None:
        for j, k in model.JK:
            equal(raw["z"][j][k], int(k == model._n3_fixed_reliability[j]), "fixed Reliability decision")
    # Validate every raw algebraic constraint, including fixed decisions and integrality.
    for var in model.component_data_objects(pyo.Var):
        value = float(pyo.value(var))
        if var.has_lb():
            upper(float(pyo.value(var.lb)), value, var.name + " lower bound")
        if var.has_ub():
            upper(value, float(pyo.value(var.ub)), var.name + " upper bound")
        if var.is_binary():
            equal(value, round(value), var.name + " integrality")
    for c in model.component_data_objects(pyo.Constraint, active=True):
        value = float(pyo.value(c.body))
        if c.has_lb():
            upper(float(pyo.value(c.lower)), value, c.name)
        if c.has_ub():
            upper(value, float(pyo.value(c.upper)), c.name)

    choices = {}
    quantities = {}
    for j in base.suppliers:
        selected = [k for k in rel.levels[j] if round(raw["z"][j][k]) == 1]
        if len(selected) != 1:
            raise ValueError("exactly one Reliability level must be selected")
        choices[j] = selected[0]
        quantities[j] = {k: max(0.0, raw["q_by_level"][j][k]) for k in rel.levels[j]}
    q = {j: sum(quantities[j].values()) for j in base.suppliers}
    C_Q = sum(base.unit_cost[j] * q[j] for j in base.suppliers)
    C_R = sum(rel.fixed_premium[j][choices[j]] + sum(rel.unit_premium[j][k] * quantities[j][k]
              for k in rel.levels[j]) for j in base.suppliers)
    y = int(round(raw["y_F"]))
    fee = data.option_fee * y if option else 0.0
    g = {w: max(0.0, raw["g"][w]) for w in base.scenarios}
    E = {w: data.emergency_price[w] * g[w] if option else 0.0 for w in base.scenarios}
    delivered = {w: sum(rel.fulfillment[w][j][k] * quantities[j][k]
                       for j in base.suppliers for k in rel.levels[j]) for w in base.scenarios}
    # Preserve the solver's q/z/y/g; select only the maximal-service x/u/h representative.
    x = {w: min(base.demand[w], delivered[w] + g[w]) for w in base.scenarios}
    u = {w: base.demand[w] - x[w] for w in base.scenarios}
    h = {w: delivered[w] + g[w] - x[w] for w in base.scenarios}
    losses = {w: E[w] + base.shortage_penalty * u[w] for w in base.scenarios}
    worst = max(base.scenarios, key=lambda w: losses[w])
    first = C_Q + C_R + fee
    equal(C_Q, pyo.value(model.C_Q), "C_Q")
    equal(C_R, pyo.value(model.C_R), "C_R")
    equal(raw["theta"], losses[worst], "worst scenario loss")
    equal(raw["objective"], first + losses[worst], "total economic objective")
    unused = {}
    for w in base.scenarios:
        upper(first + E[w], base.budget, "single lifecycle cash budget")
        if option:
            upper(E[w], data.option_cap * y, "option cap")
        if y == 0:
            equal(g[w], 0, "no procurement without Option")
            equal(E[w], 0, "no expenditure without Option")
        unused[w] = max(0.0, base.budget - first - E[w])
    return dict(objective=first + losses[worst], C_Q=C_Q, C_R=C_R, option_fee=fee, y_F=y,
                q=q, q_by_level=quantities, reliability_choice=choices, worst_scenario=worst,
                worst_loss=losses[worst], x=x, u=u, h=h, delivered=delivered, g=g, E=E,
                unused_budget=unused, raw_solution=raw)


def solve_mechanism(data, model, *, model_kind, restrictions, project_root=None,
                    config=SolverConfiguration(), audit_inputs=()):
    validate_solver_configuration(config)
    environment = ensure_preflight_once().to_dict()
    root = (project_root or Path(__file__).resolve().parents[3]).resolve()
    paths = sorted((root / "src/robust_budget_allocation").rglob("*.py"))
    paths.extend(root / p for p in ("pyproject.toml", "requirements.txt"))
    paths.extend(audit_inputs)
    settings = {**asdict(config), "MIPGap": 0.0, "MIPGapAbs": 0.0, "restrictions": restrictions}
    audit = {
        "classification": DEVELOPMENT_SCOPE, "source": build_source_manifest(root, input_paths=paths),
        "environment": environment, "data": data.to_dict(), "data_sha256": data.data_sha256,
        "base_data_sha256": data.base.data_sha256, "scenario_sha256": data.scenario_sha256,
        "solver_config": settings, "solver_config_sha256": canonical_json_sha256(settings),
        "numerical_checks": {"absolute_tolerance": ATOL, "relative_tolerance": RTOL,
                             "scope": "N3 development; not N4 E1 or algorithm acceptance"},
        "allocation_reporting": "maximal-service x/u/h at unchanged q/z/y/g; raw solution retained",
    }
    outcome = _solve_mip(model, config)
    audit["solver_outcome"] = asdict(outcome)
    common = dict(model_kind=model_kind, termination_condition=outcome.termination_condition,
                  runtime_seconds=outcome.runtime_seconds, audit=audit)
    if outcome.status != "optimal":
        return MechanismResult(status=outcome.status, diagnostics=(outcome.message or "no exact optimal solution",), **common)
    try:
        values = _extract(data, model, model_kind)
    except (ValueError, TypeError, ArithmeticError) as exc:
        return MechanismResult(status="numerical_invalid", diagnostics=(str(exc),), **common)
    return MechanismResult(status="optimal", **values, **common)
