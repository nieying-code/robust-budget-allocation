"""Frozen N4 numerical protocol, shared builder adapter and exact runtime."""

from dataclasses import asdict
import math
from pathlib import Path
from time import perf_counter

import pyomo.environ as pyo

from robust_budget_allocation.data.mechanism_data import OptionData
from robust_budget_allocation.io.hashing import canonical_json_sha256, sha256_file
from robust_budget_allocation.models.m2 import build_m2
from robust_budget_allocation.reproducibility.manifests import build_source_manifest
from robust_budget_allocation.runtime.environment import ensure_preflight_once
from robust_budget_allocation.runtime.solver import SolverConfiguration, create_solver, normalize_termination

ROOT = Path(__file__).resolve().parents[3]
PROTOCOL_PATH = "docs/N4_CORRECTNESS_PROTOCOL.md"
PROTOCOL_SHA256 = "f3c4d4ee2d352b4b5666cfb505a6fd5d61f0d2cdff7a15ab6c6a1f0a2ec0a72f"
ATOL, RTOL = 1e-7, 1e-9
CONFIG = SolverConfiguration(feasibility_tolerance=1e-9, optimality_tolerance=1e-9)
EXTRA_OPTIONS = {"MIPGap": 0.0, "MIPGapAbs": 0.0, "IntFeasTol": 1e-9}
SCOPE = "development/correctness_evidence"


def tolerance(a, b):
    if not math.isfinite(a) or not math.isfinite(b):
        raise ValueError("nonfinite comparison")
    return ATOL + RTOL * max(1.0, abs(a), abs(b))


def equal(a, b, label="equality"):
    if abs(a-b) > tolerance(a, b):
        raise ValueError(label)


def upper(a, b, label="upper bound"):
    if a-b > tolerance(a, b):
        raise ValueError(label)


def settings():
    return {**asdict(CONFIG), **EXTRA_OPTIONS}


def audit(data, *, audit_inputs=(), extra_config=None):
    data.validate()
    if sha256_file(ROOT / PROTOCOL_PATH) != PROTOCOL_SHA256:
        raise RuntimeError("frozen N4 correctness protocol hash mismatch")
    environment = ensure_preflight_once().to_dict()
    inputs = set((ROOT / "src/robust_budget_allocation").rglob("*.py"))
    inputs.update(ROOT / p for p in ("pyproject.toml", "requirements.txt", PROTOCOL_PATH))
    inputs.update(Path(p).resolve() for p in audit_inputs)
    config = {**settings(), **(extra_config or {})}
    return dict(classification=SCOPE, environment=environment,
                source=build_source_manifest(ROOT, input_paths=sorted(inputs)),
                data=data.to_dict(), data_sha256=data.data_sha256,
                scenario_order=list(data.base.scenarios), scenario_sha256=data.scenario_sha256,
                protocol_path=PROTOCOL_PATH, protocol_sha256=PROTOCOL_SHA256,
                config=config, config_sha256=canonical_json_sha256(config))


def finish(payload, provenance, started):
    payload.update(classification=SCOPE, audit=provenance,
                   runtime_seconds=perf_counter()-started)
    payload["result_sha256"] = canonical_json_sha256(payload)
    return payload


def subset_data(data, scenarios):
    scenarios = tuple(scenarios)
    if not scenarios or len(set(scenarios)) != len(scenarios) or not set(scenarios) <= set(data.base.scenarios):
        raise ValueError("master scenarios must be a nonempty unique subset of Omega")
    payload = data.to_dict()
    base = payload["reliability"]["base"]
    base["scenarios"] = list(scenarios)
    for key in ("demand", "base_fulfillment"):
        base[key] = {w: base[key][w] for w in scenarios}
    payload["reliability"]["fulfillment"] = {w: payload["reliability"]["fulfillment"][w] for w in scenarios}
    payload["emergency_price"] = {w: payload["emergency_price"][w] for w in scenarios}
    return OptionData.from_dict(payload)


def build_master(data, scenarios):
    """Reuse N3 equations unchanged; only the finite scenario index is restricted."""
    return build_m2(subset_data(data, scenarios))


def validate_loaded_model(model):
    for var in model.component_data_objects(pyo.Var):
        value = float(pyo.value(var))
        if not math.isfinite(value):
            raise ValueError("nonfinite variable: " + var.name)
        if var.has_lb(): upper(float(pyo.value(var.lb)), value, var.name)
        if var.has_ub(): upper(value, float(pyo.value(var.ub)), var.name)
        if var.is_integer(): equal(value, round(value), var.name + " integrality")
    for row in model.component_data_objects(pyo.Constraint, active=True):
        value = float(pyo.value(row.body))
        if not math.isfinite(value):
            raise ValueError("nonfinite constraint: " + row.name)
        if row.has_lb(): upper(float(pyo.value(row.lower)), value, row.name)
        if row.has_ub(): upper(value, float(pyo.value(row.upper)), row.name)


def solve_exact(model):
    # N1 preflight is cached and is outside this solver-only timer.
    solver = create_solver(CONFIG)
    solver.options.update(EXTRA_OPTIONS)
    start = perf_counter()
    outcome = dict(status="solver_error", solver_status=None, termination=None,
                   objective=None, lower_bound=None)
    try:
        raw = solver.solve(model, load_solutions=False, tee=False)
        outcome.update(solver_status=str(raw.solver.status), termination=str(raw.solver.termination_condition))
        outcome["status"] = normalize_termination(raw.solver.status, raw.solver.termination_condition)
        if outcome["status"] == "optimal":
            model.solutions.load_from(raw)
            try:
                validate_loaded_model(model)
                objective = float(pyo.value(model.total_cost))
                bound = float(raw.problem.lower_bound)
                equal(objective, bound, "solver primal/lower-bound mismatch")
                outcome.update(objective=objective, lower_bound=bound)
            except (ValueError, TypeError, ArithmeticError) as exc:
                outcome.update(status="numerical_failure", diagnostic=str(exc))
    except Exception as exc:
        outcome.update(status="solver_error", diagnostic=f"{type(exc).__name__}: {exc}")
    outcome["runtime_seconds"] = perf_counter()-start
    return outcome


def first_stage(data, model):
    rel, base = data.reliability, data.base
    choice = {}
    q = {}
    for j in base.suppliers:
        selected = [k for k in rel.levels[j] if round(pyo.value(model.z[j, k])) == 1]
        if len(selected) != 1:
            raise ValueError("invalid Reliability selection")
        choice[j] = selected[0]
        q[j] = {k: max(0.0, float(pyo.value(model.q_level[j, k]))) if k == selected[0] else 0.0 for k in rel.levels[j]}
    decision = dict(q_by_level=q, reliability_choice=choice, y_F=int(round(pyo.value(model.y_F))))
    summarize_first(data, decision)
    return decision


def summarize_first(data, decision):
    rel, base = data.reliability, data.base
    if set(decision) != {"q_by_level", "reliability_choice", "y_F"}:
        raise ValueError("first-stage schema")
    if type(decision["y_F"]) is not int or decision["y_F"] not in (0, 1):
        raise ValueError("invalid Option decision")
    for name in ("q_by_level", "reliability_choice"):
        if set(decision[name]) != set(base.suppliers): raise ValueError("supplier keys")
    cq = cr = 0.0
    q = {}
    for j in base.suppliers:
        chosen = decision["reliability_choice"][j]
        if chosen not in rel.levels[j] or set(decision["q_by_level"][j]) != set(rel.levels[j]):
            raise ValueError("Reliability level keys")
        q[j] = 0.0
        cr += rel.fixed_premium[j][chosen]
        for k, value in decision["q_by_level"][j].items():
            if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or value < 0:
                raise ValueError("invalid first-stage quantity")
            upper(value, base.procurement_limit[j] if k == chosen else 0, "quantity link")
            q[j] += value
            cq += base.unit_cost[j]*value
            cr += rel.unit_premium[j][k]*value
    fee = data.option_fee*decision["y_F"]
    first = cq+cr+fee
    upper(first, base.budget, "first-stage cash budget")
    return dict(q=q, C_Q=cq, C_R=cr, option_fee=fee, first_cost=first)


def fix_first(data, model, decision):
    summarize_first(data, decision)
    for j, k in model.JK:
        model.z[j, k].fix(int(k == decision["reliability_choice"][j]))
        model.q_level[j, k].fix(decision["q_by_level"][j][k])
    model.y_F.fix(decision["y_F"])
