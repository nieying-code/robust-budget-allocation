"""Replay R4 A1 without trusting stored phase hits, accounting, bounds, or counters."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Mapping

from robust_budget_allocation.data.qfr_data import QFRData
from robust_budget_allocation.io.hashing import canonical_json_sha256, sha256_bytes, sha256_file
from .qfr_a1_candidates import candidate_plan
from .qfr_a1_memory import QFRScenarioMemory
from .qfr_accounting import validate_accounting_payload
from .qfr_exact_oracle import validate_oracle, validate_recourse_result
from .qfr_improved_ccg import R4_PROTOCOL_PATH, R4_PROTOCOL_SHA256, a1_settings
from .qfr_protocol import (
    accepted_outcome,
    canonical_scenarios,
    require_close,
    scenario_identities,
    solver_configuration_identity,
    subset_data,
    tolerance,
)
from .qfr_state import QFRFirstStage, first_stage_cost, validate_first_stage
from .qfr_verification import _anchored_file, _anchored_tree


def _replay_evaluations(
    data: QFRData,
    decision: QFRFirstStage,
    theta: float,
    phase: Mapping[str, Any],
    planned: list[str],
) -> str | None:
    if phase["status"] != "complete" or len(phase["evaluations"]) > len(planned):
        raise ValueError("A1 partial phase is incomplete or exceeded its limit")
    selected = None
    for index, evaluation in enumerate(phase["evaluations"]):
        if evaluation["scenario_id"] != planned[index]:
            raise ValueError("A1 partial exact evaluation order mismatch")
        validate_recourse_result(data, decision, evaluation)
        loss = float(evaluation["loss"])
        if max(0.0, loss - theta) > tolerance(loss, theta):
            selected = str(evaluation["scenario_id"])
            if index != len(phase["evaluations"]) - 1:
                raise ValueError("A1 partial search continued after its first exact hit")
    if selected is None and len(phase["evaluations"]) != len(planned):
        raise ValueError("A1 partial search stopped early without a hit")
    if phase["selected"] != selected or phase["hit"] is not (selected is not None):
        raise ValueError("A1 partial phase hit/selection mismatch")
    return selected


def validate_improved_ccg_result(data: QFRData, result: Mapping[str, Any]) -> None:
    required = {
        "schema_version",
        "method",
        "model_kind",
        "status",
        "diagnostic",
        "data_sha256",
        "scenario_sha256",
        "settings",
        "canonical_scenarios",
        "scenario_identities",
        "initial_scenario",
        "maximum_iterations",
        "iterations",
        "memory_opportunities",
        "memory_hits",
        "candidate_hits",
        "full_exact_certification_calls",
        "complete_full_exact_certification_calls",
        "scenario_evaluations",
        "additions",
        "trace",
        "LB",
        "UB",
        "objective",
        "incumbent",
        "runtime_seconds",
        "result_sha256",
    }
    if set(result) != required:
        raise ValueError("A1 result fields are incomplete or unexpected")
    bare = dict(result)
    seal = bare.pop("result_sha256")
    if seal != canonical_json_sha256(bare):
        raise ValueError("A1 result seal mismatch")
    if (
        result["schema_version"] != 1
        or result["method"] != "R4_V2_A1_IMPROVED_CCG"
        or result["status"] != "certified"
        or result["diagnostic"] is not None
    ):
        raise ValueError("A1 result is not certified R4 v2 evidence")
    data.validate()
    ordered = canonical_scenarios(data)
    identities = scenario_identities(data)
    memory_enabled = result["settings"]["memory_phase_enabled"]
    if (
        result["data_sha256"] != data.data_sha256
        or result["scenario_sha256"] != data.scenario_sha256
        or result["settings"] != a1_settings(memory_phase_enabled=memory_enabled)
        or result["canonical_scenarios"] != list(ordered)
        or result["scenario_identities"] != identities
        or result["initial_scenario"] != ordered[0]
        or result["maximum_iterations"] != len(ordered) + 1
    ):
        raise ValueError("A1 input, setting, or deterministic safety identity mismatch")
    trace = result["trace"]
    if not trace or result["iterations"] != len(trace):
        raise ValueError("A1 trace length mismatch")
    active = [ordered[0]]
    additions = [
        {
            "iteration": 0,
            "scenario_id": ordered[0],
            "scenario_identity": identities[ordered[0]],
            "source": "INITIAL",
        }
    ]
    memory = QFRScenarioMemory(data.data_sha256, identities)
    incumbent_ub = None
    incumbent_iteration = None
    incumbent_decision = None
    incumbent_oracle = None
    final_lb = None
    counters = {
        "memory_opportunities": 0,
        "memory_hits": 0,
        "candidate_hits": 0,
        "full_exact_certification_calls": 0,
        "complete_full_exact_certification_calls": 0,
        "scenario_evaluations": 0,
    }
    for iteration, row in enumerate(trace, 1):
        if row["iteration"] != iteration or row["active_scenarios"] != active:
            raise ValueError("A1 active master sequence mismatch")
        expected_identities = [identities[value] for value in active]
        if row["active_scenario_identities"] != expected_identities:
            raise ValueError("A1 active scientific identities mismatch")
        master = row["master"]
        restricted = subset_data(data, tuple(active))
        if (
            master["active_scenarios"] != active
            or master["active_scenario_identities"] != expected_identities
            or master["restricted_data_sha256"] != restricted.data_sha256
            or master["restricted_scenario_sha256"] != restricted.scenario_sha256
        ):
            raise ValueError("A1 restricted-master identity mismatch")
        accepted_outcome(master["solver"])
        decision = QFRFirstStage.from_dict(row["first_stage"])
        validate_first_stage(data, decision)
        if (
            decision.model_kind != result["model_kind"]
            or decision.sha256 != row["first_stage_sha256"]
            or decision.sha256 != master["first_stage_sha256"]
        ):
            raise ValueError("A1 first-stage identity mismatch")
        theta = float(master["theta"])
        validate_accounting_payload(
            data,
            restricted,
            decision,
            master["accounting"],
            expected_objective=float(master["objective"]),
            expected_theta=theta,
        )
        require_close(float(master["solver"]["objective"]), float(master["objective"]), "A1 solver/master objective")
        require_close(float(master["solver"]["lower_bound"]), float(master["lower_bound"]), "A1 solver/master LB")
        final_lb = float(master["lower_bound"])
        require_close(float(row["LB"]), final_lb, "A1 trace LB")

        selected = None
        source = None
        inspected: list[str] = []
        if memory_enabled:
            phase = row["memory"]
            if phase is None or phase["before"] != memory.snapshot():
                raise ValueError("A1 Memory state mismatch")
            removed = memory.prune(iteration)
            plan = memory.inspection_plan(active)
            if phase["removed"] != removed or phase["after_prune"] != memory.snapshot():
                raise ValueError("A1 Memory pruning mismatch")
            for key in ("skipped_active", "ranking", "planned"):
                if phase[key] != plan[key]:
                    raise ValueError("A1 Memory plan mismatch")
            if plan["planned"]:
                counters["memory_opportunities"] += 1
            selected = _replay_evaluations(data, decision, theta, phase, plan["planned"])
            counters["scenario_evaluations"] += len(phase["evaluations"])
            if phase["update"] != memory.update(phase["evaluations"], iteration, "MEMORY") or phase["after"] != memory.snapshot():
                raise ValueError("A1 Memory update mismatch")
            inspected = [entry["scenario_id"] for entry in phase["evaluations"]]
            if selected is not None:
                source = "MEMORY"
                counters["memory_hits"] += 1
        elif row["memory"] is not None:
            raise ValueError("final A1 unexpectedly executed an independent Memory phase")

        if selected is None:
            phase = row["candidate"]
            plan = candidate_plan(data, active, inspected)
            if phase is None or any(phase[key] != value for key, value in plan.items()):
                raise ValueError("A1 Candidate plan mismatch")
            selected = _replay_evaluations(data, decision, theta, phase, plan["planned"])
            counters["scenario_evaluations"] += len(phase["evaluations"])
            if memory_enabled:
                if phase["memory_update"] != memory.update(phase["evaluations"], iteration, "CANDIDATE") or phase["memory_after"] != memory.snapshot():
                    raise ValueError("A1 Candidate-to-Memory update mismatch")
            if selected is not None:
                source = "CANDIDATE"
                counters["candidate_hits"] += 1
        elif row["candidate"] is not None:
            raise ValueError("A1 Candidate ran after a Memory hit")

        converged = False
        certification_performed = False
        if selected is None:
            oracle = row["full_exact_certification"]
            certification_performed = True
            if row["full_exact_certification_iteration"] != iteration:
                raise ValueError("A1 Full Exact Certification iteration binding mismatch")
            validate_oracle(data, decision, oracle)
            if oracle["first_stage_sha256"] != decision.sha256:
                raise ValueError("A1 certification is detached from its master decision")
            require_close(
                float(oracle["theta"]),
                theta,
                "A1 certification/master theta",
            )
            counters["full_exact_certification_calls"] += 1
            counters["complete_full_exact_certification_calls"] += 1
            counters["scenario_evaluations"] += int(oracle["evaluations"])
            if memory_enabled:
                if row["full_exact_memory_update"] != memory.update(oracle["results"], iteration, "EXACT") or row["memory_after_full_exact"] != memory.snapshot():
                    raise ValueError("A1 full-exact Memory update mismatch")
            candidate_ub = first_stage_cost(data, decision) + float(oracle["worst_loss"])
            require_close(float(row["candidate_UB"]), candidate_ub, "A1 complete candidate UB")
            if incumbent_ub is None or candidate_ub < incumbent_ub:
                incumbent_ub = candidate_ub
                incumbent_iteration = iteration
                incumbent_decision = decision
                incumbent_oracle = oracle
            signed_gap = incumbent_ub - final_lb
            threshold = tolerance(incumbent_ub, final_lb)
            violation = float(oracle["violation"])
            violation_threshold = tolerance(float(oracle["worst_loss"]), theta)
            converged = -threshold <= signed_gap <= threshold and violation <= violation_threshold
            for key, value in {
                "UB": incumbent_ub,
                "signed_gap": signed_gap,
                "gap": max(0.0, signed_gap),
                "gap_tolerance": threshold,
                "violation": violation,
                "violation_tolerance": violation_threshold,
            }.items():
                require_close(float(row[key]), value, f"A1 trace {key}")
            if row["incumbent_iteration"] != incumbent_iteration:
                raise ValueError("A1 incumbent ownership mismatch")
            if not converged:
                selected, source = str(oracle["worst_scenario"]), "EXACT"
        else:
            if (
                row["full_exact_certification"] is not None
                or row["full_exact_certification_iteration"] is not None
                or row["candidate_UB"] is not None
                or row["UB"] is not None
                or row["incumbent_iteration"] is not None
                or row["signed_gap"] is not None
                or row["gap"] is not None
                or row["gap_tolerance"] is not None
                or row["convergence"] is not None
            ):
                raise ValueError("A1 heuristic hit generated a formal UB/certification")
            phase = row["memory"] if source == "MEMORY" else row["candidate"]
            loss = next(
                float(entry["loss"])
                for entry in phase["evaluations"]
                if entry["scenario_id"] == selected
            )
            require_close(float(row["violation"]), max(0.0, loss - theta), "A1 partial violation")
            require_close(float(row["violation_tolerance"]), tolerance(loss, theta), "A1 partial violation tolerance")
            if row["UB"] is not None and incumbent_ub is None:
                raise ValueError("A1 fabricated UB before full certification")
        if certification_performed:
            if row["convergence"] is not converged:
                raise ValueError("A1 Full Exact convergence decision mismatch")
        elif row["convergence"] is not None:
            raise ValueError("A1 non-certification iteration has a convergence claim")
        if converged != (iteration == len(trace)):
            raise ValueError("A1 convergence was not owned by final full exact certification")
        if not converged:
            if (
                selected in active
                or selected not in ordered
                or row["added_scenario"] != selected
                or row["added_scenario_identity"] != identities[selected]
                or row["scenario_source"] != source
            ):
                raise ValueError("A1 scenario addition is invalid")
            additions.append(
                {
                    "iteration": iteration,
                    "scenario_id": selected,
                    "scenario_identity": identities[selected],
                    "source": source,
                }
            )
            active = sorted([*active, selected])
        elif any(row[key] is not None for key in ("added_scenario", "added_scenario_identity", "scenario_source")):
            raise ValueError("A1 added a scenario after certification")
    if result["additions"] != additions:
        raise ValueError("A1 addition history mismatch")
    for key, value in counters.items():
        if result[key] != value:
            raise ValueError(f"A1 counter mismatch: {key}")
    if incumbent_ub is None or incumbent_decision is None or incumbent_oracle is None:
        raise ValueError("A1 has no complete exact incumbent")
    incumbent = result["incumbent"]
    if (
        incumbent["iteration"] != incumbent_iteration
        or incumbent["first_stage"] != incumbent_decision.to_dict()
        or incumbent["first_stage_sha256"] != incumbent_decision.sha256
        or incumbent["oracle"] != incumbent_oracle
    ):
        raise ValueError("A1 final incumbent is detached from producing certification")
    require_close(float(incumbent["objective"]), incumbent_ub, "A1 incumbent objective")
    require_close(float(result["LB"]), float(final_lb), "A1 final LB")
    require_close(float(result["UB"]), incumbent_ub, "A1 final UB")
    require_close(float(result["objective"]), incumbent_ub, "A1 objective")
    runtime = float(result["runtime_seconds"])
    if not math.isfinite(runtime) or runtime < 0:
        raise ValueError("A1 runtime must be finite and nonnegative")


def verify_ef_a0_a1(
    data: QFRData,
    ef: Mapping[str, Any],
    a0: Mapping[str, Any],
    a1: Mapping[str, Any],
) -> dict[str, Any]:
    from .qfr_verification import verify_ef_a0_pair

    pair = verify_ef_a0_pair(data, ef, a0)
    validate_improved_ccg_result(data, a1)
    model_kind = str(ef["model_kind"])
    if a0["model_kind"] != model_kind or a1["model_kind"] != model_kind:
        raise ValueError("EF/A0/A1 model-kind identity chain mismatch")
    values = [float(ef["objective"]), float(a0["objective"]), float(a1["objective"])]
    require_close(values[0], values[2], "EF/A1 objective")
    require_close(values[1], values[2], "A0/A1 objective")
    maximum_violation = max(
        pair["maximum_feasibility_violation"],
        max(
            float(row["maximum_feasibility_violation"])
            for row in a1["incumbent"]["oracle"]["results"]
        ),
    )
    result = {
        "status": "PASS",
        "model_kind": model_kind,
        "data_sha256": data.data_sha256,
        "scenario_sha256": data.scenario_sha256,
        "ef_result_sha256": ef["result_sha256"],
        "a0_result_sha256": a0["result_sha256"],
        "a1_result_sha256": a1["result_sha256"],
        "objectives": {"EF": values[0], "A0": values[1], "A1": values[2]},
        "maximum_objective_difference": max(values) - min(values),
        "maximum_feasibility_violation": maximum_violation,
        "a0_iterations": int(a0["iterations"]),
        "a0_full_exact_calls": int(a0["exact_oracle_calls"]),
        "a0_scenario_evaluations": int(a0["scenario_evaluations"]),
        "a1_iterations": int(a1["iterations"]),
        "a1_memory_opportunities": int(a1["memory_opportunities"]),
        "a1_memory_hits": int(a1["memory_hits"]),
        "a1_candidate_hits": int(a1["candidate_hits"]),
        "a1_full_exact_certification_calls": int(a1["full_exact_certification_calls"]),
        "a1_scenario_evaluations": int(a1["scenario_evaluations"]),
        "multiple_optima_policy": "OBJECTIVE_AND_INDEPENDENT_FEASIBILITY_NOT_VECTOR_EQUALITY",
    }
    result["certificate_sha256"] = canonical_json_sha256(result)
    return result


def validate_three_certificate(
    data: QFRData,
    ef: Mapping[str, Any],
    a0: Mapping[str, Any],
    a1: Mapping[str, Any],
    certificate: Mapping[str, Any],
    *,
    expected_model_kind: str,
) -> None:
    if not (
        expected_model_kind
        == ef["model_kind"]
        == a0["model_kind"]
        == a1["model_kind"]
        == certificate.get("model_kind")
    ):
        raise ValueError("outer/EF/A0/A1/certificate model-kind chain mismatch")
    expected = verify_ef_a0_a1(data, ef, a0, a1)
    if certificate != expected:
        raise ValueError("EF/A0/A1 certificate result binding mismatch")


def validate_r4_evidence(repo_root: Path, evidence: Mapping[str, Any]) -> dict[str, Any]:
    """Replay only the identities and numerical facts required for R4 correctness."""

    required = {
        "schema_version",
        "phase",
        "scope",
        "r4_protocol",
        "source",
        "fixture",
        "environment",
        "solver_configuration",
        "memory_phase_enabled",
        "cases",
        "summary",
        "scientific_runs",
        "pilot_runs",
        "formal_experiments",
        "evidence_sha256",
    }
    if set(evidence) != required:
        raise ValueError("R4 evidence fields are incomplete or unexpected")
    bare = dict(evidence)
    seal = bare.pop("evidence_sha256")
    if seal != canonical_json_sha256(bare):
        raise ValueError("R4 evidence seal mismatch")
    if (
        evidence["schema_version"] != 1
        or evidence["phase"] != "R4"
        or evidence["scope"]
        != "CORRECTNESS_ONLY_NOT_PERFORMANCE_OR_SCIENTIFIC_EXPERIMENT"
    ):
        raise ValueError("not R4 correctness evidence")
    protocol = evidence["r4_protocol"]
    if protocol != {"path": R4_PROTOCOL_PATH, "sha256": R4_PROTOCOL_SHA256}:
        raise ValueError("R4 protocol identity mismatch")
    if sha256_file(repo_root / R4_PROTOCOL_PATH) != R4_PROTOCOL_SHA256:
        raise ValueError("working R4 protocol hash mismatch")
    source = evidence["source"]
    if set(source) != {"git", "files"}:
        raise ValueError("R4 source fields mismatch")
    git = source["git"]
    if (
        git["tracked_dirty"] is not False
        or list(git["untracked_paths"])
        or list(git["untracked_scientific_paths"])
    ):
        raise ValueError("R4 execution source was not clean")
    commit = str(git["commit_sha"])
    if _anchored_tree(repo_root, commit) != git["tree_sha"]:
        raise ValueError("R4 execution commit/tree mismatch")
    files = source["files"]
    paths = [row["path"] for row in files]
    if (
        len(paths) != len(set(paths))
        or list(git["tracked_input_paths"]) != paths
        or not {
            "src/robust_budget_allocation/data/qfr_data.py",
            "src/robust_budget_allocation/models/qfr_common.py",
            "src/robust_budget_allocation/models/qfr_support.py",
            "src/robust_budget_allocation/algorithms/qfr_standard_ccg.py",
            "src/robust_budget_allocation/algorithms/qfr_improved_ccg.py",
            "src/robust_budget_allocation/algorithms/qfr_a1_verification.py",
        }.issubset(paths)
    ):
        raise ValueError("R4 source inventory is incomplete or duplicated")
    for row in files:
        if set(row) != {"path", "sha256"} or sha256_bytes(
            _anchored_file(repo_root, commit, row["path"])
        ) != row["sha256"]:
            raise ValueError("R4 anchored source hash mismatch")
    if sha256_bytes(_anchored_file(repo_root, commit, R4_PROTOCOL_PATH)) != R4_PROTOCOL_SHA256:
        raise ValueError("R4 execution source used a different protocol")
    fixture = evidence["fixture"]
    anchored_fixture = _anchored_file(repo_root, commit, fixture["path"])
    if (
        set(fixture) != {"path", "sha256", "payload", "config_sha256"}
        or sha256_bytes(anchored_fixture) != fixture["sha256"]
        or canonical_json_sha256(fixture["payload"]) != fixture["config_sha256"]
        or json.loads(anchored_fixture.decode("utf-8")) != fixture["payload"]
    ):
        raise ValueError("R4 fixture identity mismatch")
    environment = evidence["environment"]
    locked = {
        "python": "3.12.10",
        "python_implementation": "CPython",
        "pyomo": "6.10.1",
        "gurobipy": "13.0.2",
        "gurobi_optimizer": "13.0.2",
        "solver_interface": "gurobi_direct",
        "threads": 1,
        "solver_available": True,
        "license_available": True,
        "status": "PASS",
    }
    if any(environment.get(key) != value for key, value in locked.items()):
        raise ValueError("R4 locked licensed environment mismatch")
    if evidence["solver_configuration"] != solver_configuration_identity():
        raise ValueError("R4 frozen solver policy mismatch")
    fixture_cases = {row["case_id"]: row for row in fixture["payload"]["cases"]}
    expected_pairs = {
        (case_id, kind)
        for case_id in fixture_cases
        for kind in ("M0", "M1", "M2")
    }
    seen = set()
    certificates = []
    for row in evidence["cases"]:
        if set(row) != {
            "case_id",
            "model_kind",
            "data_sha256",
            "scenario_sha256",
            "ef",
            "a0",
            "a1",
            "certificate",
        }:
            raise ValueError("R4 case fields mismatch")
        key = (row["case_id"], row["model_kind"])
        if key in seen or key not in expected_pairs:
            raise ValueError("R4 case coverage is duplicate or unknown")
        seen.add(key)
        data = QFRData.from_dict(fixture_cases[row["case_id"]]["data"])
        if (
            row["data_sha256"] != data.data_sha256
            or row["scenario_sha256"] != data.scenario_sha256
            or row["a1"]["settings"]["memory_phase_enabled"]
            is not evidence["memory_phase_enabled"]
        ):
            raise ValueError("R4 case identity or structure mismatch")
        validate_three_certificate(
            data,
            row["ef"],
            row["a0"],
            row["a1"],
            row["certificate"],
            expected_model_kind=row["model_kind"],
        )
        expected = verify_ef_a0_a1(data, row["ef"], row["a0"], row["a1"])
        certificates.append(expected)
    if seen != expected_pairs:
        raise ValueError("R4 M0/M1/M2 matrix is incomplete")
    summary = evidence["summary"]
    expected_summary = {
        "status": "PASS",
        "case_count": len(seen),
        "maximum_objective_difference": max(
            row["maximum_objective_difference"] for row in certificates
        ),
        "maximum_feasibility_violation": max(
            row["maximum_feasibility_violation"] for row in certificates
        ),
        "a0_iterations": sum(row["a0_iterations"] for row in certificates),
        "a0_full_exact_calls": sum(row["a0_full_exact_calls"] for row in certificates),
        "a0_scenario_evaluations": sum(
            row["a0_scenario_evaluations"] for row in certificates
        ),
        "a1_iterations": sum(row["a1_iterations"] for row in certificates),
        "memory_opportunities": sum(
            row["a1_memory_opportunities"] for row in certificates
        ),
        "memory_hits": sum(row["a1_memory_hits"] for row in certificates),
        "candidate_hits": sum(row["a1_candidate_hits"] for row in certificates),
        "a1_full_exact_certification_calls": sum(
            row["a1_full_exact_certification_calls"] for row in certificates
        ),
        "a1_scenario_evaluations": sum(
            row["a1_scenario_evaluations"] for row in certificates
        ),
    }
    opportunities, hits = expected_summary["memory_opportunities"], expected_summary["memory_hits"]
    expected_summary["memory_decision"] = (
        "REMOVE_INDEPENDENT_MEMORY_PHASE"
        if opportunities > 0 and hits == 0
        else "RETAIN_MEMORY_PHASE"
        if hits > 0
        else "MEMORY_VALUE_NOT_IDENTIFIED_NONBLOCKING"
    )
    if summary != expected_summary:
        raise ValueError("R4 summary does not recompute")
    if (
        evidence["scientific_runs"] != 0
        or evidence["pilot_runs"] != 0
        or evidence["formal_experiments"] != 0
    ):
        raise ValueError("R4 scope exclusion mismatch")
    return {
        "status": "PASS",
        "evidence_sha256": seal,
        "case_count": len(seen),
        "memory_decision": expected_summary["memory_decision"],
    }
