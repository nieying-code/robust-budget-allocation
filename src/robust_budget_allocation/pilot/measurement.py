"""N6 adapters and observations; frozen builders and algorithms are untouched."""

from time import perf_counter
import pyomo.environ as pyo

from robust_budget_allocation.algorithms.common import equal, solve_exact, summarize_first, upper, tolerance
from robust_budget_allocation.algorithms.exact_oracle import canonical_recourse, validate_oracle
from robust_budget_allocation.algorithms.verification import accepted_solver
from robust_budget_allocation.algorithms.a1_verification import verify_a1
from robust_budget_allocation.models.m0 import build_m0
from robust_budget_allocation.models.m1 import build_m1


def solve_ablation(data, method):
    """Native full-scenario M0/M1 + unchanged N4 exact numerical acceptance."""
    started = perf_counter()
    model = build_m0(data.base) if method == "M0" else build_m1(data.reliability)
    outcome = solve_exact(model)
    result = dict(method=method, status=outcome["status"], solver=outcome, objective=None)
    if outcome["status"] == "optimal":
        if method == "M0":
            choice = {j: "0" for j in data.base.suppliers}
            qlevel = {j: {k: max(0., float(pyo.value(model.q[j]))) if k == "0" else 0.
                          for k in data.reliability.levels[j]} for j in data.base.suppliers}
        else:
            choice = {j: next(k for k in data.reliability.levels[j]
                              if round(pyo.value(model.z[j, k])) == 1) for j in data.base.suppliers}
            qlevel = {j: {k: max(0., float(pyo.value(model.q_level[j, k])))
                          for k in data.reliability.levels[j]} for j in data.base.suppliers}
        decision = dict(q_by_level=qlevel, reliability_choice=choice, y_F=0)
        accounting = summarize_first(data, decision)
        rows = [canonical_recourse(data, decision, w) for w in sorted(data.base.scenarios)]
        worst = min(rows, key=lambda r: (-r["loss"], r["scenario"]))
        result.update(first_stage=decision, accounting=accounting, scenarios=rows,
            worst_scenario=worst["scenario"], eta=float(pyo.value(model.theta)),
            objective=accounting["first_cost"]+worst["loss"],
            raw_recourse={w: {key: float(pyo.value(getattr(model, key)[w]))
                             for key in ("x", "u", "h")} for w in data.base.scenarios})
        verify_ablation(data, result)
    result["runtime_seconds"] = perf_counter()-started
    return result


def verify_ablation(data, result):
    accepted_solver(result["solver"])
    decision = result["first_stage"]
    if decision["y_F"] != 0 or (result["method"] == "M0" and
            any(k != "0" for k in decision["reliability_choice"].values())):
        raise ValueError("ablation restriction")
    summary = summarize_first(data, decision)
    if summary != result["accounting"]:
        raise ValueError("ablation accounting")
    rows = [canonical_recourse(data, decision, w) for w in sorted(data.base.scenarios)]
    if rows != result["scenarios"]:
        raise ValueError("ablation recourse")
    for row in rows:
        w, raw = row["scenario"], result["raw_recourse"][row["scenario"]]
        for value in raw.values():
            upper(0, value, "nonnegative raw ablation")
        equal(raw["x"]+raw["u"], data.base.demand[w], "ablation demand")
        equal(raw["x"]+raw["h"], row["delivered"], "ablation resource")
        upper(data.base.shortage_penalty*raw["u"], result["eta"], "ablation epigraph")
    worst = min(rows, key=lambda r: (-r["loss"], r["scenario"]))
    if result["worst_scenario"] != worst["scenario"]:
        raise ValueError("ablation worst ID")
    equal(result["eta"], worst["loss"], "ablation eta")
    equal(result["objective"], summary["first_cost"]+worst["loss"], "ablation total")
    equal(result["solver"]["objective"], result["objective"], "ablation solver")
    return True


def verify_engine(data, result):
    method = result["method"]
    if method in ("M0", "M1"):
        return verify_ablation(data, result)
    if method == "A1":
        verify_a1(data, result)
    if method == "EF":
        accepted_solver(result["solver"])
        decision, oracle, eta = result["first_stage"], result["oracle"], result["eta"]
        equal(result["solver"]["objective"], result["objective"], "EF solver objective")
    else:
        if result["status"] != "certified":
            raise ValueError("algorithm is not certified")
        inc = result["incumbent"]
        decision, oracle, eta = inc["first_stage"], inc["oracle"], inc["oracle"]["eta"]
        # Full A0 trace replay additionally occurs against EF at paired collection.
    validate_oracle(data, decision, eta, oracle)
    equal(result["objective"], summarize_first(data, decision)["first_cost"]+oracle["worst_loss"], "total")
    return True


def mechanism(data, result):
    if result["method"] in ("M0", "M1", "EF"):
        decision = result["first_stage"]
    else:
        decision = result["incumbent"]["first_stage"]
    first = summarize_first(data, decision)
    rows = [canonical_recourse(data, decision, w) for w in sorted(data.base.scenarios)]
    return dict(**first, y_F=decision["y_F"], reliability_choice=decision["reliability_choice"],
                paid_suppliers=sum(k != "0" for k in decision["reliability_choice"].values()),
                quantity=sum(first["q"].values()), scenarios=rows)


def metrics(result):
    trace = result.get("trace", [])
    if trace:
        final = trace[-1]
        fulls = [r.get("oracle") if result["method"] == "A0" else r.get("phase_iii") for r in trace]
        partials = [e for r in trace for phase in ("phase_i", "phase_ii")
                    for e in (r.get(phase) or {}).get("evaluations", [])]
        master = sum(r["master"]["runtime_seconds"] for r in trace)
        oracle = sum(o["runtime_seconds"] for o in fulls if o is not None)
        partial_solver = sum(e["solver"]["runtime_seconds"] for e in partials)
    else:
        final, partial_solver = {}, 0.
        master = result.get("solver", {}).get("runtime_seconds", 0.)
        oracle = result.get("oracle", {}).get("runtime_seconds", 0.)
        lb, ub = result["solver"]["lower_bound"], result["objective"]
        final = dict(gap=max(0., ub-lb), signed_gap=ub-lb,
                     gap_tolerance=tolerance(ub, lb),
                     violation=result.get("oracle", {}).get("violation", 0.))
    return dict(algorithm_seconds=result["runtime_seconds"], master_solve_seconds=master,
                full_oracle_seconds=oracle, partial_evaluation_solver_seconds=partial_solver,
                residual_seconds=result["runtime_seconds"]-master-oracle-partial_solver,
                objective=result["objective"], LB=result.get("LB", result.get("solver", {}).get("lower_bound")),
                UB=result.get("UB", result["objective"]),
                gap=final.get("gap"), signed_gap=final.get("signed_gap"),
                gap_tolerance=final.get("gap_tolerance"), exact_violation=final.get("violation"),
                iterations=result.get("iterations", 0), exact_oracle_calls=result.get("exact_oracle_calls", 0),
                complete_oracle_calls=result.get("complete_oracle_calls", 0),
                scenario_evaluations=result.get("scenario_evaluations", 0),
                phase_i_hits=result.get("phase_i_hits", 0), phase_ii_hits=result.get("phase_ii_hits", 0),
                phase_iii_calls=result.get("phase_iii_calls", 0),
                scenarios_added=sum(r.get("added_scenario") is not None for r in trace),
                active_size=len(final.get("active_scenarios", [])))
