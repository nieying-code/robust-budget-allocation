"""Replay A1's three-phase proof without trusting stored scores, bounds or hits."""

from .a1_candidates import candidate_plan
from .a1_memory import ScenarioMemory
from .common import PROTOCOL_SHA256, equal, summarize_first, tolerance, upper
from .exact_oracle import canonical_recourse, validate_oracle
from .memory_guided_ccg import A1_PROTOCOL_SHA256
from .verification import accepted_solver, verify_pair


def validate_evaluation(data, decision, row):
    if row["status"] != "optimal":
        raise ValueError("partial-phase evaluation is not exact optimal")
    accepted_solver(row["solver"])
    expected = canonical_recourse(data, decision, row["scenario"])
    for key, value in expected.items():
        if key != "scenario": equal(row[key], value, "partial evaluation " + key)
    equal(row["solver"]["objective"], row["loss"], "partial optimal loss")
    raw, w = row["raw_solution"], row["scenario"]
    for name in ("g", "E", "x", "u", "h"): upper(0, raw[name], "raw nonnegative")
    equal(raw["E"], data.emergency_price[w]*raw["g"], "raw exercise cost")
    equal(raw["x"]+raw["u"], data.base.demand[w], "raw demand")
    equal(raw["x"]+raw["h"], expected["delivered"]+raw["g"], "raw resource")
    upper(raw["E"], data.option_cap*decision["y_F"], "raw option cap")
    upper(summarize_first(data, decision)["first_cost"]+raw["E"], data.base.budget, "raw cash")
    equal(raw["E"]+data.base.shortage_penalty*raw["u"], row["loss"], "raw objective")


def replay_inspection(data, decision, eta, phase, plan):
    for key, value in plan.items():
        if phase[key] != value: raise ValueError("inspection plan mismatch: " + key)
    if phase["status"] != "optimal": raise ValueError("failed inspection in certified trace")
    rows, selected = phase["evaluations"], None
    if len(rows) > len(plan["planned"]): raise ValueError("inspection budget exceeded")
    for index, row in enumerate(rows):
        if row["scenario"] != plan["planned"][index]: raise ValueError("inspection order mismatch")
        validate_evaluation(data, decision, row)
        if max(0.0, row["loss"]-eta) > tolerance(row["loss"], eta):
            selected = row["scenario"]
            if index != len(rows)-1: raise ValueError("evaluation continued after first hit")
    if selected is None and len(rows) != len(plan["planned"]): raise ValueError("unexplained early inspection stop")
    if phase["hit"] != (selected is not None) or phase["selected"] != selected: raise ValueError("hit/selection mismatch")
    return selected


def verify_a1(data, a1):
    if a1["status"] != "certified" or a1["certified"] is not True: raise ValueError("A1 is not certified")
    audit = a1["audit"]
    if audit["data_sha256"] != data.data_sha256 or audit["protocol_sha256"] != PROTOCOL_SHA256 or audit["a1_protocol_sha256"] != A1_PROTOCOL_SHA256:
        raise ValueError("A1 data/protocol mismatch")
    memory = ScenarioMemory(data.data_sha256, data.base.scenarios)
    active = [min(data.base.scenarios)]
    additions = [dict(iteration=0, scenario=active[0], source="INITIAL")]
    lb = ub = incumbent_iteration = None
    counters = dict(phase_i_hits=0, phase_ii_hits=0, phase_iii_calls=0,
                    exact_oracle_calls=0, complete_oracle_calls=0, scenario_evaluations=0)
    trace = a1["trace"]
    if not trace or a1["iterations"] != len(trace): raise ValueError("invalid trace length")
    for number, row in enumerate(trace, 1):
        if row["iteration"] != number or row["active_scenarios"] != active: raise ValueError("master sequence mismatch")
        accepted_solver(row["master"])
        decision, eta = row["first_stage"], row["eta"]
        first = summarize_first(data, decision)["first_cost"]
        equal(row["master"]["objective"], first+eta, "master objective")
        lb = row["master"]["lower_bound"] if lb is None else max(lb, row["master"]["lower_bound"])
        equal(row["LB"], lb, "LB")
        if row["memory_before"] != memory.snapshot(): raise ValueError("memory leaked or was not replayed")
        removed = memory.prune(number)
        phase = row["phase_i"]
        if phase is None or phase["removed"] != removed or phase["after_prune"] != memory.snapshot(): raise ValueError("memory prune mismatch")
        selected = replay_inspection(data, decision, eta, phase, memory.inspection_plan(active))
        counters["scenario_evaluations"] += len(phase["evaluations"])
        if phase["memory_update"] != memory.update(phase["evaluations"], number, "MEMORY") or phase["memory_after"] != memory.snapshot(): raise ValueError("memory update mismatch")
        source = "MEMORY"
        if selected is not None:
            counters["phase_i_hits"] += 1
            if row["phase_ii"] is not None: raise ValueError("Phase II ran after memory hit")
        else:
            phase = row["phase_ii"]
            if phase is None: raise ValueError("missing Phase II after memory miss")
            plan = candidate_plan(data, decision, active, [e["scenario"] for e in row["phase_i"]["evaluations"]])
            selected = replay_inspection(data, decision, eta, phase, plan)
            counters["scenario_evaluations"] += len(phase["evaluations"])
            if phase["memory_update"] != memory.update(phase["evaluations"], number, "CANDIDATE") or phase["memory_after"] != memory.snapshot(): raise ValueError("candidate memory update mismatch")
            source = "CANDIDATE"
            if selected is not None: counters["phase_ii_hits"] += 1
        converged = False
        if selected is not None:
            if row["phase_iii_called"] or row["phase_iii"] is not None or row["candidate_UB"] is not None:
                raise ValueError("Phase I/II cannot generate an exact UB or invoke Phase III on a hit")
            if row["UB"] != ub or row["incumbent_iteration"] != incumbent_iteration:
                raise ValueError("Phase I/II changed global UB/incumbent")
            loss = next(e["loss"] for e in phase["evaluations"] if e["scenario"] == selected)
            equal(row["violation"], max(0.0, loss-eta), "selected violation")
            equal(row["violation_tolerance"], tolerance(loss, eta), "selected tolerance")
            gap_fields = ("gap", "signed_gap", "gap_tolerance")
            if any(key not in row for key in gap_fields):
                raise ValueError("missing gap fields")
            if ub is None:
                if any(row[key] is not None for key in gap_fields):
                    raise ValueError("fabricated gap without full UB")
            else:
                equal(row["gap"], max(0.0, ub-lb), "historical gap")
                equal(row["signed_gap"], ub-lb, "historical signed gap")
                equal(row["gap_tolerance"], tolerance(ub, lb), "historical gap tolerance")
        else:
            if row["phase_iii_called"] is not True or row["phase_iii"] is None: raise ValueError("misses cannot skip exact certification")
            oracle = row["phase_iii"]
            validate_oracle(data, decision, eta, oracle)
            for name in ("phase_iii_calls", "exact_oracle_calls", "complete_oracle_calls"): counters[name] += 1
            counters["scenario_evaluations"] += len(oracle["scenarios"])
            if row["exact_memory_update"] != memory.update(oracle["scenarios"], number, "EXACT"): raise ValueError("full-oracle memory update mismatch")
            candidate = first+oracle["worst_loss"]
            if ub is None or candidate < ub: ub, incumbent_iteration = candidate, number
            for key, value in dict(candidate_UB=candidate, UB=ub, gap=max(0.0, ub-lb), signed_gap=ub-lb,
                                   gap_tolerance=tolerance(ub, lb), violation=oracle["violation"],
                                   violation_tolerance=tolerance(oracle["worst_loss"], eta)).items():
                equal(row[key], value, "exact trace " + key)
            if row["incumbent_iteration"] != incumbent_iteration: raise ValueError("lost incumbent")
            converged = abs(ub-lb) <= tolerance(ub, lb) and oracle["violation"] <= row["violation_tolerance"]
            selected, source = oracle["worst_scenario"], "EXACT"
        if row["memory_after"] != memory.snapshot(): raise ValueError("memory lifecycle mismatch")
        if row["convergence"] != converged or row["certified"] != converged or converged != (number == len(trace)):
            raise ValueError("premature or missing full certification")
        if not converged:
            if selected in active or row["added_scenario"] != selected or row["scenario_source"] != source: raise ValueError("duplicate/incorrect scenario addition")
            active = sorted([*active, selected])
            additions.append(dict(iteration=number, scenario=selected, source=source))
        elif row["added_scenario"] is not None or row["scenario_source"] is not None:
            raise ValueError("certified iteration added a scenario")
    if a1["additions"] != additions: raise ValueError("addition history mismatch")
    for key, value in counters.items():
        if a1[key] != value: raise ValueError("counter mismatch: " + key)
    incumbent = a1["incumbent"]
    producing = trace[incumbent_iteration-1]
    if incumbent["iteration"] != incumbent_iteration or incumbent["first_stage"] != producing["first_stage"] or incumbent["oracle"] != producing["phase_iii"]:
        raise ValueError("incumbent is not bound to producing Phase III")
    for key, value in (("LB", lb), ("UB", ub), ("objective", ub)): equal(a1[key], value, "final " + key)
    equal(incumbent["objective"], ub, "incumbent objective")
    return dict(status="PASS", final_gap=trace[-1]["gap"], final_violation=trace[-1]["violation"],
                full_omega_feasible=True, iterations=len(trace), **counters)


def verify_three(data, ef, a0, a1):
    verify_pair(data, ef, a0)
    checks = verify_a1(data, a1)
    equal(ef["objective"], a1["objective"], "EF/A1 objective")
    equal(a0["objective"], a1["objective"], "A0/A1 objective")
    values = [ef["objective"], a0["objective"], a1["objective"]]
    difference = max(values)-min(values)
    checks.update(max_objective_difference=difference, relative_objective_difference=difference/max(1.0, *map(abs, values)),
                  objectives=dict(EF=values[0], A0=values[1], A1=values[2]),
                  worst_losses=dict(EF=ef["oracle"]["worst_loss"], A0=a0["incumbent"]["oracle"]["worst_loss"], A1=a1["incumbent"]["oracle"]["worst_loss"]),
                  final_bounds=dict(A0_LB=a0["LB"], A0_UB=a0["UB"], A1_LB=a1["LB"], A1_UB=a1["UB"]))
    return checks
