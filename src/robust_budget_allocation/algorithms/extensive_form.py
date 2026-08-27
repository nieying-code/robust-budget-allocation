"""Full finite-scenario M2 baseline, sharing the frozen N3 model builder."""

from time import perf_counter

import pyomo.environ as pyo

from robust_budget_allocation.models.m2 import build_m2
from .common import audit, equal, finish, first_stage, solve_exact, summarize_first
from .exact_oracle import exact_oracle, validate_oracle


def build_extensive_form(data):
    return build_m2(data)


def solve_extensive_form(data, *, audit_inputs=()):
    provenance = audit(data, audit_inputs=audit_inputs)
    started = perf_counter()
    model = build_extensive_form(data)
    outcome = solve_exact(model)
    result = dict(method="EF", status=outcome["status"], solver=outcome, objective=None)
    if outcome["status"] == "optimal":
        try:
            decision = first_stage(data, model)
            summary = summarize_first(data, decision)
            eta = float(pyo.value(model.theta))
            oracle = exact_oracle(data, decision, eta)
            result.update(first_stage=decision, accounting=summary, eta=eta, oracle=oracle,
                          raw_recourse={w: {name: float(pyo.value(getattr(model, name)[w]))
                                           for name in ("g", "E", "x", "u", "h")} for w in data.base.scenarios})
            if oracle["status"] != "optimal":
                result["status"] = "oracle_failure"
            else:
                validate_oracle(data, decision, eta, oracle)
                equal(outcome["objective"], summary["first_cost"]+oracle["worst_loss"], "EF exact objective")
                equal(eta, oracle["worst_loss"], "EF theta")
                result["objective"] = summary["first_cost"]+oracle["worst_loss"]
        except (ValueError, TypeError, ArithmeticError, KeyError) as exc:
            result.update(status="numerical_failure", objective=None, diagnostic=str(exc))
    return finish(result, provenance, started)
