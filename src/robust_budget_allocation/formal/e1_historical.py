"""Fail-closed E1-Historical execution, diagnostics, comparison, and replay."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import subprocess
from typing import Any, Mapping

from robust_budget_allocation.algorithms.qfr_a1_verification import (
    validate_three_certificate,
    verify_ef_a0_a1,
)
from robust_budget_allocation.algorithms.qfr_extensive_form import solve_qfr_extensive_form
from robust_budget_allocation.algorithms.qfr_improved_ccg import solve_qfr_improved_ccg
from robust_budget_allocation.algorithms.qfr_protocol import solver_configuration_identity, tolerance
from robust_budget_allocation.algorithms.qfr_standard_ccg import solve_qfr_standard_ccg
from robust_budget_allocation.data.qfr_data import QFRData
from robust_budget_allocation.data.qfr_e1_historical import (
    DATASET_KIND,
    EXPECTED_ITEMS,
    EXPECTED_SCENARIOS,
    build_e1_historical_data,
)
from robust_budget_allocation.formal.e1 import _case_diagnostics
from robust_budget_allocation.io.atomic import atomic_write_json, atomic_write_text
from robust_budget_allocation.io.hashing import canonical_json_sha256, sha256_bytes, sha256_file
from robust_budget_allocation.reproducibility.git_state import inspect_git_state, require_tracked_files
from robust_budget_allocation.runtime.environment import ensure_preflight_once


EXECUTION_CONFIG_PATH = "configs/e1_historical_execution_v1.json"
DATA_PATH = "configs/e1_historical_rawls15_data_v1.json"
PROTOCOL_PATH = "docs/E1_HISTORICAL_PROTOCOL_v1.md"
OLD_51_SUMMARY_PATH = "experiments/r7_e1/summary.json"
EXPECTED_DATA_SHA256 = "d1b48e13757f0ca6ff4919e26b8ed3f225b3f2b7764e9026d16fc2f985ff487c"
EXPECTED_MODELS = ("M0", "M1", "M2")
EXPECTED_BUDGETS = (0.9, 1.0, 1.1)
SOURCE_PATHS = (
    EXECUTION_CONFIG_PATH,
    DATA_PATH,
    PROTOCOL_PATH,
    "configs/r6c_formal_ready_data_v2.json",
    "configs/r6c_scientific_revision_v2.json",
    OLD_51_SUMMARY_PATH,
    "docs/R6_C_SCIENTIFIC_REVISION_REFREEZE_v2.md",
    "docs/R3_CORRECTNESS_PROTOCOL_v2.md",
    "docs/R4_A1_PROTOCOL_v2.md",
    "src/robust_budget_allocation/data/qfr_e1_historical.py",
    "src/robust_budget_allocation/formal/e1_historical.py",
    "src/robust_budget_allocation/formal/e1.py",
    "src/robust_budget_allocation/data/qfr_data.py",
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
    "scripts/prepare_e1_historical_data.py",
    "scripts/e1_historical_experiment.py",
    "tests/test_e1_historical.py",
)


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def _git(root: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *arguments], check=True, capture_output=True, text=True
    ).stdout.strip()


def _cases(data_sha256: str) -> list[dict[str, Any]]:
    result = []
    for budget in EXPECTED_BUDGETS:
        for model in EXPECTED_MODELS:
            row = {
                "family": "E1-Historical",
                "dataset_kind": DATASET_KIND,
                "data_sha256": data_sha256,
                "model_kind": model,
                "budget_ratio": budget,
            }
            row["experiment_identity"] = canonical_json_sha256(row)
            result.append(row)
    return result


def _validate_ready(ready: Mapping[str, Any]) -> None:
    bare = dict(ready)
    seal = bare.pop("data_sha256", None)
    if seal != EXPECTED_DATA_SHA256 or canonical_json_sha256(bare) != seal:
        raise ValueError("E1-Historical data canonical identity mismatch")
    if ready.get("dataset_kind") != DATASET_KIND:
        raise ValueError("E1-Historical dataset kind mismatch")
    if tuple(ready.get("scenario_ordering", ())) != EXPECTED_SCENARIOS:
        raise ValueError("E1-Historical scenario identity/order mismatch")
    if ready.get("scenario_counts") != {"single": 15, "combined": 0, "no_hurricane": 0, "total": 15}:
        raise ValueError("E1-Historical scenario composition mismatch")
    if tuple(ready["qfr_data"]["items"]) != EXPECTED_ITEMS:
        raise ValueError("E1-Historical commodity identity mismatch")
    if not math.isclose(sum(float(row["probability"]) for row in ready["scenarios"]), 1.0, abs_tol=1e-12):
        raise ValueError("E1-Historical conditional probabilities do not sum to one")
    if not math.isclose(float(ready["source_single_probability_sum"]), 0.75, abs_tol=1e-12):
        raise ValueError("Rawls source single-scenario probability mass mismatch")
    expected_supply = {1: (0.9, 0.1), 2: (0.85, 0.3), 3: (0.8, 0.6), 4: (0.75, 0.8), 5: (0.7, 1.0)}
    for row in ready["scenarios"]:
        if row["scenario_type"] != "single" or len(row["hurricanes"]) != 1:
            raise ValueError("non-single scenario contamination")
        if (float(row["q_availability"]), float(row["disruption"])) != expected_supply[int(row["category"])]:
            raise ValueError("frozen category supply mapping mismatch")
    parameters = ready["parameters"]
    if parameters["reliability_mitigation"] != [0.2, 0.5, 0.8]:
        raise ValueError("frozen eta mismatch")
    if parameters["reliability_cost_ratios"] != [0.0, 0.1, 0.25]:
        raise ValueError("frozen reliability premium mismatch")
    if parameters["shortage_priority_lambda"] != dict.fromkeys(EXPECTED_ITEMS, 1.0):
        raise ValueError("frozen neutral priority mismatch")
    if float(parameters["shortage_beta"]) != 4.0:
        raise ValueError("frozen beta mismatch")
    if ready["flexible_capacity"] != {
        "Water": 18000000.0,
        "Seasonal Influenza Vaccine": 955734.406438632,
        "Crackers": 186200000.0,
    }:
        raise ValueError("mechanically derived Rawls-15 F_bar mismatch")
    if not math.isclose(float(ready["reference_budget"]), 6721988.79033174, abs_tol=1e-8):
        raise ValueError("mechanically derived Rawls-15 B_ref mismatch")
    data = QFRData.from_dict(ready["qfr_data"])
    data.validate()
    if data.scenario_sha256 != ready["scenario_sha256"]:
        raise ValueError("E1-Historical QFR scenario hash mismatch")


def load_authorities(repo_root: Path) -> dict[str, Any]:
    root = repo_root.resolve()
    execution = _load_json(root / EXECUTION_CONFIG_PATH)
    required = {
        "schema_version", "scope", "dataset_kind", "base_main_sha", "required_branch",
        "formal_ready_data_path", "formal_ready_data_sha256", "models", "budget_ratios",
        "case_count", "certification_chain", "a1_memory_phase_enabled", "timing_protocol",
        "solver_interface", "solver_fallback", "solver_threads", "output_root",
    }
    if set(execution) != required:
        raise ValueError("E1-Historical execution config schema mismatch")
    if (
        execution["scope"] != "E1_HISTORICAL_FORMAL_EXECUTION_ONLY"
        or execution["dataset_kind"] != DATASET_KIND
        or execution["formal_ready_data_path"] != DATA_PATH
        or execution["formal_ready_data_sha256"] != EXPECTED_DATA_SHA256
        or tuple(execution["models"]) != EXPECTED_MODELS
        or tuple(float(value) for value in execution["budget_ratios"]) != EXPECTED_BUDGETS
        or execution["case_count"] != 9
        or execution["certification_chain"] != ["EF", "A0", "A1_full"]
        or execution["a1_memory_phase_enabled"] is not True
        or execution["solver_interface"] != "gurobi_direct"
        or execution["solver_fallback"] is not False
        or execution["solver_threads"] != 1
    ):
        raise ValueError("E1-Historical execution policy mismatch")
    ready = _load_json(root / DATA_PATH)
    _validate_ready(ready)
    if build_e1_historical_data(root) != ready:
        raise ValueError("E1-Historical data does not deterministically regenerate")
    return {
        "execution": execution,
        "execution_config_identity": canonical_json_sha256(execution),
        "ready": ready,
        "cases": _cases(EXPECTED_DATA_SHA256),
    }


def build_case_data(ready: Mapping[str, Any], budget_ratio: float) -> QFRData:
    if float(budget_ratio) not in EXPECTED_BUDGETS:
        raise ValueError("unregistered E1-Historical budget ratio")
    payload = deepcopy(ready["qfr_data"])
    payload["budget"] = float(ready["reference_budget"]) * float(budget_ratio)
    data = QFRData.from_dict(payload)
    data.validate()
    return data


def solver_free_preflight(repo_root: Path, *, execution_gate: bool = False) -> dict[str, Any]:
    root = repo_root.resolve()
    authority = load_authorities(root)
    source = None
    if execution_gate:
        execution = authority["execution"]
        if _git(root, "branch", "--show-current") != execution["required_branch"]:
            raise RuntimeError("E1-Historical execution branch mismatch")
        if _git(root, "rev-parse", "origin/main") != execution["base_main_sha"]:
            raise RuntimeError("origin/main/base main SHA mismatch")
        subprocess.run(
            ["git", "-C", str(root), "merge-base", "--is-ancestor", execution["base_main_sha"], "HEAD"],
            check=True,
        )
        state = inspect_git_state(root)
        if state.tracked_dirty or state.untracked_paths:
            raise RuntimeError("first Formal execution requires a completely clean working tree")
        output = root / execution["output_root"]
        if output.exists():
            raise FileExistsError(f"Formal output root already exists: {output}")
        tracked = require_tracked_files(root, [root / path for path in SOURCE_PATHS])
        source = state.to_dict()
        source["tracked_input_paths"] = tracked
        source["untracked_scientific_paths"] = ()
    ready = authority["ready"]
    return {
        "status": "PASS",
        "dataset_kind": DATASET_KIND,
        "formal_ready_data_path": DATA_PATH,
        "formal_ready_data_sha256": EXPECTED_DATA_SHA256,
        "scenario_count": 15,
        "scenario_ids": list(EXPECTED_SCENARIOS),
        "scenario_set_sha256": ready["scenario_set_sha256"],
        "parameter_sha256": ready["parameter_sha256"],
        "B_ref_formula": ready["reference_budget_rule"],
        "B_ref": ready["reference_budget"],
        "old_51_B_ref": ready["old_51_reference_budget"],
        "F_bar": ready["flexible_capacity"],
        "old_51_F_bar": ready["old_51_flexible_capacity"],
        "case_count": 9,
        "case_identities": [row["experiment_identity"] for row in authority["cases"]],
        "source": source,
    }


def licensed_preflight(repo_root: Path, *, execution_gate: bool = False) -> dict[str, Any]:
    result = solver_free_preflight(repo_root, execution_gate=execution_gate)
    environment = ensure_preflight_once().to_dict()
    solver = solver_configuration_identity()
    if environment.get("status") != "PASS" or not environment.get("license_available"):
        raise RuntimeError("Gurobi environment/license preflight failed")
    if solver.get("solver_interface") != "gurobi_direct" or solver.get("threads") != 1 or solver.get("no_fallback") is not True:
        raise RuntimeError("frozen Gurobi solver configuration mismatch")
    result["environment"] = environment
    result["solver_configuration"] = solver
    return result


def _solve_case(ready: Mapping[str, Any], case: Mapping[str, Any]) -> dict[str, Any]:
    data = build_case_data(ready, float(case["budget_ratio"]))
    model = str(case["model_kind"])
    ef = solve_qfr_extensive_form(data, model)
    a0 = solve_qfr_standard_ccg(data, model)
    a1 = solve_qfr_improved_ccg(data, model, memory_phase_enabled=True)
    certificate = verify_ef_a0_a1(data, ef, a0, a1)
    validate_three_certificate(data, ef, a0, a1, certificate, expected_model_kind=model)
    result = {
        "schema_version": 1,
        "scope": "E1_HISTORICAL_FORMAL_CASE",
        "case": dict(case),
        "case_id": f"B{float(case['budget_ratio']):.2f}_{model}",
        "formal_data_sha256": EXPECTED_DATA_SHA256,
        "case_data_sha256": data.data_sha256,
        "scenario_sha256": data.scenario_sha256,
        "budget": float(data.budget),
        "certification_chain": ["EF", "A0", "A1_full"],
        "ef": ef,
        "a0": a0,
        "a1": a1,
        "certificate": certificate,
        "diagnostics": _case_diagnostics(ready, data, case, ef, a0, a1, certificate),
        "formal_scientific_runs": 1,
        "timing_repetitions": 0,
    }
    result["case_result_sha256"] = canonical_json_sha256(result)
    return result


def _raw_filename(case: Mapping[str, Any]) -> str:
    return f"B{float(case['budget_ratio']):.2f}_{case['model_kind']}_{case['experiment_identity']}.json"


def _summary(cases: list[Mapping[str, Any]]) -> dict[str, Any]:
    ordered = sorted(cases, key=lambda row: (float(row["case"]["budget_ratio"]), EXPECTED_MODELS.index(str(row["case"]["model_kind"]))))
    rows = []
    for case in ordered:
        diagnostics = case["diagnostics"]
        worst_id = diagnostics["active_worst_scenario"]["scenario_id"]
        worst = diagnostics["scenario_results"][worst_id]
        allocation = diagnostics["allocation"]
        f_total = {item: float(allocation[item]["aggregate_F_i"]) for item in EXPECTED_ITEMS}
        utilization = {
            item: (0.0 if f_total[item] <= tolerance(f_total[item], 0.0) else float(worst["exercise"][item]) / f_total[item])
            for item in EXPECTED_ITEMS
        }
        ranked = sorted(
            diagnostics["scenario_results"].items(),
            key=lambda pair: (-float(pair[1]["recourse_loss"]), pair[0]),
        )
        worst_loss = float(ranked[0][1]["recourse_loss"])
        near = [
            {"scenario_id": scenario, "recourse_loss": float(value["recourse_loss"]), "gap_to_worst": worst_loss - float(value["recourse_loss"])}
            for scenario, value in ranked[:5]
        ]
        certificate = case["certificate"]
        rows.append({
            "case_id": case["case_id"],
            "experiment_identity": case["case"]["experiment_identity"],
            "model_kind": case["case"]["model_kind"],
            "budget_ratio": case["case"]["budget_ratio"],
            "absolute_B": case["budget"],
            "objective_T_COST": diagnostics["robust_result"]["robust_objective_T_COST"],
            "first_stage_total_expenditure": diagnostics["cost_decomposition"]["first_stage_expenditure"],
            "Q_expenditure": diagnostics["cost_decomposition"]["C_Q"],
            "F_reservation_expenditure": diagnostics["cost_decomposition"]["C_F"],
            "R_expenditure": diagnostics["cost_decomposition"]["C_R"],
            "worst_emergency_exercise_expenditure": worst["C_E"],
            "worst_shortage_penalty": worst["shortage_loss"],
            "Q_i": {item: allocation[item]["Q_i"] for item in EXPECTED_ITEMS},
            "F_i": f_total,
            "selected_R_i": diagnostics["mechanism_activation"]["selected_R_levels"],
            "worst_scenario_id": worst_id,
            "worst_hurricane_ids": worst["hurricanes"],
            "worst_hurricane_names": None,
            "worst_category": worst["category"],
            "worst_scenario_demand": worst["demand"],
            "worst_exercise_x": worst["exercise"],
            "worst_shortage_u": worst["shortage"],
            "F_utilization_by_item": utilization,
            "budget_utilization": worst["budget_utilization"],
            "convergence_status": diagnostics["robust_result"]["convergence_status"],
            "certification_status": diagnostics["robust_result"]["certificate_status"],
            "A0_A1_consistency": {
                "status": certificate["status"],
                "objectives": certificate["objectives"],
                "maximum_objective_difference": certificate["maximum_objective_difference"],
                "maximum_feasibility_violation": certificate["maximum_feasibility_violation"],
                "certificate_sha256": certificate["certificate_sha256"],
            },
            "F_active": diagnostics["mechanism_activation"]["F_active"],
            "paid_R_active": diagnostics["mechanism_activation"]["paid_R_active"],
            "Q_F_mix_commodities": diagnostics["mechanism_activation"]["Q_F_mix_commodities"],
            "probability_weighted_total_shortage": diagnostics["service_outcome"]["probability_weighted_total_shortage"],
            "worst_total_shortage": worst["total_shortage"],
            "near_worst_top5": near,
            "scenarios_within_1pct_of_worst_loss": sum(float(value["recourse_loss"]) >= 0.99 * worst_loss for value in diagnostics["scenario_results"].values()),
            "scenario_count_certified": len(diagnostics["scenario_results"]),
        })
    by_key = {(float(row["budget_ratio"]), str(row["model_kind"])): row for row in rows}
    contrasts = []
    for budget in EXPECTED_BUDGETS:
        for left, right, mechanism in (("M0", "M1", "F"), ("M1", "M2", "R")):
            a, b = by_key[(budget, left)], by_key[(budget, right)]
            contrasts.append({
                "budget_ratio": budget,
                "contrast": f"{right}-{left}",
                "mechanism": mechanism,
                "objective_change": b["objective_T_COST"] - a["objective_T_COST"],
                "objective_improvement": a["objective_T_COST"] - b["objective_T_COST"],
                "shortage_change": b["probability_weighted_total_shortage"] - a["probability_weighted_total_shortage"],
            })
    result = {
        "schema_version": 1,
        "scope": "E1_HISTORICAL_FORMAL_SUMMARY",
        "dataset_kind": DATASET_KIND,
        "status": "PASS" if len(rows) == 9 and all(row["certification_status"] == "PASS" and row["scenario_count_certified"] == 15 for row in rows) else "FAIL",
        "case_count": len(rows),
        "rows": rows,
        "same_budget_model_contrasts": contrasts,
        "same_model_budget_paths": [
            {"model_kind": model, "cases": [by_key[(budget, model)] for budget in EXPECTED_BUDGETS]}
            for model in EXPECTED_MODELS
        ],
        "formal_scientific_runs": len(rows),
        "e1_extended_runs": 0,
        "e2_e5_runs": 0,
        "timing_repetitions": 0,
    }
    result["summary_sha256"] = canonical_json_sha256(result)
    return result


def _comparison(summary: Mapping[str, Any], old: Mapping[str, Any]) -> dict[str, Any]:
    old_by_key = {(float(row["budget_ratio"]), str(row["model_kind"])): row for row in old["rows"]}
    rows = []
    for row in summary["rows"]:
        prior = old_by_key[(float(row["budget_ratio"]), str(row["model_kind"]))]
        old_shortage = float(prior["probability_weighted_total_shortage"])
        rows.append({
            "case_id": row["case_id"],
            "old_51_objective": float(prior["objective"]),
            "historical_15_objective": row["objective_T_COST"],
            "objective_change_15_minus_51": row["objective_T_COST"] - float(prior["objective"]),
            "old_51_F_active": bool(prior["F_active"]),
            "historical_15_F_active": row["F_active"],
            "old_51_paid_R_active": bool(prior["paid_R_active"]),
            "historical_15_paid_R_active": row["paid_R_active"],
            "old_51_probability_weighted_shortage": old_shortage,
            "historical_15_probability_weighted_shortage": row["probability_weighted_total_shortage"],
            "shortage_change_15_minus_51": row["probability_weighted_total_shortage"] - old_shortage,
            "old_51_worst_scenario": prior["active_worst_scenario"]["scenario_id"],
            "historical_15_worst_scenario": row["worst_scenario_id"],
        })
    result = {
        "schema_version": 1,
        "scope": "E1_HISTORICAL_VS_REPOSITORY_OLD_51_COMPARISON",
        "old_51_source": OLD_51_SUMMARY_PATH,
        "old_51_identity": old.get("summary_sha256"),
        "historical_15_identity": summary["summary_sha256"],
        "comparability_warning": (
            "The repository old-51 results are explicitly pre-revision historical diagnostic evidence. "
            "They used old eta0/delta/lambda values, whereas E1-Historical inherits the current frozen R6-C v2 values. "
            "Therefore numerical differences cannot be causally attributed to scenario-set deletion alone; no extra 51-scenario rerun was authorized."
        ),
        "rows": rows,
    }
    result["comparison_sha256"] = canonical_json_sha256(result)
    return result


def _report(manifest: Mapping[str, Any], summary: Mapping[str, Any], comparison: Mapping[str, Any]) -> str:
    table = [
        "| Case | T-COST | Q exp. | F exp. | R exp. | F | paid R | worst | cat |",
        "| --- | ---: | ---: | ---: | ---: | --- | --- | --- | ---: |",
    ]
    for row in summary["rows"]:
        table.append(
            f"| {row['case_id']} | {row['objective_T_COST']:.10g} | {row['Q_expenditure']:.10g} | "
            f"{row['F_reservation_expenditure']:.10g} | {row['R_expenditure']:.10g} | "
            f"{row['F_active']} | {row['paid_R_active']} | {row['worst_scenario_id']} | {row['worst_category']} |"
        )
    source = manifest["source"]["git"]
    return "\n".join([
        "# E1-Historical Formal Experiment Report",
        "",
        "Status: **PASS — ready for independent review**",
        "",
        "## Research position",
        "",
        "E1-Historical is the first formal component of E1. It validates the basic Q-F-R economic mechanism on the classical historical benchmark formed by Rawls' original 15 single-hurricane scenarios. E1-Extended will later use an independently constructed, larger real historical single-hurricane uncertainty set through 2025 to test whether the same mechanism persists under broader empirical uncertainty. This run does not perform or claim E1-Extended, E2–E5, or sensitivity analysis.",
        "",
        "## Identity and derivation audit",
        "",
        f"- execution commit: `{source['commit_sha']}`; tree: `{source['tree_sha']}`",
        f"- dataset: `{DATASET_KIND}`; data SHA-256: `{manifest['formal_ready_data_sha256']}`",
        f"- ordered scenarios: `{', '.join(EXPECTED_SCENARIOS)}`",
        f"- scenario-set SHA-256: `{manifest['preflight']['scenario_set_sha256']}`",
        f"- parameter SHA-256: `{manifest['preflight']['parameter_sha256']}`",
        f"- B_ref formula: `{manifest['preflight']['B_ref_formula']}`",
        f"- old 51 B_ref: `{manifest['preflight']['old_51_B_ref']}`; Rawls-15 B_ref: `{manifest['preflight']['B_ref']}`",
        f"- old 51 F_bar: `{json.dumps(manifest['preflight']['old_51_F_bar'], sort_keys=True)}`",
        f"- Rawls-15 F_bar: `{json.dumps(manifest['preflight']['F_bar'], sort_keys=True)}`",
        "- B_ref and F_bar changes are mechanical applications of the same frozen formulas to the conditioned 15-scenario dataset, not recalibration.",
        "- The authoritative source has hurricane IDs and categories but no hurricane-name field; names are recorded as unavailable rather than inferred.",
        "",
        "## Nine-case results",
        "",
        *table,
        "",
        "Complete Q_i/F_i/R_i, worst-scenario demand/x/u, expenditures, utilization, near-worst rankings, all 15 scenario diagnostics, EF/A0/A1 evidence, and certificate identities are in `summary.json` and `raw/`.",
        "",
        "## Validation and old-51 comparison",
        "",
        "All nine cases passed EF/A0/A1 objective/feasibility consistency, memory-guided A1 convergence, and Full Exact Certification over exactly 15 scenarios. Deterministic replay and the output hash inventory passed.",
        "",
        comparison["comparability_warning"],
        "The repository old 51-scenario results are preserved and were not modified. The machine-readable case-by-case comparison is `old_51_comparison.json`.",
        "",
    ])


def _validate_raw(path: Path, ready: Mapping[str, Any], expected_case: Mapping[str, Any]) -> dict[str, Any]:
    result = _load_json(path)
    bare = dict(result)
    seal = bare.pop("case_result_sha256", None)
    if seal != canonical_json_sha256(bare) or result.get("case") != expected_case:
        raise ValueError(f"raw case seal/identity mismatch: {path.name}")
    if result.get("scope") != "E1_HISTORICAL_FORMAL_CASE" or result.get("formal_data_sha256") != EXPECTED_DATA_SHA256:
        raise ValueError(f"raw execution scope mismatch: {path.name}")
    data = build_case_data(ready, float(expected_case["budget_ratio"]))
    validate_three_certificate(data, result["ef"], result["a0"], result["a1"], result["certificate"], expected_model_kind=str(expected_case["model_kind"]))
    expected = _case_diagnostics(ready, data, expected_case, result["ef"], result["a0"], result["a1"], result["certificate"])
    if result["diagnostics"] != expected:
        raise ValueError(f"raw diagnostics do not replay: {path.name}")
    return result


def replay_delivery(repo_root: Path) -> dict[str, Any]:
    root = repo_root.resolve()
    authority = load_authorities(root)
    output = root / authority["execution"]["output_root"]
    expected_names = [_raw_filename(case) for case in authority["cases"]]
    raw_files = sorted((output / "raw").glob("*.json"))
    if [path.name for path in raw_files] != sorted(expected_names):
        raise ValueError("raw case inventory mismatch")
    results = [_validate_raw(output / "raw" / _raw_filename(case), authority["ready"], case) for case in authority["cases"]]
    summary = _summary(results)
    if _load_json(output / "summary.json") != summary:
        raise ValueError("summary deterministic regeneration mismatch")
    comparison = _comparison(summary, _load_json(root / OLD_51_SUMMARY_PATH))
    if _load_json(output / "old_51_comparison.json") != comparison:
        raise ValueError("old-51 comparison deterministic regeneration mismatch")
    manifest = _load_json(output / "manifest.json")
    bare = dict(manifest)
    seal = bare.pop("manifest_sha256", None)
    if seal != canonical_json_sha256(bare):
        raise ValueError("manifest seal mismatch")
    git = manifest["source"]["git"]
    commit = str(git["commit_sha"])
    if tuple(git["tracked_input_paths"]) != SOURCE_PATHS or git["tracked_dirty"] is not False or git["untracked_paths"]:
        raise ValueError("anchored execution source-state mismatch")
    if _git(root, "show", "-s", "--format=%T", commit) != git["tree_sha"]:
        raise ValueError("anchored execution tree mismatch")
    for row in manifest["source"]["files"]:
        anchored = subprocess.run(["git", "-C", str(root), "show", f"{commit}:{row['path']}"], check=True, capture_output=True).stdout
        if sha256_bytes(anchored) != row["sha256"]:
            raise ValueError(f"anchored source hash mismatch: {row['path']}")
    lines = (output / "HASHES.sha256").read_text(encoding="utf-8").splitlines()
    for line in lines:
        digest, relative = line.split("  ", 1)
        if sha256_file(output / relative) != digest:
            raise ValueError(f"output hash mismatch: {relative}")
    return {"status": "PASS", "case_count": 9, "certificate_pass_count": 9, "manifest_sha256": seal, "summary_sha256": summary["summary_sha256"], "comparison_sha256": comparison["comparison_sha256"]}


def run_e1_historical(repo_root: Path) -> dict[str, Any]:
    root = repo_root.resolve()
    preflight = licensed_preflight(root, execution_gate=True)
    authority = load_authorities(root)
    output = root / authority["execution"]["output_root"]
    (output / "raw").mkdir(parents=True, exist_ok=False)
    state = {
        "schema_version": 1, "scope": "E1_HISTORICAL_RUN_STATE", "status": "RUNNING",
        "started_at_utc": datetime.now(timezone.utc).isoformat(), "completed_case_identities": [],
        "formal_scientific_runs_started": 0, "formal_scientific_runs_completed": 0,
        "invalid_or_incomplete_runs": 0,
    }
    atomic_write_json(output / "RUN_STATE.json", state)
    results = []
    try:
        for case in authority["cases"]:
            state["formal_scientific_runs_started"] += 1
            atomic_write_json(output / "RUN_STATE.json", state)
            result = _solve_case(authority["ready"], case)
            atomic_write_json(output / "raw" / _raw_filename(case), result)
            results.append(result)
            state["completed_case_identities"].append(case["experiment_identity"])
            state["formal_scientific_runs_completed"] = len(results)
            atomic_write_json(output / "RUN_STATE.json", state)
    except Exception as exc:
        state.update({
            "status": "INVALID", "failed_at_utc": datetime.now(timezone.utc).isoformat(),
            "error_type": type(exc).__name__, "error": str(exc),
            "invalid_or_incomplete_runs": state["formal_scientific_runs_started"] - len(results),
        })
        atomic_write_json(output / "RUN_STATE.json", state)
        raise
    summary = _summary(results)
    if summary["status"] != "PASS":
        raise RuntimeError("E1-Historical summary completeness/certificate gate failed")
    atomic_write_json(output / "summary.json", summary)
    comparison = _comparison(summary, _load_json(root / OLD_51_SUMMARY_PATH))
    atomic_write_json(output / "old_51_comparison.json", comparison)
    source_files = [{"path": path, "sha256": sha256_file(root / path)} for path in SOURCE_PATHS]
    manifest = {
        "schema_version": 1, "scope": "E1_HISTORICAL_FORMAL_EXPERIMENT", "status": "PASS",
        "source": {"git": preflight["source"], "files": source_files},
        "preflight": preflight,
        "execution_config_path": EXECUTION_CONFIG_PATH,
        "execution_config_identity": authority["execution_config_identity"],
        "formal_ready_data_sha256": EXPECTED_DATA_SHA256,
        "case_count": 9, "certificate_pass_count": 9, "formal_scientific_runs": 9,
        "e1_extended_runs": 0, "e2_e5_runs": 0, "timing_repetitions": 0,
        "invalid_or_incomplete_runs": 0,
        "case_files": [
            {"case_id": result["case_id"], "experiment_identity": result["case"]["experiment_identity"], "path": f"raw/{_raw_filename(result['case'])}", "case_result_sha256": result["case_result_sha256"]}
            for result in results
        ],
        "summary_path": "summary.json", "summary_sha256": summary["summary_sha256"],
        "comparison_path": "old_51_comparison.json", "comparison_sha256": comparison["comparison_sha256"],
        "report_path": "REPORT.md",
    }
    manifest["manifest_sha256"] = canonical_json_sha256(manifest)
    atomic_write_json(output / "manifest.json", manifest)
    state.update({
        "status": "PASS", "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "formal_scientific_runs_completed": 9, "invalid_or_incomplete_runs": 0,
        "manifest_sha256": manifest["manifest_sha256"],
    })
    atomic_write_json(output / "RUN_STATE.json", state)
    atomic_write_text(output / "REPORT.md", _report(manifest, summary, comparison))
    paths = [Path(row["path"]) for row in manifest["case_files"]] + [
        Path("summary.json"), Path("old_51_comparison.json"), Path("manifest.json"), Path("RUN_STATE.json"), Path("REPORT.md")
    ]
    atomic_write_text(output / "HASHES.sha256", "".join(f"{sha256_file(output / path)}  {path.as_posix()}\n" for path in paths))
    replay = replay_delivery(root)
    return {"preflight": preflight, "manifest": manifest, "summary": summary, "comparison": comparison, "replay": replay}
