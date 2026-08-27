"""Every-scenario exact recourse solves under fixed M2 first-stage decisions."""

from time import perf_counter

import pyomo.environ as pyo

from robust_budget_allocation.io.hashing import canonical_json_sha256
from .common import (build_master, equal, fix_first, solve_exact, summarize_first,
                     tolerance, upper)


def canonical_recourse(data, decision, scenario):
    """Closed-form single-resource LP value, independently checked against a solve."""
    if scenario not in data.base.scenarios:
        raise ValueError("unknown scenario")
    base, rel = data.base, data.reliability
    summary = summarize_first(data, decision)
    received = sum(rel.fulfillment[scenario][j][k]*decision["q_by_level"][j][k]
                   for j in base.suppliers for k in rel.levels[j])
    price, penalty = data.emergency_price[scenario], base.shortage_penalty
    remaining = max(0.0, base.budget-summary["first_cost"])
    g = min(max(0.0, base.demand[scenario]-received),
            data.option_cap*decision["y_F"]/price, remaining/price) if price < penalty else 0.0
    expenditure = price*g
    x = min(base.demand[scenario], received+g)
    u, h = base.demand[scenario]-x, received+g-x
    upper(summary["first_cost"]+expenditure, base.budget, "scenario cash budget")
    upper(expenditure, data.option_cap*decision["y_F"], "Option cap")
    return dict(scenario=scenario, delivered=received, g=g, E=expenditure, x=x, u=u, h=h,
                loss=expenditure+penalty*u,
                unused_budget=max(0.0, remaining-expenditure))


def evaluate_scenario(data, decision, scenario):
    model = build_master(data, [scenario])
    fix_first(data, model, decision)
    model.total_cost.set_value(model.E[scenario]+data.base.shortage_penalty*model.u[scenario])
    outcome = solve_exact(model)
    result = dict(scenario=scenario, status=outcome["status"], solver=outcome)
    if outcome["status"] != "optimal":
        return result
    try:
        expected = canonical_recourse(data, decision, scenario)
        raw = {name: float(pyo.value(getattr(model, name)[scenario])) for name in ("g", "E", "x", "u", "h")}
        equal(outcome["objective"], expected["loss"], "recourse LP/closed-form mismatch")
        result.update(expected, raw_solution=raw)
    except (ValueError, TypeError, ArithmeticError) as exc:
        result.update(status="numerical_failure", diagnostic=str(exc))
    return result


def exact_oracle(data, decision, eta):
    """No scenario subset parameter: the complete finite Omega is mandatory."""
    summarize_first(data, decision)
    tolerance(eta, 0)
    started = perf_counter()
    rows = []
    result = dict(status="oracle_failure", complete=False, data_sha256=data.data_sha256,
                  first_stage_sha256=canonical_json_sha256(decision), eta=eta,
                  scenario_order=sorted(data.base.scenarios), scenarios=rows)
    for w in sorted(data.base.scenarios):
        row = evaluate_scenario(data, decision, w)
        rows.append(row)
        if row["status"] != "optimal":
            result.update(cause=row["status"], runtime_seconds=perf_counter()-started)
            return result
    worst = min(rows, key=lambda r: (-r["loss"], r["scenario"]))
    result.update(status="optimal", complete=True, worst_scenario=worst["scenario"],
                  worst_loss=worst["loss"], violation=max(0.0, worst["loss"]-eta),
                  runtime_seconds=perf_counter()-started)
    validate_oracle(data, decision, eta, result)
    return result


def validate_oracle(data, decision, eta, result):
    """Require complete, decision-bound, optimal and recomputable proof before UB."""
    if result["status"] != "optimal" or result["complete"] is not True:
        raise ValueError("oracle is not a full optimal certificate")
    if result["data_sha256"] != data.data_sha256 or result["first_stage_sha256"] != canonical_json_sha256(decision):
        raise ValueError("oracle data/decision mismatch")
    expected_order = sorted(data.base.scenarios)
    if result["scenario_order"] != expected_order or [r["scenario"] for r in result["scenarios"]] != expected_order:
        raise ValueError("oracle omits, repeats or reorders scenarios")
    for row in result["scenarios"]:
        solver = row["solver"]
        if row["status"] != "optimal" or solver["status"] != "optimal" or solver["solver_status"] != "ok" or solver["termination"] not in ("optimal", "globallyOptimal"):
            raise ValueError("uncertified scenario")
        expected = canonical_recourse(data, decision, row["scenario"])
        for key, value in expected.items():
            if key != "scenario": equal(row[key], value, "oracle " + key)
        raw = row["raw_solution"]
        w = row["scenario"]
        for name in ("g", "E", "x", "u", "h"):
            upper(0, raw[name], "raw recourse nonnegative")
        equal(raw["E"], data.emergency_price[w]*raw["g"], "raw expenditure")
        equal(raw["x"]+raw["u"], data.base.demand[w], "raw demand")
        equal(raw["x"]+raw["h"], expected["delivered"]+raw["g"], "raw resource")
        upper(raw["E"], data.option_cap*decision["y_F"], "raw cap")
        upper(summarize_first(data, decision)["first_cost"]+raw["E"], data.base.budget, "raw cash")
        equal(raw["E"]+data.base.shortage_penalty*raw["u"], solver["objective"], "raw recourse objective")
        equal(solver["objective"], row["loss"], "oracle objective")
        equal(solver["lower_bound"], row["loss"], "oracle bound")
    worst = min(result["scenarios"], key=lambda r: (-r["loss"], r["scenario"]))
    if result["worst_scenario"] != worst["scenario"]:
        raise ValueError("noncanonical worst ID")
    equal(result["worst_loss"], worst["loss"], "maximum loss")
    equal(result["eta"], eta, "eta binding")
    equal(result["violation"], max(0.0, worst["loss"]-eta), "maximum violation")
