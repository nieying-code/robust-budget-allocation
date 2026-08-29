"""R4 A1 improved exact C&CG for the reviewed Q-F-R v2 model family."""

from __future__ import annotations

import math
from time import perf_counter
from typing import Any, Iterable

from robust_budget_allocation.data.qfr_data import QFRData
from robust_budget_allocation.io.hashing import canonical_json_sha256
from .qfr_a1_candidates import EVALUATION_LIMIT, candidate_plan
from .qfr_a1_memory import CAPACITY, INSPECTION_LIMIT, MAX_AGE, QFRScenarioMemory
from .qfr_exact_oracle import exact_oracle, solve_exact_recourse
from .qfr_protocol import canonical_scenarios, scenario_identities, tolerance
from .qfr_standard_ccg import _solve_master
from .qfr_state import QFRFirstStage, first_stage_cost


R4_PROTOCOL_PATH = "docs/R4_A1_PROTOCOL_v2.md"
R4_PROTOCOL_SHA256 = "5b493b3844210bb63180575ffc2dde5d74a883f75c93a9e8374b58f61b5306a6"
PROVISIONAL_MEMORY_PHASE_ENABLED = True


def a1_settings(*, memory_phase_enabled: bool) -> dict[str, Any]:
    return {
        "structure": (
            "MEMORY_CANDIDATE_FULL_EXACT"
            if memory_phase_enabled
            else "CANDIDATE_FULL_EXACT"
        ),
        "memory_phase_enabled": memory_phase_enabled,
        "memory_capacity": CAPACITY,
        "memory_max_age": MAX_AGE,
        "memory_inspection_limit": INSPECTION_LIMIT,
        "candidate_evaluation_limit": EVALUATION_LIMIT,
        "candidate_ranking": "CANONICAL_SCENARIO_ID_ONLY",
        "cross_solve_memory": False,
        "formal_ub_source": "FULL_EXACT_FINITE_SCENARIO_CERTIFICATION_ONLY",
        "r4_protocol_sha256": R4_PROTOCOL_SHA256,
    }


def _inspect(
    data: QFRData,
    decision: QFRFirstStage,
    theta: float,
    planned: Iterable[str],
) -> dict[str, Any]:
    evaluations: list[dict[str, Any]] = []
    selected: str | None = None
    for scenario in planned:
        row = solve_exact_recourse(data, decision, scenario)
        evaluations.append(row)
        if row["solver"]["status"] != "optimal":
            return {
                "status": "oracle_failure",
                "evaluations": evaluations,
                "selected": None,
                "hit": False,
            }
        loss = float(row["loss"])
        if max(0.0, loss - theta) > tolerance(loss, theta):
            selected = scenario
            break
    return {
        "status": "complete",
        "evaluations": evaluations,
        "selected": selected,
        "hit": selected is not None,
    }


def solve_qfr_improved_ccg(
    data: QFRData,
    model_kind: str,
    *,
    maximum_iterations: int | None = None,
    memory_phase_enabled: bool = PROVISIONAL_MEMORY_PHASE_ENABLED,
) -> dict[str, Any]:
    """Run exact A1; only complete full-Omega certification may set UB/converge."""

    data.validate()
    if type(memory_phase_enabled) is not bool:
        raise ValueError("memory_phase_enabled must be bool")
    ordered = canonical_scenarios(data)
    identities = scenario_identities(data)
    limit = len(ordered) + 1 if maximum_iterations is None else maximum_iterations
    if type(limit) is not int or limit <= 0 or limit > len(ordered) + 1:
        raise ValueError(
            "maximum_iterations must be a positive integer no greater than len(Omega)+1"
        )
    started = perf_counter()
    active = [ordered[0]]
    memory = QFRScenarioMemory(data.data_sha256, identities)
    trace: list[dict[str, Any]] = []
    incumbent: dict[str, Any] | None = None
    incumbent_ub: float | None = None
    final_lb: float | None = None
    status = "iteration_limit"
    diagnostic: str | None = None
    counters = {
        "memory_opportunities": 0,
        "memory_hits": 0,
        "candidate_hits": 0,
        "full_exact_certification_calls": 0,
        "complete_full_exact_certification_calls": 0,
        "scenario_evaluations": 0,
    }
    additions = [
        {
            "iteration": 0,
            "scenario_id": active[0],
            "scenario_identity": identities[active[0]],
            "source": "INITIAL",
        }
    ]
    for iteration in range(1, limit + 1):
        master, decision = _solve_master(data, model_kind, active)
        row: dict[str, Any] = {
            "iteration": iteration,
            "active_scenarios": list(active),
            "active_scenario_identities": [identities[value] for value in active],
            "master": master,
            "first_stage": None,
            "first_stage_sha256": None,
            "LB": None,
            "memory": None,
            "candidate": None,
            "full_exact_certification": None,
            "candidate_UB": None,
            "UB": incumbent_ub,
            "incumbent_iteration": None if incumbent is None else incumbent["iteration"],
            "signed_gap": None,
            "gap": None,
            "gap_tolerance": None,
            "violation": None,
            "violation_tolerance": None,
            "convergence": False,
            "added_scenario": None,
            "added_scenario_identity": None,
            "scenario_source": None,
        }
        trace.append(row)
        if decision is None:
            status = "master_failure"
            diagnostic = "restricted master did not return an accepted exact optimum"
            break
        final_lb = float(master["lower_bound"])
        theta = float(master["theta"])
        row.update(
            first_stage=decision.to_dict(),
            first_stage_sha256=decision.sha256,
            LB=final_lb,
        )
        selected: str | None = None
        source: str | None = None
        inspected: list[str] = []
        if memory_phase_enabled:
            before = memory.snapshot()
            removed = memory.prune(iteration)
            plan = memory.inspection_plan(active)
            if plan["planned"]:
                counters["memory_opportunities"] += 1
            phase = {
                "before": before,
                "removed": removed,
                "after_prune": memory.snapshot(),
                **plan,
            }
            phase.update(_inspect(data, decision, theta, plan["planned"]))
            row["memory"] = phase
            counters["scenario_evaluations"] += len(phase["evaluations"])
            if phase["status"] != "complete":
                status, diagnostic = "oracle_failure", "Memory exact evaluation failed"
                break
            phase["update"] = memory.update(phase["evaluations"], iteration, "MEMORY")
            phase["after"] = memory.snapshot()
            inspected = [entry["scenario_id"] for entry in phase["evaluations"]]
            selected = phase["selected"]
            if selected is not None:
                source = "MEMORY"
                counters["memory_hits"] += 1
        if selected is None:
            plan = candidate_plan(data, active, inspected)
            phase = dict(plan)
            phase.update(_inspect(data, decision, theta, plan["planned"]))
            row["candidate"] = phase
            counters["scenario_evaluations"] += len(phase["evaluations"])
            if phase["status"] != "complete":
                status, diagnostic = "oracle_failure", "Candidate exact evaluation failed"
                break
            if memory_phase_enabled:
                phase["memory_update"] = memory.update(
                    phase["evaluations"], iteration, "CANDIDATE"
                )
                phase["memory_after"] = memory.snapshot()
            selected = phase["selected"]
            if selected is not None:
                source = "CANDIDATE"
                counters["candidate_hits"] += 1
        if selected is None:
            counters["full_exact_certification_calls"] += 1
            oracle = exact_oracle(data, decision, theta)
            row["full_exact_certification"] = oracle
            counters["scenario_evaluations"] += int(oracle["evaluations"])
            if oracle["status"] != "complete":
                status, diagnostic = "oracle_failure", "Full exact certification was incomplete"
                break
            counters["complete_full_exact_certification_calls"] += 1
            if memory_phase_enabled:
                row["full_exact_memory_update"] = memory.update(
                    oracle["results"], iteration, "EXACT"
                )
                row["memory_after_full_exact"] = memory.snapshot()
            candidate_ub = first_stage_cost(data, decision) + float(oracle["worst_loss"])
            if incumbent_ub is None or candidate_ub < incumbent_ub:
                incumbent_ub = candidate_ub
                incumbent = {
                    "iteration": iteration,
                    "objective": candidate_ub,
                    "first_stage": decision.to_dict(),
                    "first_stage_sha256": decision.sha256,
                    "oracle": oracle,
                }
            assert incumbent is not None and incumbent_ub is not None
            signed_gap = incumbent_ub - final_lb
            gap_threshold = tolerance(incumbent_ub, final_lb)
            violation = float(oracle["violation"])
            violation_threshold = tolerance(float(oracle["worst_loss"]), theta)
            convergence = (
                -gap_threshold <= signed_gap <= gap_threshold
                and violation <= violation_threshold
            )
            row.update(
                candidate_UB=candidate_ub,
                UB=incumbent_ub,
                incumbent_iteration=incumbent["iteration"],
                signed_gap=signed_gap,
                gap=max(0.0, signed_gap),
                gap_tolerance=gap_threshold,
                violation=violation,
                violation_tolerance=violation_threshold,
                convergence=convergence,
            )
            if convergence:
                status = "certified"
                break
            if signed_gap < -gap_threshold:
                status, diagnostic = "numerical_failure", "formal UB crossed below master LB"
                break
            selected, source = str(oracle["worst_scenario"]), "EXACT"
            if violation <= violation_threshold:
                status = "convergence_failure"
                diagnostic = "failed global gap without a new exact violation"
                break
        else:
            phase = row["memory"] if source == "MEMORY" else row["candidate"]
            selected_row = next(
                entry for entry in phase["evaluations"] if entry["scenario_id"] == selected
            )
            loss = float(selected_row["loss"])
            row.update(
                violation=max(0.0, loss - theta),
                violation_tolerance=tolerance(loss, theta),
            )
        if selected in active or selected not in ordered:
            status, diagnostic = "convergence_failure", "invalid or duplicate scenario addition"
            break
        identity = identities[selected]
        row.update(
            added_scenario=selected,
            added_scenario_identity=identity,
            scenario_source=source,
        )
        additions.append(
            {
                "iteration": iteration,
                "scenario_id": selected,
                "scenario_identity": identity,
                "source": source,
            }
        )
        active = sorted([*active, selected])

    result: dict[str, Any] = {
        "schema_version": 1,
        "method": "R4_V2_A1_IMPROVED_CCG",
        "model_kind": model_kind,
        "status": status,
        "diagnostic": diagnostic,
        "data_sha256": data.data_sha256,
        "scenario_sha256": data.scenario_sha256,
        "settings": a1_settings(memory_phase_enabled=memory_phase_enabled),
        "canonical_scenarios": list(ordered),
        "scenario_identities": identities,
        "initial_scenario": ordered[0],
        "maximum_iterations": limit,
        "iterations": len(trace),
        **counters,
        "additions": additions,
        "trace": trace,
        "LB": final_lb,
        "UB": incumbent_ub,
        "objective": incumbent_ub if status == "certified" else None,
        "incumbent": incumbent,
        "runtime_seconds": perf_counter() - started,
    }
    result["result_sha256"] = canonical_json_sha256(result)
    return result
