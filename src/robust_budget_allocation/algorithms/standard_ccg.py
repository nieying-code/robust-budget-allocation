"""A0 Standard C&CG: one complete finite-Omega exact oracle per master iteration."""

from time import perf_counter

import pyomo.environ as pyo

from .common import (audit, build_master, equal, finish, first_stage, solve_exact,
                     summarize_first, tolerance)
from .exact_oracle import exact_oracle, validate_oracle


def solve_a0(data, *, max_iterations=None, audit_inputs=()):
    limit = len(data.base.scenarios)+1 if max_iterations is None else max_iterations
    if type(limit) is not int or limit <= 0:
        raise ValueError("max_iterations must be a positive integer")
    provenance = audit(data, audit_inputs=audit_inputs, extra_config={"max_iterations": limit})
    started = perf_counter()
    active = [min(data.base.scenarios)]
    lb = ub = None
    incumbent = None
    trace = []
    result = dict(method="A0", status="iteration_limit", objective=None, trace=trace,
                  exact_oracle_calls=0, scenario_evaluations=0, complete_oracle_calls=0)
    for iteration in range(1, limit+1):
        model = build_master(data, active)
        outcome = solve_exact(model)
        row = dict(iteration=iteration, active_scenarios=list(active), master=outcome,
                   convergence=False, added_scenario=None)
        trace.append(row)
        if outcome["status"] != "optimal":
            result["status"] = outcome["status"]
            break
        try:
            decision = first_stage(data, model)
            summary = summarize_first(data, decision)
            eta = float(pyo.value(model.theta))
            equal(outcome["objective"], summary["first_cost"]+eta, "master cost")
            lb = outcome["lower_bound"] if lb is None else max(lb, outcome["lower_bound"])
            row.update(first_stage=decision, accounting=summary, eta=eta, LB=lb)
            result["exact_oracle_calls"] += 1
            oracle = exact_oracle(data, decision, eta)
            result["scenario_evaluations"] += len(oracle["scenarios"])
            row["oracle"] = oracle
            if oracle["status"] != "optimal":
                result["status"] = "oracle_failure"
                result["cause"] = oracle.get("cause", oracle["status"])
                break
            try:
                validate_oracle(data, decision, eta, oracle)
            except (ValueError, TypeError, KeyError, ArithmeticError) as exc:
                result.update(status="oracle_failure", diagnostic=str(exc))
                break
            result["complete_oracle_calls"] += 1
            candidate = summary["first_cost"]+oracle["worst_loss"]
            if ub is None or candidate < ub:
                ub = candidate
                incumbent = dict(iteration=iteration, first_stage=decision, accounting=summary,
                                 oracle=oracle, objective=candidate)
            signed_gap = ub-lb
            gap_tol = tolerance(ub, lb)
            violation_tol = tolerance(oracle["worst_loss"], eta)
            row.update(candidate_UB=candidate, UB=ub, incumbent_iteration=incumbent["iteration"],
                       signed_gap=signed_gap, gap=max(0.0, signed_gap), gap_tolerance=gap_tol,
                       violation=oracle["violation"], violation_tolerance=violation_tol)
            if signed_gap < -gap_tol:
                result["status"] = "numerical_failure"
                break
            if signed_gap <= gap_tol and oracle["violation"] <= violation_tol:
                row["convergence"] = True
                result.update(status="certified", objective=ub)
                break
            worst = oracle["worst_scenario"]
            if worst in active or oracle["violation"] <= violation_tol:
                result["status"] = "convergence_failure"
                break
            # Exhaustion is failure, not convergence, even if a new scenario exists.
            if iteration < limit:
                active = sorted([*active, worst])
                row["added_scenario"] = worst
        except (ValueError, TypeError, KeyError, ArithmeticError) as exc:
            result.update(status="numerical_failure", diagnostic=str(exc))
            break
    result.update(iterations=len(trace), LB=lb, UB=ub, incumbent=incumbent)
    return finish(result, provenance, started)
