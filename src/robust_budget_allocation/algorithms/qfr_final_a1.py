"""Final no-state-reuse A1: Candidate Search then Full Exact Certification."""

from __future__ import annotations

import math
from time import perf_counter
from typing import Any, Iterable, Mapping

from robust_budget_allocation.data.qfr_data import QFRData
from robust_budget_allocation.io.hashing import canonical_json_sha256
from .qfr_a1_candidates import EVALUATION_LIMIT, candidate_plan
from .qfr_exact_oracle import exact_oracle, solve_exact_recourse
from .qfr_numerical_validation import VALIDATION_RULE_ID
from .qfr_protocol import canonical_scenarios, scenario_identities, tolerance
from .qfr_standard_ccg import _solve_master
from .qfr_state import QFRFirstStage, first_stage_cost


FINAL_A1_IDENTITY = "A1_FINAL_NO_MEMORY_V1"
FINAL_A1_IMPLEMENTATION_REVISION = (
    "A1_FINAL_NO_MEMORY_V1_R1_WITNESS_GATED_INFEASIBLE_RETRY"
)


def final_a1_settings() -> dict[str, Any]:
    return {
        "algorithm_identity": FINAL_A1_IDENTITY,
        "implementation_revision": FINAL_A1_IMPLEMENTATION_REVISION,
        "structure": "CANDIDATE_SEARCH_THEN_FULL_EXACT_CERTIFICATION",
        "candidate_evaluation_limit": EVALUATION_LIMIT,
        "candidate_ranking": "CANONICAL_SCENARIO_ID_ONLY",
        "cross_solve_state_reuse": False,
        "formal_ub_source": "FULL_EXACT_FINITE_SCENARIO_CERTIFICATION_ONLY",
        "numerical_validation_rule": VALIDATION_RULE_ID,
        "exact_oracle_fallback": (
            "NUMERICAL_FAILURE_OR_WITNESS_GATED_INFEASIBLE_"
            "SCALED_CLONE_MAP_BACK"
        ),
    }


def _inspect_candidates(
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


def solve_qfr_final_a1(
    data: QFRData,
    model_kind: str,
    *,
    maximum_iterations: int | None = None,
) -> dict[str, Any]:
    """Run final A1; only complete full-Omega certification can set UB/converge."""

    data.validate()
    ordered = canonical_scenarios(data)
    identities = scenario_identities(data)
    limit = len(ordered) + 1 if maximum_iterations is None else maximum_iterations
    if type(limit) is not int or limit <= 0 or limit > len(ordered) + 1:
        raise ValueError(
            "maximum_iterations must be a positive integer no greater than len(Omega)+1"
        )

    started = perf_counter()
    active = [ordered[0]]
    trace: list[dict[str, Any]] = []
    incumbent: dict[str, Any] | None = None
    incumbent_ub: float | None = None
    final_lb: float | None = None
    status = "iteration_limit"
    diagnostic: str | None = None
    counters = {
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
            "candidate": None,
            "full_exact_certification": None,
            "full_exact_certification_iteration": None,
            "candidate_UB": None,
            "UB": None,
            "incumbent_iteration": None,
            "signed_gap": None,
            "gap": None,
            "gap_tolerance": None,
            "violation": None,
            "violation_tolerance": None,
            "convergence": None,
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

        plan = candidate_plan(data, active, ())
        candidate = dict(plan)
        candidate.update(_inspect_candidates(data, decision, theta, plan["planned"]))
        row["candidate"] = candidate
        counters["scenario_evaluations"] += len(candidate["evaluations"])
        if candidate["status"] != "complete":
            status, diagnostic = "oracle_failure", "Candidate exact evaluation failed"
            break

        selected = candidate["selected"]
        source: str | None = None
        if selected is not None:
            source = "CANDIDATE"
            counters["candidate_hits"] += 1
            selected_row = next(
                entry
                for entry in candidate["evaluations"]
                if entry["scenario_id"] == selected
            )
            loss = float(selected_row["loss"])
            row.update(
                violation=max(0.0, loss - theta),
                violation_tolerance=tolerance(loss, theta),
            )
        else:
            counters["full_exact_certification_calls"] += 1
            oracle = exact_oracle(data, decision, theta)
            row["full_exact_certification"] = oracle
            row["full_exact_certification_iteration"] = iteration
            counters["scenario_evaluations"] += int(oracle["evaluations"])
            if oracle["status"] != "complete":
                status, diagnostic = "oracle_failure", "Full exact certification was incomplete"
                break
            counters["complete_full_exact_certification_calls"] += 1
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
        "method": FINAL_A1_IDENTITY,
        "algorithm_identity": FINAL_A1_IDENTITY,
        "model_kind": model_kind,
        "status": status,
        "diagnostic": diagnostic,
        "data_sha256": data.data_sha256,
        "scenario_sha256": data.scenario_sha256,
        "settings": final_a1_settings(),
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
    validate_final_a1_result(result)
    return result


def validate_final_a1_result(result: Mapping[str, Any]) -> None:
    """Fail closed on the final algorithm identity and full certificate chain."""

    bare = dict(result)
    sealed = bare.pop("result_sha256", None)
    if sealed != canonical_json_sha256(bare):
        raise ValueError("Final A1 result seal mismatch")
    if result.get("method") != FINAL_A1_IDENTITY or result.get(
        "algorithm_identity"
    ) != FINAL_A1_IDENTITY:
        raise ValueError("Final A1 algorithm identity mismatch")
    if result.get("settings") != final_a1_settings():
        raise ValueError("Final A1 settings mismatch")
    runtime = float(result["runtime_seconds"])
    if not math.isfinite(runtime) or runtime < 0:
        raise ValueError("Final A1 runtime must be finite and nonnegative")
    if result.get("status") == "certified":
        incumbent = result.get("incumbent")
        if not isinstance(incumbent, Mapping):
            raise ValueError("certified Final A1 result lacks an incumbent")
        oracle = incumbent.get("oracle")
        if not isinstance(oracle, Mapping) or oracle.get("status") != "complete" or not oracle.get(
            "complete"
        ):
            raise ValueError("certified Final A1 result lacks full exact certification")
        if int(result.get("complete_full_exact_certification_calls", 0)) < 1:
            raise ValueError("candidate search cannot replace full exact certification")
