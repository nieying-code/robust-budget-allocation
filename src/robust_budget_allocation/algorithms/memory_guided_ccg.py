"""A1: memory -> candidate -> full exact certification, with solve-local state."""

from time import perf_counter

import pyomo.environ as pyo

from robust_budget_allocation.io.hashing import sha256_file
from .a1_candidates import candidate_plan, EVALUATION_LIMIT
from .a1_memory import ScenarioMemory, CAPACITY, MAX_AGE, INSPECTION_LIMIT
from .common import (ROOT, audit, build_master, equal, finish, first_stage,
                     solve_exact, summarize_first, tolerance)
from .exact_oracle import evaluate_scenario, exact_oracle, validate_oracle

A1_PROTOCOL_PATH = "docs/N5_A1_PROTOCOL.md"
A1_PROTOCOL_SHA256 = "c674f64297e6ad47fca0feeb593cd31202f370a6c567d5620d7f26ccab360a12"


def a1_settings():
    return dict(memory_capacity=CAPACITY, memory_max_age=MAX_AGE,
                memory_inspection_limit=INSPECTION_LIMIT, candidate_evaluation_limit=EVALUATION_LIMIT,
                candidate_score="s*max(d-regular_delivered,0)", cross_solve_memory=False,
                a1_protocol_sha256=A1_PROTOCOL_SHA256)


def inspect(data, decision, eta, planned):
    rows, selected = [], None
    for w in planned:
        evaluated = evaluate_scenario(data, decision, w)
        rows.append(evaluated)
        if evaluated["status"] != "optimal":
            return dict(status="oracle_failure", cause=evaluated["status"], evaluations=rows, selected=None, hit=False)
        violation = max(0.0, evaluated["loss"]-eta)
        if violation > tolerance(evaluated["loss"], eta):
            selected = w
            break
    return dict(status="optimal", evaluations=rows, selected=selected, hit=selected is not None)


def solve_a1(data, *, max_iterations=None, audit_inputs=()):
    limit = len(data.base.scenarios)+1 if max_iterations is None else max_iterations
    if type(limit) is not int or limit <= 0:
        raise ValueError("max_iterations must be a positive integer")
    if sha256_file(ROOT / A1_PROTOCOL_PATH) != A1_PROTOCOL_SHA256:
        raise RuntimeError("frozen N5 A1 protocol hash mismatch")
    provenance = audit(data, audit_inputs=(*audit_inputs, ROOT / A1_PROTOCOL_PATH),
                       extra_config={"max_iterations": limit, **a1_settings()})
    provenance.update(a1_protocol_path=A1_PROTOCOL_PATH, a1_protocol_sha256=A1_PROTOCOL_SHA256)
    started = perf_counter()
    active = [min(data.base.scenarios)]
    memory = ScenarioMemory(data.data_sha256, data.base.scenarios)
    lb = ub = incumbent = None
    trace = []
    result = dict(method="A1", status="iteration_limit", certified=False, objective=None, trace=trace,
                  additions=[dict(iteration=0, scenario=active[0], source="INITIAL")],
                  phase_i_hits=0, phase_ii_hits=0, phase_iii_calls=0, exact_oracle_calls=0,
                  complete_oracle_calls=0, scenario_evaluations=0)
    for iteration in range(1, limit+1):
        model = build_master(data, active)
        outcome = solve_exact(model)
        row = dict(iteration=iteration, active_scenarios=list(active), master=outcome,
                   memory_before=memory.snapshot(), phase_i=None, phase_ii=None, phase_iii=None,
                   phase_iii_called=False, candidate_UB=None, UB=ub, LB=lb,
                   incumbent_iteration=incumbent["iteration"] if incumbent else None,
                   gap=None, violation=None, convergence=False, certified=False,
                   added_scenario=None, scenario_source=None, status=outcome["status"])
        trace.append(row)
        if outcome["status"] != "optimal":
            result["status"] = outcome["status"]
            row["memory_after"] = memory.snapshot()
            break
        try:
            decision = first_stage(data, model)
            summary = summarize_first(data, decision)
            eta = float(pyo.value(model.theta))
            equal(outcome["objective"], summary["first_cost"]+eta, "master accounting")
            lb = outcome["lower_bound"] if lb is None else max(lb, outcome["lower_bound"])
            row.update(first_stage=decision, accounting=summary, eta=eta, LB=lb)
            if ub is not None:
                row.update(gap=max(0.0, ub-lb), signed_gap=ub-lb, gap_tolerance=tolerance(ub, lb))
                if ub-lb < -tolerance(ub, lb):
                    result["status"] = "numerical_failure"
                    break
            removed = memory.prune(iteration)
            memory_plan = memory.inspection_plan(active)
            phase_i = dict(removed=removed, after_prune=memory.snapshot(), **memory_plan)
            row["phase_i"] = phase_i
            phase_i.update(inspect(data, decision, eta, memory_plan["planned"]))
            result["scenario_evaluations"] += len(phase_i["evaluations"])
            if phase_i["status"] != "optimal":
                result.update(status="oracle_failure", cause=phase_i["cause"])
                break
            phase_i["memory_update"] = memory.update(phase_i["evaluations"], iteration, "MEMORY")
            phase_i["memory_after"] = memory.snapshot()
            selected, source = phase_i["selected"], "MEMORY"
            if selected is not None:
                result["phase_i_hits"] += 1
            else:
                inspected = [e["scenario"] for e in phase_i["evaluations"]]
                phase_ii = candidate_plan(data, decision, active, inspected)
                row["phase_ii"] = phase_ii
                phase_ii.update(inspect(data, decision, eta, phase_ii["planned"]))
                result["scenario_evaluations"] += len(phase_ii["evaluations"])
                if phase_ii["status"] != "optimal":
                    result.update(status="oracle_failure", cause=phase_ii["cause"])
                    break
                phase_ii["memory_update"] = memory.update(phase_ii["evaluations"], iteration, "CANDIDATE")
                phase_ii["memory_after"] = memory.snapshot()
                selected, source = phase_ii["selected"], "CANDIDATE"
                if selected is not None:
                    result["phase_ii_hits"] += 1
            if selected is None:
                result["phase_iii_calls"] += 1
                result["exact_oracle_calls"] += 1
                row["phase_iii_called"] = True
                oracle = exact_oracle(data, decision, eta)
                row["phase_iii"] = oracle
                result["scenario_evaluations"] += len(oracle["scenarios"])
                if oracle["status"] != "optimal":
                    result.update(status="oracle_failure", cause=oracle.get("cause", oracle["status"]))
                    break
                try:
                    validate_oracle(data, decision, eta, oracle)
                except (ValueError, TypeError, KeyError, ArithmeticError) as exc:
                    result.update(status="oracle_failure", diagnostic=str(exc))
                    break
                result["complete_oracle_calls"] += 1
                row["exact_memory_update"] = memory.update(oracle["scenarios"], iteration, "EXACT")
                candidate = summary["first_cost"]+oracle["worst_loss"]
                if ub is None or candidate < ub:
                    ub = candidate
                    incumbent = dict(iteration=iteration, first_stage=decision, accounting=summary,
                                     oracle=oracle, objective=candidate)
                row.update(candidate_UB=candidate, UB=ub, incumbent_iteration=incumbent["iteration"],
                           signed_gap=ub-lb, gap=max(0.0, ub-lb), gap_tolerance=tolerance(ub, lb),
                           violation=oracle["violation"], violation_tolerance=tolerance(oracle["worst_loss"], eta))
                if ub-lb < -row["gap_tolerance"]:
                    result["status"] = "numerical_failure"
                    break
                if ub-lb <= row["gap_tolerance"] and oracle["violation"] <= row["violation_tolerance"]:
                    row.update(convergence=True, certified=True)
                    result.update(status="certified", certified=True, objective=ub)
                    break
                selected, source = oracle["worst_scenario"], "EXACT"
                if oracle["violation"] <= row["violation_tolerance"]:
                    result["status"] = "convergence_failure"
                    break
            else:
                phase = row["phase_i"] if source == "MEMORY" else row["phase_ii"]
                loss = next(e["loss"] for e in phase["evaluations"] if e["scenario"] == selected)
                row.update(violation=max(0.0, loss-eta), violation_tolerance=tolerance(loss, eta))
            if selected in active or selected not in data.base.scenarios:
                result["status"] = "convergence_failure"
                break
            if iteration < limit:
                row.update(added_scenario=selected, scenario_source=source)
                active = sorted([*active, selected])
                result["additions"].append(dict(iteration=iteration, scenario=selected, source=source))
        except (ValueError, TypeError, ArithmeticError, KeyError) as exc:
            result.update(status="numerical_failure", diagnostic=str(exc))
            break
        finally:
            row["memory_after"] = memory.snapshot()
    if trace:
        trace[-1]["status"] = result["status"]
    result.update(iterations=len(trace), LB=lb, UB=ub, incumbent=incumbent)
    return finish(result, provenance, started)
