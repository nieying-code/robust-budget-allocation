"""Recompute N4 development acceptance, including complete bound/incumbent traces."""

from .common import PROTOCOL_SHA256, equal, summarize_first, tolerance
from .exact_oracle import validate_oracle


def accepted_solver(outcome):
    if outcome["status"] != "optimal" or outcome["solver_status"] != "ok" or outcome["termination"] not in ("optimal", "globallyOptimal"):
        raise ValueError("solver outcome is not accepted exact optimal")
    equal(outcome["objective"], outcome["lower_bound"], "solver optimality gap")


def verify_pair(data, ef, a0):
    if ef["status"] != "optimal" or a0["status"] != "certified":
        raise ValueError("EF/A0 success requires both exact certificates")
    for result in (ef, a0):
        if result["audit"]["data_sha256"] != data.data_sha256 or result["audit"]["protocol_sha256"] != PROTOCOL_SHA256:
            raise ValueError("data/protocol mismatch")
    accepted_solver(ef["solver"])
    validate_oracle(data, ef["first_stage"], ef["eta"], ef["oracle"])
    ef_first = summarize_first(data, ef["first_stage"])["first_cost"]
    equal(ef["objective"], ef_first+ef["oracle"]["worst_loss"], "EF objective")
    equal(ef["solver"]["objective"], ef["objective"], "EF solver objective")
    lb = ub = None
    incumbent_iteration = None
    active = [min(data.base.scenarios)]
    trace = a0["trace"]
    if not trace or a0["iterations"] != len(trace) or a0["exact_oracle_calls"] != len(trace) or a0["complete_oracle_calls"] != len(trace):
        raise ValueError("one complete oracle per iteration is mandatory")
    if a0["scenario_evaluations"] != len(trace)*len(data.base.scenarios):
        raise ValueError("scenario evaluation count mismatch")
    for number, row in enumerate(trace, 1):
        if row["iteration"] != number or row["active_scenarios"] != active:
            raise ValueError("active scenario sequence mismatch")
        accepted_solver(row["master"])
        first = summarize_first(data, row["first_stage"])["first_cost"]
        equal(row["master"]["objective"], first+row["eta"], "master objective")
        validate_oracle(data, row["first_stage"], row["eta"], row["oracle"])
        lb = row["master"]["lower_bound"] if lb is None else max(lb, row["master"]["lower_bound"])
        candidate = first+row["oracle"]["worst_loss"]
        if ub is None or candidate < ub:
            ub, incumbent_iteration = candidate, number
        for key, value in dict(LB=lb, candidate_UB=candidate, UB=ub, signed_gap=ub-lb,
                               gap=max(0.0, ub-lb), violation=row["oracle"]["violation"],
                               gap_tolerance=tolerance(ub, lb),
                               violation_tolerance=tolerance(row["oracle"]["worst_loss"], row["eta"])).items():
            equal(row[key], value, "trace " + key)
        if row["incumbent_iteration"] != incumbent_iteration:
            raise ValueError("lost historical UB incumbent")
        converged = abs(ub-lb) <= tolerance(ub, lb) and row["violation"] <= row["violation_tolerance"]
        if row["convergence"] != converged or converged != (number == len(trace)):
            raise ValueError("premature or missing certification")
        if number < len(trace):
            added = row["added_scenario"]
            if added in active or added != row["oracle"]["worst_scenario"] or row["violation"] <= row["violation_tolerance"]:
                raise ValueError("no valid scenario progress")
            active = sorted([*active, added])
    incumbent = a0["incumbent"]
    source = trace[incumbent_iteration-1]
    if incumbent["iteration"] != incumbent_iteration or incumbent["first_stage"] != source["first_stage"] or incumbent["oracle"] != source["oracle"]:
        raise ValueError("incumbent is not bound to its generating full oracle")
    equal(incumbent["objective"], ub, "incumbent objective")
    equal(a0["LB"], lb, "final LB")
    equal(a0["UB"], ub, "final UB")
    equal(a0["objective"], ub, "A0 objective")
    equal(ef["objective"], a0["objective"], "EF/A0 objective difference")
    difference = abs(ef["objective"]-a0["objective"])
    return dict(status="PASS", objective_difference=difference,
                relative_objective_difference=difference/max(1.0, abs(ef["objective"]), abs(a0["objective"])),
                final_gap=trace[-1]["gap"], final_violation=trace[-1]["violation"],
                iterations=len(trace), exact_oracle_calls=a0["exact_oracle_calls"],
                all_scenario_incumbent_feasible=True)
