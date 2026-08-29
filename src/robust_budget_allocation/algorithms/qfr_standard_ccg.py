"""A0 Standard exact finite-scenario C&CG for Q-F-R v2."""

from __future__ import annotations

import math
from time import perf_counter
from typing import Any, Mapping

import pyomo.environ as pyo

from robust_budget_allocation.data.qfr_data import QFRData
from robust_budget_allocation.io.hashing import canonical_json_sha256
from robust_budget_allocation.models.qfr_support import validate_qfr_solution
from .qfr_builders import build_qfr_restricted_master
from .qfr_exact_oracle import exact_oracle, validate_oracle
from .qfr_protocol import (
    accepted_outcome,
    canonical_scenarios,
    require_close,
    scenario_identities,
    solve_exact,
    subset_data,
    tolerance,
)
from .qfr_state import QFRFirstStage, extract_first_stage, first_stage_cost, validate_first_stage


def _solve_master(
    data: QFRData,
    model_kind: str,
    active_scenarios: list[str],
) -> tuple[dict[str, Any], QFRFirstStage | None]:
    restricted = subset_data(data, tuple(active_scenarios))
    model = build_qfr_restricted_master(restricted, model_kind)
    outcome = solve_exact(model)
    result: dict[str, Any] = {
        "active_scenarios": list(active_scenarios),
        "active_scenario_identities": [
            scenario_identities(data)[scenario] for scenario in active_scenarios
        ],
        "restricted_data_sha256": restricted.data_sha256,
        "restricted_scenario_sha256": restricted.scenario_sha256,
        "solver": outcome.to_dict(),
        "objective": outcome.objective,
        "lower_bound": outcome.lower_bound,
        "theta": None,
        "first_stage_sha256": None,
        "accounting": None,
    }
    if outcome.status != "optimal":
        return result, None
    accounting = validate_qfr_solution(restricted, model, tolerance=1e-7)
    decision = extract_first_stage(data, model)
    result.update(
        theta=float(pyo.value(model.theta)),
        first_stage_sha256=decision.sha256,
        accounting=accounting.to_dict(),
    )
    return result, decision


def solve_qfr_standard_ccg(
    data: QFRData,
    model_kind: str,
    *,
    maximum_iterations: int | None = None,
) -> dict[str, Any]:
    """Run A0 with a complete exact oracle on every successful master iteration."""

    data.validate()
    started = perf_counter()
    ordered = canonical_scenarios(data)
    identities = scenario_identities(data)
    limit = len(ordered) + 1 if maximum_iterations is None else maximum_iterations
    if type(limit) is not int or limit <= 0 or limit > len(ordered) + 1:
        raise ValueError("maximum_iterations must be a positive integer no greater than len(Omega)+1")
    active = [ordered[0]]
    trace: list[dict[str, Any]] = []
    incumbent: dict[str, Any] | None = None
    incumbent_ub: float | None = None
    final_lb: float | None = None
    status = "iteration_limit"
    diagnostic: str | None = None
    for iteration in range(1, limit + 1):
        master, decision = _solve_master(data, model_kind, active)
        row: dict[str, Any] = {
            "iteration": iteration,
            "active_scenarios": list(active),
            "active_scenario_identities": [identities[value] for value in active],
            "master": master,
            "first_stage": None,
            "first_stage_sha256": None,
            "oracle": None,
            "LB": None,
            "candidate_UB": None,
            "UB": incumbent_ub,
            "incumbent_iteration": None if incumbent is None else incumbent["iteration"],
            "signed_gap": None,
            "gap": None,
            "gap_tolerance": None,
            "violation": None,
            "violation_tolerance": None,
            "gap_pass": False,
            "violation_pass": False,
            "convergence": False,
            "added_scenario": None,
            "added_scenario_identity": None,
        }
        if decision is None:
            status = "master_failure"
            diagnostic = "restricted master did not return an accepted exact optimum"
            trace.append(row)
            break
        final_lb = float(master["lower_bound"])
        theta = float(master["theta"])
        oracle = exact_oracle(data, decision, theta)
        row.update(
            first_stage=decision.to_dict(),
            first_stage_sha256=decision.sha256,
            oracle=oracle,
            LB=final_lb,
        )
        if oracle["status"] != "complete":
            status = "oracle_failure"
            diagnostic = "full finite-scenario oracle was incomplete"
            trace.append(row)
            break
        candidate = first_stage_cost(data, decision) + float(oracle["worst_loss"])
        if incumbent_ub is None or candidate < incumbent_ub:
            incumbent_ub = candidate
            incumbent = {
                "iteration": iteration,
                "objective": candidate,
                "first_stage": decision.to_dict(),
                "first_stage_sha256": decision.sha256,
                "oracle": oracle,
            }
        assert incumbent is not None and incumbent_ub is not None
        signed_gap = incumbent_ub - final_lb
        gap_threshold = tolerance(incumbent_ub, final_lb)
        violation = float(oracle["violation"])
        violation_threshold = tolerance(float(oracle["worst_loss"]), theta)
        gap_pass = -gap_threshold <= signed_gap <= gap_threshold
        violation_pass = violation <= violation_threshold
        convergence = gap_pass and violation_pass
        row.update(
            candidate_UB=candidate,
            UB=incumbent_ub,
            incumbent_iteration=incumbent["iteration"],
            signed_gap=signed_gap,
            gap=max(0.0, signed_gap),
            gap_tolerance=gap_threshold,
            violation=violation,
            violation_tolerance=violation_threshold,
            gap_pass=gap_pass,
            violation_pass=violation_pass,
            convergence=convergence,
        )
        if convergence:
            status = "certified"
            trace.append(row)
            break
        if signed_gap < -gap_threshold:
            status = "numerical_failure"
            diagnostic = "formal UB crossed below restricted-master LB beyond tolerance"
            trace.append(row)
            break
        worst = str(oracle["worst_scenario"])
        worst_identity = identities[worst]
        represented = worst_identity in {identities[value] for value in active}
        if violation > violation_threshold and not represented:
            row["added_scenario"] = worst
            row["added_scenario_identity"] = worst_identity
            active = sorted([*active, worst])
            trace.append(row)
            continue
        status = "convergence_failure"
        diagnostic = (
            "gap did not pass but the exact oracle supplied no new violating scientific scenario"
        )
        trace.append(row)
        break
    result: dict[str, Any] = {
        "schema_version": 1,
        "method": "R3_V2_A0_STANDARD_CCG",
        "model_kind": model_kind,
        "status": status,
        "diagnostic": diagnostic,
        "data_sha256": data.data_sha256,
        "scenario_sha256": data.scenario_sha256,
        "canonical_scenarios": list(ordered),
        "scenario_identities": identities,
        "initial_scenario": ordered[0],
        "maximum_iterations": limit,
        "iterations": len(trace),
        "exact_oracle_calls": sum(row["oracle"] is not None for row in trace),
        "complete_oracle_calls": sum(
            row["oracle"] is not None and row["oracle"].get("complete") is True for row in trace
        ),
        "scenario_evaluations": sum(
            0 if row["oracle"] is None else int(row["oracle"]["evaluations"]) for row in trace
        ),
        "trace": trace,
        "LB": final_lb,
        "UB": incumbent_ub,
        "objective": incumbent_ub if status == "certified" else None,
        "incumbent": incumbent,
        "runtime_seconds": perf_counter() - started,
    }
    result["result_sha256"] = canonical_json_sha256(result)
    if status == "certified":
        validate_standard_ccg_result(data, result)
    return result


def validate_standard_ccg_result(data: QFRData, result: Mapping[str, Any]) -> None:
    required = {
        "schema_version",
        "method",
        "model_kind",
        "status",
        "diagnostic",
        "data_sha256",
        "scenario_sha256",
        "canonical_scenarios",
        "scenario_identities",
        "initial_scenario",
        "maximum_iterations",
        "iterations",
        "exact_oracle_calls",
        "complete_oracle_calls",
        "scenario_evaluations",
        "trace",
        "LB",
        "UB",
        "objective",
        "incumbent",
        "runtime_seconds",
        "result_sha256",
    }
    if set(result) != required:
        raise ValueError("A0 result fields are incomplete or unexpected")
    bare = dict(result)
    sealed = bare.pop("result_sha256")
    if sealed != canonical_json_sha256(bare):
        raise ValueError("A0 result seal mismatch")
    if result["schema_version"] != 1 or result["method"] != "R3_V2_A0_STANDARD_CCG":
        raise ValueError("not an R3 v2 A0 result")
    if result["status"] != "certified" or result["diagnostic"] is not None:
        raise ValueError("A0 result is not certified")
    ordered = canonical_scenarios(data)
    identities = scenario_identities(data)
    if (
        result["data_sha256"] != data.data_sha256
        or result["scenario_sha256"] != data.scenario_sha256
        or result["canonical_scenarios"] != list(ordered)
        or result["scenario_identities"] != identities
        or result["initial_scenario"] != ordered[0]
        or result["maximum_iterations"] != len(ordered) + 1
    ):
        raise ValueError("A0 data, initial scenario, or safety rule mismatch")
    trace = result["trace"]
    if (
        not trace
        or result["iterations"] != len(trace)
        or result["exact_oracle_calls"] != len(trace)
        or result["complete_oracle_calls"] != len(trace)
        or result["scenario_evaluations"] != len(trace) * len(ordered)
    ):
        raise ValueError("A0 requires one complete full-Omega oracle per iteration")
    active = [ordered[0]]
    incumbent_ub: float | None = None
    incumbent_iteration: int | None = None
    final_lb: float | None = None
    source_decision: QFRFirstStage | None = None
    source_oracle: Mapping[str, Any] | None = None
    for number, row in enumerate(trace, 1):
        if row["iteration"] != number or row["active_scenarios"] != active:
            raise ValueError("A0 active-scenario sequence mismatch")
        expected_active_identities = [identities[value] for value in active]
        if row["active_scenario_identities"] != expected_active_identities:
            raise ValueError("A0 active scientific identity sequence mismatch")
        master = row["master"]
        if master["active_scenarios"] != active or master["active_scenario_identities"] != expected_active_identities:
            raise ValueError("restricted-master active set mismatch")
        restricted = subset_data(data, tuple(active))
        if master["restricted_data_sha256"] != restricted.data_sha256 or master["restricted_scenario_sha256"] != restricted.scenario_sha256:
            raise ValueError("restricted-master data identity mismatch")
        accepted_outcome(master["solver"])
        decision = QFRFirstStage.from_dict(row["first_stage"])
        validate_first_stage(data, decision)
        if decision.model_kind != result["model_kind"] or row["first_stage_sha256"] != decision.sha256 or master["first_stage_sha256"] != decision.sha256:
            raise ValueError("A0 first-stage identity mismatch")
        accounting = master["accounting"]
        if accounting["data_sha256"] != restricted.data_sha256 or accounting["scenario_sha256"] != restricted.scenario_sha256:
            raise ValueError("restricted-master loaded accounting identity mismatch")
        theta = float(master["theta"])
        require_close(float(master["objective"]), first_stage_cost(data, decision) + theta, "restricted-master objective")
        validate_oracle(data, decision, row["oracle"])
        final_lb = float(master["lower_bound"])
        require_close(float(row["LB"]), final_lb, "iteration LB")
        candidate = first_stage_cost(data, decision) + float(row["oracle"]["worst_loss"])
        require_close(float(row["candidate_UB"]), candidate, "candidate UB")
        if incumbent_ub is None or candidate < incumbent_ub:
            incumbent_ub = candidate
            incumbent_iteration = number
            source_decision = decision
            source_oracle = row["oracle"]
        assert incumbent_ub is not None
        require_close(float(row["UB"]), incumbent_ub, "formal incumbent UB")
        if row["incumbent_iteration"] != incumbent_iteration:
            raise ValueError("A0 lost incumbent ownership")
        signed_gap = incumbent_ub - final_lb
        gap_threshold = tolerance(incumbent_ub, final_lb)
        violation = max(0.0, float(row["oracle"]["worst_loss"]) - theta)
        violation_threshold = tolerance(float(row["oracle"]["worst_loss"]), theta)
        expected = {
            "signed_gap": signed_gap,
            "gap": max(0.0, signed_gap),
            "gap_tolerance": gap_threshold,
            "violation": violation,
            "violation_tolerance": violation_threshold,
        }
        for key, value in expected.items():
            require_close(float(row[key]), value, f"A0 trace {key}")
        gap_pass = -gap_threshold <= signed_gap <= gap_threshold
        violation_pass = violation <= violation_threshold
        convergence = gap_pass and violation_pass
        if row["gap_pass"] is not gap_pass or row["violation_pass"] is not violation_pass or row["convergence"] is not convergence:
            raise ValueError("A0 convergence decision mismatch")
        if convergence != (number == len(trace)):
            raise ValueError("A0 premature or missing final convergence")
        if not convergence:
            worst = row["oracle"]["worst_scenario"]
            identity = identities[worst]
            if (
                row["added_scenario"] != worst
                or row["added_scenario_identity"] != identity
                or worst in active
                or identity in {identities[value] for value in active}
                or violation <= violation_threshold
            ):
                raise ValueError("A0 did not make valid exact-scenario progress")
            active = sorted([*active, worst])
        elif row["added_scenario"] is not None or row["added_scenario_identity"] is not None:
            raise ValueError("A0 added a scenario after convergence")
    assert incumbent_ub is not None and incumbent_iteration is not None
    incumbent = result["incumbent"]
    if incumbent["iteration"] != incumbent_iteration or incumbent["first_stage_sha256"] != source_decision.sha256:
        raise ValueError("A0 final incumbent is not bound to its producing iteration")
    if incumbent["first_stage"] != source_decision.to_dict() or incumbent["oracle"] != source_oracle:
        raise ValueError("A0 incumbent evidence differs from its producing iteration")
    require_close(float(incumbent["objective"]), incumbent_ub, "incumbent objective")
    require_close(float(result["LB"]), float(final_lb), "final LB")
    require_close(float(result["UB"]), incumbent_ub, "final UB")
    require_close(float(result["objective"]), incumbent_ub, "A0 objective")
    runtime = float(result["runtime_seconds"])
    if not math.isfinite(runtime) or runtime < 0:
        raise ValueError("A0 runtime must be finite and nonnegative")
