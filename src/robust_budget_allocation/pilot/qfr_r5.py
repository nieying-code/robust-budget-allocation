"""R5 Q-F-R Pilot execution, diagnostics, and minimal replay."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Mapping

from robust_budget_allocation.algorithms.qfr_a1_verification import (
    _anchored_file,
    _anchored_tree,
    validate_three_certificate,
    verify_ef_a0_a1,
)
from robust_budget_allocation.algorithms.qfr_extensive_form import solve_qfr_extensive_form
from robust_budget_allocation.algorithms.qfr_improved_ccg import solve_qfr_improved_ccg
from robust_budget_allocation.algorithms.qfr_protocol import solver_configuration_identity, tolerance
from robust_budget_allocation.algorithms.qfr_standard_ccg import solve_qfr_standard_ccg
from robust_budget_allocation.algorithms.qfr_verification import seal_evidence
from robust_budget_allocation.data.qfr_revision import load_pilot_baseline
from robust_budget_allocation.io.hashing import canonical_json_sha256, sha256_bytes, sha256_file
from robust_budget_allocation.reproducibility.git_state import validate_source_state
from robust_budget_allocation.runtime.environment import ensure_preflight_once

from .qfr_wfp import audit_wfp_workbook


PROTOCOL_PATH = "docs/R5_PILOT_PROTOCOL_v2.md"
PROTOCOL_SHA256 = "5c20518a6dcb586838bf0a4b4980154059f82b7c1732df324d5ae3df43ae617b"
EXECUTION_CONFIG_PATH = "configs/r5_pilot_execution_v2.json"
SOURCE_PATHS = (
    PROTOCOL_PATH,
    EXECUTION_CONFIG_PATH,
    "configs/qfr_pilot_baseline_v2_1.json",
    "src/robust_budget_allocation/data/qfr_data.py",
    "src/robust_budget_allocation/data/qfr_revision.py",
    "src/robust_budget_allocation/models/qfr_common.py",
    "src/robust_budget_allocation/models/qfr_m0.py",
    "src/robust_budget_allocation/models/qfr_m1.py",
    "src/robust_budget_allocation/models/qfr_m2.py",
    "src/robust_budget_allocation/models/qfr_support.py",
    "src/robust_budget_allocation/algorithms/qfr_protocol.py",
    "src/robust_budget_allocation/algorithms/qfr_state.py",
    "src/robust_budget_allocation/algorithms/qfr_builders.py",
    "src/robust_budget_allocation/algorithms/qfr_accounting.py",
    "src/robust_budget_allocation/algorithms/qfr_exact_oracle.py",
    "src/robust_budget_allocation/algorithms/qfr_extensive_form.py",
    "src/robust_budget_allocation/algorithms/qfr_standard_ccg.py",
    "src/robust_budget_allocation/algorithms/qfr_a1_memory.py",
    "src/robust_budget_allocation/algorithms/qfr_a1_candidates.py",
    "src/robust_budget_allocation/algorithms/qfr_improved_ccg.py",
    "src/robust_budget_allocation/algorithms/qfr_a1_verification.py",
    "src/robust_budget_allocation/pilot/qfr_wfp.py",
    "src/robust_budget_allocation/pilot/qfr_r5.py",
    "scripts/r5_qfr_pilot.py",
)


def load_execution_config(path: Path) -> dict[str, Any]:
    payload = json.loads(path.resolve().read_text(encoding="utf-8"))
    required = {
        "schema_version",
        "scope",
        "protocol_path",
        "baseline_path",
        "wfp_workbook",
        "models",
        "algorithms",
        "budget_ratios",
        "memory_phase_enabled",
    }
    if set(payload) != required:
        raise ValueError("R5 execution config fields mismatch")
    if (
        payload["schema_version"] != 1
        or payload["scope"] != "R5_PILOT_MECHANISM_DIAGNOSIS_NOT_FORMAL_EXPERIMENT"
        or payload["protocol_path"] != PROTOCOL_PATH
        or payload["models"] != ["M0", "M1", "M2"]
        or payload["algorithms"] != ["EF", "A0", "A1"]
        or payload["budget_ratios"] != [0.9, 1.0, 1.1]
        or payload["memory_phase_enabled"] is not True
    ):
        raise ValueError("R5 execution config is not the frozen Pilot matrix")
    return payload


def _active_level(first_stage: Mapping[str, Any], item: str) -> int | None:
    selected = [int(level) for level, value in first_stage["z"][item].items() if value == 1]
    return selected[0] if len(selected) == 1 else None


def _diagnostic_case(data: Any, ef: Mapping[str, Any], a0: Mapping[str, Any], a1: Mapping[str, Any], certificate: Mapping[str, Any]) -> dict[str, Any]:
    first = ef["first_stage"]
    accounting = ef["accounting"]
    oracle = ef["oracle"]
    levels = [int(level) for level in first["reliability_levels"]]
    f_total = {
        item: sum(float(first["f"][item][str(level)]) for level in levels)
        for item in data.items
    }
    selected = {item: _active_level(first, item) for item in data.items}
    scenarios = {
        row["scenario_id"]: {
            "exercise": dict(row["exercise"]),
            "shortage": dict(row["shortage"]),
            "exercise_cost": float(row["exercise_cost"]),
            "shortage_loss": float(row["shortage_loss"]),
            "recourse_loss": float(row["loss"]),
            "unused_cash": float(row["unused_cash"]),
            "budget_usage": float(data.budget - row["unused_cash"]),
            "maximum_feasibility_violation": float(row["maximum_feasibility_violation"]),
        }
        for row in oracle["results"]
    }
    worst = str(oracle["worst_scenario"])
    return {
        "model_kind": ef["model_kind"],
        "budget": float(data.budget),
        "objective": float(ef["objective"]),
        "objectives": dict(certificate["objectives"]),
        "maximum_objective_difference": float(certificate["maximum_objective_difference"]),
        "maximum_feasibility_violation": float(certificate["maximum_feasibility_violation"]),
        "q": dict(first["q"]),
        "f_by_level": {item: dict(first["f"][item]) for item in data.items},
        "f_total": f_total,
        "z": {item: dict(first["z"][item]) for item in data.items},
        "selected_reliability_level": selected,
        "q_fraction_of_nominal": {
            item: float(first["q"][item]) / float(data.demand["omega_2"][item])
            for item in data.items
        },
        "f_fraction_of_nominal": {
            item: f_total[item] / float(data.demand["omega_2"][item])
            for item in data.items
        },
        "first_stage_cost": {
            "C_Q": float(accounting["C_Q"]),
            "C_F": float(accounting["C_F"]),
            "C_R": float(accounting["C_R"]),
            "C_pre": float(accounting["C_pre"]),
        },
        "worst_scenario": worst,
        "worst_emergency_cost": scenarios[worst]["exercise_cost"],
        "worst_shortage_cost": scenarios[worst]["shortage_loss"],
        "worst_recourse_loss": scenarios[worst]["recourse_loss"],
        "worst_budget_usage": scenarios[worst]["budget_usage"],
        "scenarios": scenarios,
        "runtime_seconds": {
            "EF": float(ef["runtime_seconds"]),
            "A0": float(a0["runtime_seconds"]),
            "A1": float(a1["runtime_seconds"]),
        },
        "a0": {
            "iterations": int(a0["iterations"]),
            "full_exact_calls": int(a0["exact_oracle_calls"]),
            "scenario_evaluations": int(a0["scenario_evaluations"]),
        },
        "a1": {
            "iterations": int(a1["iterations"]),
            "memory_opportunities": int(a1["memory_opportunities"]),
            "memory_hits": int(a1["memory_hits"]),
            "candidate_hits": int(a1["candidate_hits"]),
            "full_exact_certification_calls": int(a1["full_exact_certification_calls"]),
            "scenario_evaluations": int(a1["scenario_evaluations"]),
        },
        "method_first_stages": {
            "EF": ef["first_stage"],
            "A0": a0["incumbent"]["first_stage"],
            "A1": a1["incumbent"]["first_stage"],
        },
    }


def _summary(cases: list[Mapping[str, Any]]) -> dict[str, Any]:
    diagnostics = [row["diagnostic"] for row in cases]
    return {
        "status": "PASS",
        "case_count": len(cases),
        "maximum_objective_difference": max(row["maximum_objective_difference"] for row in diagnostics),
        "maximum_feasibility_violation": max(row["maximum_feasibility_violation"] for row in diagnostics),
        "f_active_cases": [row["case_id"] for row in cases if any(value > tolerance(value, 0.0) for value in row["diagnostic"]["f_total"].values())],
        "r_upgrade_cases": [row["case_id"] for row in cases if any(level is not None and level > 0 and row["diagnostic"]["f_total"][item] > tolerance(row["diagnostic"]["f_total"][item], 0.0) for item, level in row["diagnostic"]["selected_reliability_level"].items())],
        "a0_iterations": sum(row["a0"]["iterations"] for row in diagnostics),
        "a0_full_exact_calls": sum(row["a0"]["full_exact_calls"] for row in diagnostics),
        "a0_scenario_evaluations": sum(row["a0"]["scenario_evaluations"] for row in diagnostics),
        "a1_iterations": sum(row["a1"]["iterations"] for row in diagnostics),
        "memory_opportunities": sum(row["a1"]["memory_opportunities"] for row in diagnostics),
        "memory_hits": sum(row["a1"]["memory_hits"] for row in diagnostics),
        "candidate_hits": sum(row["a1"]["candidate_hits"] for row in diagnostics),
        "a1_full_exact_certification_calls": sum(row["a1"]["full_exact_certification_calls"] for row in diagnostics),
        "a1_scenario_evaluations": sum(row["a1"]["scenario_evaluations"] for row in diagnostics),
        "runtime_seconds": {
            method: sum(row["runtime_seconds"][method] for row in diagnostics)
            for method in ("EF", "A0", "A1")
        },
    }


def run_r5_pilot(repo_root: Path, workbook_path: Path) -> dict[str, Any]:
    root = repo_root.resolve()
    config_path = root / EXECUTION_CONFIG_PATH
    config = load_execution_config(config_path)
    if sha256_file(root / PROTOCOL_PATH) != PROTOCOL_SHA256:
        raise RuntimeError("R5 protocol hash mismatch")
    source_git = validate_source_state(
        root,
        required_tracked_paths=[root / path for path in SOURCE_PATHS],
        scientific_roots=("src", "configs", "scripts", "tests/fixtures"),
    )
    workbook_audit = audit_wfp_workbook(workbook_path, config["wfp_workbook"])
    cases: list[dict[str, Any]] = []
    baseline_path = root / config["baseline_path"]
    for ratio in config["budget_ratios"]:
        baseline = load_pilot_baseline(baseline_path, float(ratio))
        for model_kind in config["models"]:
            data = baseline.data
            ef = solve_qfr_extensive_form(data, model_kind)
            a0 = solve_qfr_standard_ccg(data, model_kind)
            a1 = solve_qfr_improved_ccg(data, model_kind, memory_phase_enabled=True)
            certificate = verify_ef_a0_a1(data, ef, a0, a1)
            case_id = f"B{ratio:.2f}_{model_kind}"
            cases.append(
                {
                    "case_id": case_id,
                    "budget_ratio": float(ratio),
                    "model_kind": model_kind,
                    "data_sha256": data.data_sha256,
                    "scenario_sha256": data.scenario_sha256,
                    "ef": ef,
                    "a0": a0,
                    "a1": a1,
                    "certificate": certificate,
                    "diagnostic": _diagnostic_case(data, ef, a0, a1, certificate),
                }
            )
    evidence = seal_evidence(
        {
            "schema_version": 1,
            "phase": "R5_PILOT_MECHANISM_DIAGNOSIS",
            "scope": config["scope"],
            "protocol": {"path": PROTOCOL_PATH, "sha256": PROTOCOL_SHA256},
            "source": {
                "git": source_git,
                "files": [{"path": path, "sha256": sha256_file(root / path)} for path in SOURCE_PATHS],
                "wfp_workbook": workbook_audit,
            },
            "configuration": {
                "path": EXECUTION_CONFIG_PATH,
                "sha256": sha256_file(config_path),
                "payload": config,
                "config_sha256": canonical_json_sha256(config),
                "baseline_sha256": sha256_file(baseline_path),
            },
            "environment": ensure_preflight_once().to_dict(),
            "solver_configuration": solver_configuration_identity(),
            "cases": cases,
            "summary": _summary(cases),
            "execution_counts": {
                "pilot_batches": 1,
                "pilot_cases": 9,
                "formal_experiment_runs": 0,
                "oos_runs": 0,
            },
        }
    )
    validate_r5_evidence(root, workbook_path, evidence)
    return evidence


def validate_r5_evidence(repo_root: Path, workbook_path: Path, evidence: Mapping[str, Any]) -> dict[str, Any]:
    root = repo_root.resolve()
    bare = dict(evidence)
    seal = bare.pop("evidence_sha256", None)
    if seal != canonical_json_sha256(bare):
        raise ValueError("R5 evidence seal mismatch")
    if evidence.get("schema_version") != 1 or evidence.get("phase") != "R5_PILOT_MECHANISM_DIAGNOSIS":
        raise ValueError("not R5 Q-F-R Pilot evidence")
    if evidence["protocol"] != {"path": PROTOCOL_PATH, "sha256": PROTOCOL_SHA256} or sha256_file(root / PROTOCOL_PATH) != PROTOCOL_SHA256:
        raise ValueError("R5 protocol identity mismatch")
    config_record = evidence["configuration"]
    config = load_execution_config(root / config_record["path"])
    if config_record["payload"] != config or config_record["sha256"] != sha256_file(root / config_record["path"]) or config_record["config_sha256"] != canonical_json_sha256(config):
        raise ValueError("R5 execution config identity mismatch")
    baseline_path = root / config["baseline_path"]
    if config_record["baseline_sha256"] != sha256_file(baseline_path):
        raise ValueError("R5 baseline identity mismatch")
    source = evidence["source"]
    git = source["git"]
    if git["tracked_dirty"] is not False or git["untracked_paths"] or git["untracked_scientific_paths"]:
        raise ValueError("R5 execution source was not clean")
    commit = str(git["commit_sha"])
    if _anchored_tree(root, commit) != git["tree_sha"] or tuple(git["tracked_input_paths"]) != SOURCE_PATHS:
        raise ValueError("R5 source commit/tree or inventory mismatch")
    if [row["path"] for row in source["files"]] != list(SOURCE_PATHS):
        raise ValueError("R5 source-file inventory mismatch")
    for row in source["files"]:
        if sha256_bytes(_anchored_file(root, commit, row["path"])) != row["sha256"]:
            raise ValueError("R5 anchored source hash mismatch")
    if source["wfp_workbook"] != audit_wfp_workbook(workbook_path, config["wfp_workbook"]):
        raise ValueError("R5 WFP workbook audit mismatch")
    if evidence["solver_configuration"] != solver_configuration_identity():
        raise ValueError("R5 solver configuration mismatch")
    expected = [(float(ratio), model) for ratio in config["budget_ratios"] for model in config["models"]]
    if len(evidence["cases"]) != len(expected):
        raise ValueError("R5 Pilot matrix is incomplete")
    checked: list[dict[str, Any]] = []
    for row, (ratio, model_kind) in zip(evidence["cases"], expected, strict=True):
        baseline = load_pilot_baseline(baseline_path, ratio)
        data = baseline.data
        if row["case_id"] != f"B{ratio:.2f}_{model_kind}" or row["budget_ratio"] != ratio or row["model_kind"] != model_kind or row["data_sha256"] != data.data_sha256 or row["scenario_sha256"] != data.scenario_sha256:
            raise ValueError("R5 Pilot case identity mismatch")
        validate_three_certificate(data, row["ef"], row["a0"], row["a1"], row["certificate"], expected_model_kind=model_kind)
        certificate = verify_ef_a0_a1(data, row["ef"], row["a0"], row["a1"])
        if row["certificate"] != certificate or row["diagnostic"] != _diagnostic_case(data, row["ef"], row["a0"], row["a1"], certificate):
            raise ValueError("R5 Pilot diagnostic does not recompute")
        checked.append(dict(row))
    if evidence["summary"] != _summary(checked):
        raise ValueError("R5 Pilot summary mismatch")
    if evidence["execution_counts"] != {"pilot_batches": 1, "pilot_cases": 9, "formal_experiment_runs": 0, "oos_runs": 0}:
        raise ValueError("R5 execution scope counts mismatch")
    runtime = evidence["summary"]["runtime_seconds"]
    if any(not math.isfinite(float(value)) or float(value) < 0 for value in runtime.values()):
        raise ValueError("R5 runtime summary is invalid")
    return {"status": "PASS", "case_count": len(checked), "evidence_sha256": seal}
