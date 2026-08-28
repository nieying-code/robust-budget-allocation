"""Preregistered Option gate and lightweight Memory opportunity counts, not inference."""

from robust_budget_allocation.algorithms.common import tolerance
from robust_budget_allocation.pilot.measurement import mechanism, metrics
from .configuration import registration, SCOPE


def effective(m1_objective, m2_objective, observed):
    exercise = [r["scenario"] for r in observed["scenarios"]
                if r["g"] > tolerance(r["g"], 0) and r["E"] > tolerance(r["E"], 0)]
    delta = m1_objective-m2_objective
    threshold = tolerance(m1_objective, m2_objective)
    return dict(purchase=observed["y_F"] == 1, exercise_scenarios=exercise,
        objective_improvement=delta, numerical_tolerance=threshold,
        improvement_not_equivalent=delta > threshold,
        EFFECTIVE_OPTION_ACTIVE=observed["y_F"] == 1 and bool(exercise) and delta > threshold)


def memory_diagnosis(a1):
    rows, first = [], None
    relevant = False
    for row in a1["trace"]:
        iteration = row["iteration"]
        if first is None and row["memory_after"]:
            first = iteration
        phase = row["phase_i"] or {}
        eligible = [e["scenario"] for e in phase.get("ranking", [])]
        nonterminal = not row["certified"] and row["added_scenario"] is not None
        opportunity = bool(row["memory_before"]) and nonterminal and bool(eligible)
        evals = [e for name in ("phase_i", "phase_ii")
                 for e in (row.get(name) or {}).get("evaluations", [])]
        evals += (row.get("phase_iii") or {}).get("scenarios", [])
        active_exercise = row["first_stage"]["y_F"] == 1 and any(
            e["g"] > tolerance(e["g"], 0) and e["E"] > tolerance(e["E"], 0) for e in evals)
        relevant |= active_exercise
        rows.append(dict(iteration=iteration, memory_before=row["memory_before"],
            memory_after=row["memory_after"], nonterminal=nonterminal,
            later_than_first_population=first is not None and iteration > first,
            eligible_ids=eligible, planned=phase.get("planned", []), evaluations=phase.get("evaluations", []),
            phase_i_hit=phase.get("hit", False), opportunity=opportunity,
            eligible_terminal=bool(eligible) and row["certified"], option_active_evaluation=active_exercise))
    return dict(first_population_iteration=first, relevant_option_active_trajectory=relevant,
        opportunities=sum(r["opportunity"] for r in rows),
        eligible_terminal_iterations=sum(r["eligible_terminal"] for r in rows),
        later_nonterminal_iterations=sum(r["later_than_first_population"] and r["nonterminal"] for r in rows),
        phase_i_hits=a1["phase_i_hits"], rows=rows)


def observation(config, data, engines, checks):
    m2 = mechanism(data, engines["EF"])
    return dict(classification=SCOPE, config=config,
        objectives={m: e["objective"] for m, e in engines.items()},
        models={m: mechanism(data, engines[m]) for m in ("M0", "M1", "EF")},
        option=effective(engines["M1"]["objective"], engines["EF"]["objective"], m2),
        memory=memory_diagnosis(engines["A1"]), correctness=checks,
        workload={m: metrics(engines[m]) for m in ("A0", "A1")})


def option_gate(observations):
    configs = registration()["configs"][:18]
    actual = [o for o in observations if o["config"]["layer"] == 1]
    if [o["config"] for o in actual] != configs:
        raise ValueError("Gate M requires complete ordered Layer 1")
    counts = {str(b): sum(o["option"]["EFFECTIVE_OPTION_ACTIVE"] for o in actual
                         if o["config"]["budget"] == b) for b in (45, 90, 150)}
    state = "PASSED" if max(counts.values()) >= 3 else ("INCONCLUSIVE" if sum(counts.values()) else "FAILED")
    return dict(status="N7_PRE_OPTION_GATE_"+state, cell_counts=counts, denominator=6)


def summarize(observations):
    configs = registration()["configs"]
    if [o["config"] for o in observations] != configs[:len(observations)]:
        raise ValueError("observation order or duplicates")
    gate = option_gate(observations) if len(observations) >= 18 else None
    cells = []
    for regime in ("F", "R", "B"):
        for budget in (45, 90, 150):
            rows = [o for o in observations if o["config"]["regime"] == regime and o["config"]["budget"] == budget]
            cells.append(dict(regime=regime, budget=budget, completed=len(rows),
                effective=sum(o["option"]["EFFECTIVE_OPTION_ACTIVE"] for o in rows), denominator=6,
                seeds=[dict(seed=o["config"]["seed"], effective=o["option"]["EFFECTIVE_OPTION_ACTIVE"])
                       for o in rows]))
    relevant = [o for o in observations if o["memory"]["relevant_option_active_trajectory"]]
    opportunities = sum(o["memory"]["opportunities"] for o in relevant)
    hits = sum(o["memory"]["phase_i_hits"] for o in relevant)
    decision = "N7_PRE_MEMORY_NOT_IDENTIFIED" if not opportunities else (
        "N7_PRE_MEMORY_REVIEW_REQUIRED" if hits else "MEMORY_REMOVAL_REQUIRES_NEW_CORRECTNESS")
    return dict(classification=SCOPE, completed_configs=len(observations), gate=gate, cells=cells,
        relevant_runs=len(relevant), relevant_opportunities=opportunities, relevant_phase_i_hits=hits,
        all_opportunities=sum(o["memory"]["opportunities"] for o in observations), memory_decision=decision,
        totals={m: {k: sum(o["workload"][m][k] for o in observations) for k in
                ("phase_i_hits", "phase_ii_hits", "phase_iii_calls", "exact_oracle_calls", "complete_oracle_calls",
                 "scenario_evaluations", "iterations", "scenarios_added")} for m in ("A0", "A1")})
