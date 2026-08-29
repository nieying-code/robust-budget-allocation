"""Fail-closed R3 v2 EF/A0 certificate and replay validation."""

from __future__ import annotations

from copy import deepcopy
import json
import math
from pathlib import Path
import subprocess
from typing import Any, Mapping

from robust_budget_allocation.data.qfr_data import QFRData
from robust_budget_allocation.io.hashing import (
    canonical_json_sha256,
    sha256_bytes,
    sha256_file,
)
from .qfr_extensive_form import validate_extensive_form_result
from .qfr_protocol import PROTOCOL_SHA256, protocol_identity, require_close, tolerance
from .qfr_standard_ccg import validate_standard_ccg_result
from .qfr_state import QFRFirstStage, validate_first_stage


def verify_ef_a0_pair(
    data: QFRData,
    ef: Mapping[str, Any],
    a0: Mapping[str, Any],
) -> dict[str, Any]:
    validate_extensive_form_result(data, ef)
    validate_standard_ccg_result(data, a0)
    if ef["model_kind"] != a0["model_kind"]:
        raise ValueError("EF/A0 model kinds differ")
    require_close(float(ef["objective"]), float(a0["objective"]), "EF/A0 objective")
    final = a0["trace"][-1]
    if final["convergence"] is not True:
        raise ValueError("A0 final trace is not converged")
    if not (
        -float(final["gap_tolerance"])
        <= float(final["signed_gap"])
        <= float(final["gap_tolerance"])
    ):
        raise ValueError("A0 final global gap is outside the frozen tolerance")
    if float(final["violation"]) > float(final["violation_tolerance"]):
        raise ValueError("A0 final exact-oracle violation exceeds tolerance")
    ef_decision = QFRFirstStage.from_dict(ef["first_stage"])
    a0_decision = QFRFirstStage.from_dict(a0["incumbent"]["first_stage"])
    validate_first_stage(data, ef_decision)
    validate_first_stage(data, a0_decision)
    difference = abs(float(ef["objective"]) - float(a0["objective"]))
    maximum_recourse_violation = max(
        float(row["maximum_feasibility_violation"])
        for result in (ef["oracle"], a0["incumbent"]["oracle"])
        for row in result["results"]
    )
    certificate = {
        "status": "PASS",
        "model_kind": ef["model_kind"],
        "data_sha256": data.data_sha256,
        "scenario_sha256": data.scenario_sha256,
        "ef_result_sha256": ef["result_sha256"],
        "a0_result_sha256": a0["result_sha256"],
        "ef_objective": float(ef["objective"]),
        "a0_objective": float(a0["objective"]),
        "objective_difference": difference,
        "objective_tolerance": tolerance(float(ef["objective"]), float(a0["objective"])),
        "relative_objective_difference": difference
        / max(1.0, abs(float(ef["objective"])), abs(float(a0["objective"]))),
        "maximum_feasibility_violation": maximum_recourse_violation,
        "final_LB": float(a0["LB"]),
        "final_UB": float(a0["UB"]),
        "final_signed_gap": float(final["signed_gap"]),
        "final_gap_tolerance": float(final["gap_tolerance"]),
        "final_violation": float(final["violation"]),
        "final_violation_tolerance": float(final["violation_tolerance"]),
        "iterations": int(a0["iterations"]),
        "exact_oracle_calls": int(a0["exact_oracle_calls"]),
        "scenario_evaluations": int(a0["scenario_evaluations"]),
        "final_scenario_pool": list(a0["trace"][-1]["active_scenarios"]),
        "multiple_optima_policy": "OBJECTIVE_AND_INDEPENDENT_FEASIBILITY_NOT_VECTOR_EQUALITY",
    }
    certificate["certificate_sha256"] = canonical_json_sha256(certificate)
    return certificate


def validate_pair_certificate(
    data: QFRData,
    ef: Mapping[str, Any],
    a0: Mapping[str, Any],
    certificate: Mapping[str, Any],
) -> None:
    expected = verify_ef_a0_pair(data, ef, a0)
    if certificate != expected:
        raise ValueError("EF/A0 pair certificate does not replay exactly")


def seal_evidence(payload: Mapping[str, Any]) -> dict[str, Any]:
    result = deepcopy(dict(payload))
    if "evidence_sha256" in result:
        raise ValueError("unsealed evidence must not already contain evidence_sha256")
    result["evidence_sha256"] = canonical_json_sha256(result)
    return result


def _git_output(repo_root: Path, *arguments: str, text: bool = False) -> bytes | str:
    completed = subprocess.run(
        ["git", "-C", str(repo_root.resolve()), *arguments],
        check=True,
        capture_output=True,
        text=text,
    )
    return completed.stdout


def _anchored_file(repo_root: Path, commit_sha: str, relative_path: str) -> bytes:
    if not relative_path or relative_path.startswith(("/", "\\")) or ".." in Path(relative_path).parts:
        raise ValueError("R3 anchored source path is unsafe")
    try:
        return _git_output(repo_root, "show", f"{commit_sha}:{relative_path}")
    except subprocess.CalledProcessError as exc:
        raise ValueError(f"R3 anchored source path is missing: {relative_path}") from exc


def validate_r3_evidence(
    repo_root: Path,
    evidence: Mapping[str, Any],
) -> dict[str, Any]:
    required = {
        "schema_version",
        "phase",
        "scope",
        "protocol",
        "source",
        "fixture",
        "environment",
        "cases",
        "summary",
        "scientific_runs",
        "pilot_runs",
        "formal_experiments",
        "a1_new_implemented",
        "evidence_sha256",
    }
    if set(evidence) != required:
        raise ValueError("R3 evidence fields are incomplete or unexpected")
    bare = dict(evidence)
    seal = bare.pop("evidence_sha256")
    if seal != canonical_json_sha256(bare):
        raise ValueError("R3 evidence seal mismatch")
    if evidence["schema_version"] != 1 or evidence["phase"] != "R3":
        raise ValueError("not R3 evidence")
    if evidence["scope"] != "CORRECTNESS_FIXTURE_ONLY_NOT_FORMAL_SCIENTIFIC_PARAMETERS":
        raise ValueError("R3 fixture scope marker mismatch")
    if evidence["protocol"] != protocol_identity(repo_root) or evidence["protocol"]["sha256"] != PROTOCOL_SHA256:
        raise ValueError("R3 protocol identity mismatch")
    source = evidence["source"]
    if set(source) != {"git", "files"}:
        raise ValueError("R3 source identity fields mismatch")
    git = source["git"]
    if set(git) != {
        "commit_sha",
        "tree_sha",
        "tracked_dirty",
        "untracked_paths",
        "tracked_input_paths",
        "untracked_scientific_paths",
    }:
        raise ValueError("R3 Git identity fields mismatch")
    if git["tracked_dirty"] is not False or git["untracked_scientific_paths"] not in ([], ()): 
        raise ValueError("R3 execution source was not clean")
    commit_sha = git["commit_sha"]
    tree_sha = git["tree_sha"]
    if not isinstance(commit_sha, str) or not isinstance(tree_sha, str):
        raise ValueError("R3 Git commit/tree identity is invalid")
    try:
        anchored_tree = str(
            _git_output(repo_root, "rev-parse", f"{commit_sha}^{{tree}}", text=True)
        ).strip()
    except subprocess.CalledProcessError as exc:
        raise ValueError("R3 execution commit is unavailable") from exc
    if anchored_tree != tree_sha:
        raise ValueError("R3 execution commit/tree binding mismatch")
    for row in source["files"]:
        if set(row) != {"path", "sha256"}:
            raise ValueError("R3 source file inventory fields mismatch")
        if sha256_bytes(_anchored_file(repo_root, commit_sha, row["path"])) != row["sha256"]:
            raise ValueError("R3 source file hash mismatch")
    fixture = evidence["fixture"]
    if set(fixture) != {"path", "sha256", "payload", "config_sha256"}:
        raise ValueError("R3 fixture fields mismatch")
    anchored_fixture = _anchored_file(repo_root, commit_sha, fixture["path"])
    if sha256_bytes(anchored_fixture) != fixture["sha256"]:
        raise ValueError("R3 fixture file hash mismatch")
    if fixture["config_sha256"] != canonical_json_sha256(fixture["payload"]):
        raise ValueError("R3 fixture config identity mismatch")
    try:
        anchored_payload = json.loads(anchored_fixture.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("R3 anchored fixture is not canonical UTF-8 JSON") from exc
    if fixture["payload"] != anchored_payload:
        raise ValueError("R3 embedded fixture payload differs from anchored execution input")
    fixture_cases = {row["case_id"]: row for row in fixture["payload"]["cases"]}
    if len(evidence["cases"]) != len(fixture_cases) * 3:
        raise ValueError("R3 evidence does not cover every fixture and M0/M1/M2")
    seen: set[tuple[str, str]] = set()
    max_difference = 0.0
    max_violation = 0.0
    for row in evidence["cases"]:
        required_case = {
            "case_id",
            "model_kind",
            "data_sha256",
            "scenario_sha256",
            "ef",
            "a0",
            "certificate",
        }
        if set(row) != required_case:
            raise ValueError("R3 case evidence fields mismatch")
        key = (row["case_id"], row["model_kind"])
        if key in seen or row["case_id"] not in fixture_cases or row["model_kind"] not in {"M0", "M1", "M2"}:
            raise ValueError("R3 case coverage is duplicate or unknown")
        seen.add(key)
        data = QFRData.from_dict(fixture_cases[row["case_id"]]["data"])
        if row["data_sha256"] != data.data_sha256 or row["scenario_sha256"] != data.scenario_sha256:
            raise ValueError("R3 case Q-F-R identity mismatch")
        validate_pair_certificate(data, row["ef"], row["a0"], row["certificate"])
        max_difference = max(max_difference, float(row["certificate"]["objective_difference"]))
        max_violation = max(max_violation, float(row["certificate"]["maximum_feasibility_violation"]))
    expected_pairs = {(case, kind) for case in fixture_cases for kind in ("M0", "M1", "M2")}
    if seen != expected_pairs:
        raise ValueError("R3 case matrix is incomplete")
    summary = evidence["summary"]
    if summary["status"] != "PASS" or summary["case_count"] != len(seen):
        raise ValueError("R3 evidence summary status/count mismatch")
    require_close(float(summary["maximum_objective_difference"]), max_difference, "summary maximum objective difference")
    require_close(float(summary["maximum_feasibility_violation"]), max_violation, "summary maximum feasibility violation")
    if evidence["scientific_runs"] != 0 or evidence["pilot_runs"] != 0 or evidence["formal_experiments"] != 0 or evidence["a1_new_implemented"] is not False:
        raise ValueError("R3 scope-exclusion audit mismatch")
    return {
        "status": "PASS",
        "evidence_sha256": seal,
        "case_count": len(seen),
        "maximum_objective_difference": max_difference,
        "maximum_feasibility_violation": max_violation,
    }
