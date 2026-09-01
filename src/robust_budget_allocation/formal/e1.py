"""Fail-closed R7-E1 execution, diagnostics, and replay."""

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
from robust_budget_allocation.io.atomic import atomic_write_json, atomic_write_text
from robust_budget_allocation.io.hashing import canonical_json_sha256, sha256_bytes, sha256_file
from robust_budget_allocation.reproducibility.git_state import inspect_git_state, require_tracked_files
from robust_budget_allocation.runtime.environment import ensure_preflight_once


EXECUTION_CONFIG_PATH = "configs/r7_e1_execution_v1.json"
PROTOCOL_PATH = "docs/R7_E1_PROTOCOL_v1.md"
EXPECTED_DATA_SHA256 = "3eaf0357d9d586198a8887c59b8e67ebeeb2ab8d7224923db854dca717f236f5"
EXPECTED_CONFIG_IDENTITY = "ccf90d26d8947e2b0607d38c9812f69c485b5f1532fc5b9e9e8cd0b2abb7e0a2"
EXPECTED_MATRIX_IDENTITY = "cbedbec9643400af69b0d4369cfd0f1e0a0ccf4e9b61d26c5fc48717948f6b49"
EXPECTED_HUMAN_SPEC_SHA256 = "f1146f5ba6b25723a5e5f55b8106c4954c7804bfde03a49dfe8f8e88abe5fcc4"
EXPECTED_DELIVERY_MANIFEST_SHA256 = "177485800b5bbc50fe15e0e1d13a6188a5c6d617ba889207815ba7d5c79a6780"
EXPECTED_ITEMS = ("Water", "Seasonal Influenza Vaccine", "Crackers")
EXPECTED_MODELS = ("M0", "M1", "M2")
EXPECTED_BUDGETS = (0.9, 1.0, 1.1)
SOURCE_PATHS = (
    EXECUTION_CONFIG_PATH,
    PROTOCOL_PATH,
    "configs/r6_formal_ready_data_v1.json",
    "configs/r6_formal_experiment_matrix_v1.json",
    "configs/r6_formal_experiment_matrix_expanded_v1.json",
    "docs/R6_DATA_DELIVERY_MANIFEST.json",
    "docs/R6_B_DELIVERY_MANIFEST.json",
    "docs/R6_FORMAL_EXPERIMENT_MATRIX_v1.md",
    "docs/MODEL_SPEC_v2.md",
    "docs/R3_CORRECTNESS_PROTOCOL_v2.md",
    "docs/R4_A1_PROTOCOL_v2.md",
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
    "src/robust_budget_allocation/formal/e1.py",
    "scripts/r7_e1_main_experiment.py",
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


def _validate_ready_payload(ready: Mapping[str, Any]) -> None:
    bare = dict(ready)
    embedded = bare.pop("data_sha256", None)
    if embedded != EXPECTED_DATA_SHA256 or canonical_json_sha256(bare) != embedded:
        raise ValueError("Formal-ready data canonical identity mismatch")
    if len(ready.get("scenarios", [])) != 51:
        raise ValueError("Formal-ready scenario count is not 51")
    if tuple(ready.get("qfr_data", {}).get("items", [])) != EXPECTED_ITEMS:
        raise ValueError("Formal commodity identity mismatch")
    if ready.get("scenario_counts") != {"combined": 35, "no_hurricane": 1, "single": 15}:
        raise ValueError("Formal scenario composition mismatch")
    rows = ready["scenarios"]
    if not math.isclose(sum(float(row["probability"]) for row in rows), 1.0, abs_tol=1e-12):
        raise ValueError("Formal scenario probabilities do not sum to one")
    expected = {0: (1.0, 0.0), 1: (0.9, 0.1), 2: (0.85, 0.3), 3: (0.8, 0.6), 4: (0.75, 1.0), 5: (0.7, 1.0)}
    for row in rows:
        category = int(row["category"])
        if (float(row["q_availability"]), float(row["disruption"])) != expected[category]:
            raise ValueError("Formal category/rhoQ/delta mapping mismatch")
    if float(ready.get("reference_budget", -1)) != 7975014.2749022:
        raise ValueError("Formal B_ref mismatch")
    if ready.get("flexible_capacity") != {
        "Water": 27000000.0,
        "Seasonal Influenza Vaccine": 1144366.1971831,
        "Crackers": 206878000.0,
    }:
        raise ValueError("Formal F_bar mismatch")


def _validate_e1_cases(cases: Any) -> list[dict[str, Any]]:
    if not isinstance(cases, list) or len(cases) != 9:
        raise ValueError("E1 must contain exactly 9 cases")
    expected = [(budget, model) for budget in EXPECTED_BUDGETS for model in EXPECTED_MODELS]
    observed: list[tuple[float, str]] = []
    identities: set[str] = set()
    for row in cases:
        if set(row) != {"budget_ratio", "data_sha256", "experiment_identity", "family", "model_kind"}:
            raise ValueError("E1 case schema mismatch")
        if row["family"] != "E1" or row["data_sha256"] != EXPECTED_DATA_SHA256:
            raise ValueError("non-E1 or wrong-data case contamination")
        identity = str(row["experiment_identity"])
        if len(identity) != 64 or identity in identities:
            raise ValueError("duplicate or malformed E1 case identity")
        identities.add(identity)
        observed.append((float(row["budget_ratio"]), str(row["model_kind"])))
    if observed != expected:
        raise ValueError("E1 case ordering or model/budget matrix mismatch")
    return [dict(row) for row in cases]


def load_authorities(repo_root: Path) -> dict[str, Any]:
    root = repo_root.resolve()
    execution = _load_json(root / EXECUTION_CONFIG_PATH)
    required_execution = {
        "schema_version", "scope", "base_main_sha", "required_branch",
        "formal_ready_data_path", "formal_ready_data_sha256",
        "r6_experiment_config_path", "r6_experiment_config_identity_sha256",
        "r6_expanded_matrix_path", "r6_expanded_matrix_identity_sha256",
        "r6_human_spec_path", "r6_human_spec_sha256", "models", "budget_ratios",
        "case_count", "certification_chain", "a1_memory_phase_enabled",
        "timing_protocol", "solver_interface", "solver_fallback", "solver_threads",
        "output_root",
    }
    if set(execution) != required_execution:
        raise ValueError("R7-E1 execution config schema mismatch")
    if (
        execution["schema_version"] != 1
        or execution["scope"] != "R7_E1_FORMAL_MAIN_EXPERIMENT_ONLY"
        or tuple(execution["models"]) != EXPECTED_MODELS
        or tuple(float(value) for value in execution["budget_ratios"]) != EXPECTED_BUDGETS
        or execution["case_count"] != 9
        or execution["certification_chain"] != ["EF", "A0", "A1_full"]
        or execution["a1_memory_phase_enabled"] is not True
        or execution["timing_protocol"] != "NO_TIMING_REPETITIONS_E1"
        or execution["solver_interface"] != "gurobi_direct"
        or execution["solver_fallback"] is not False
        or execution["solver_threads"] != 1
    ):
        raise ValueError("R7-E1 execution policy mismatch")
    data_manifest = _load_json(root / "docs/R6_DATA_DELIVERY_MANIFEST.json")
    r6b_manifest = _load_json(root / "docs/R6_B_DELIVERY_MANIFEST.json")
    formal_path = data_manifest["formal_ready_data"]["path"]
    if formal_path != execution["formal_ready_data_path"] or data_manifest["formal_ready_data"]["data_sha256"] != EXPECTED_DATA_SHA256:
        raise ValueError("R6 authoritative Formal-ready path/identity mismatch")
    authority = r6b_manifest["authoritative_specification"]
    if (
        authority["config_path"] != execution["r6_experiment_config_path"]
        or authority["config_identity_sha256"] != EXPECTED_CONFIG_IDENTITY
        or authority["expanded_path"] != execution["r6_expanded_matrix_path"]
        or authority["matrix_identity_sha256"] != EXPECTED_MATRIX_IDENTITY
        or authority["human_spec_path"] != execution["r6_human_spec_path"]
    ):
        raise ValueError("R6-B authoritative path/identity chain mismatch")
    ready = _load_json(root / formal_path)
    _validate_ready_payload(ready)
    config = _load_json(root / authority["config_path"])
    if canonical_json_sha256(config) != EXPECTED_CONFIG_IDENTITY:
        raise ValueError("R6-B config canonical identity mismatch")
    if config.get("formal_ready_data_path") != formal_path or config.get("formal_ready_data_sha256") != EXPECTED_DATA_SHA256:
        raise ValueError("R6-B config does not uniquely bind the Formal-ready dataset")
    expanded = _load_json(root / authority["expanded_path"])
    bare_matrix = dict(expanded)
    seal = bare_matrix.pop("matrix_sha256", None)
    if seal != EXPECTED_MATRIX_IDENTITY or canonical_json_sha256(bare_matrix) != seal:
        raise ValueError("R6-B expanded matrix identity mismatch")
    if sha256_file(root / authority["human_spec_path"]) != EXPECTED_HUMAN_SPEC_SHA256:
        raise ValueError("R6-B human specification SHA-256 mismatch")
    cases = _validate_e1_cases(expanded.get("E1_cases"))
    return {
        "execution": execution,
        "execution_config_identity": canonical_json_sha256(execution),
        "ready": ready,
        "r6_config": config,
        "expanded": expanded,
        "cases": cases,
        "paths": {
            "formal_ready_data": formal_path,
            "r6_experiment_config": authority["config_path"],
            "r6_expanded_matrix": authority["expanded_path"],
            "r6_human_spec": authority["human_spec_path"],
        },
    }


def build_case_data(ready: Mapping[str, Any], budget_ratio: float) -> QFRData:
    if float(budget_ratio) not in EXPECTED_BUDGETS:
        raise ValueError("unregistered E1 budget ratio")
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
            raise RuntimeError("R7-E1 execution branch mismatch")
        if _git(root, "rev-parse", "origin/main") != execution["base_main_sha"]:
            raise RuntimeError("origin/main/base main SHA mismatch")
        subprocess.run(
            ["git", "-C", str(root), "merge-base", "--is-ancestor", execution["base_main_sha"], "HEAD"],
            check=True,
        )
        state = inspect_git_state(root)
        if state.tracked_dirty or state.untracked_paths:
            raise RuntimeError("first Formal execution requires a completely clean working tree")
        output_root = root / execution["output_root"]
        if output_root.exists():
            raise FileExistsError(f"Formal output root already exists: {output_root}")
        tracked_inputs = require_tracked_files(root, [root / path for path in SOURCE_PATHS])
        source = state.to_dict()
        source["tracked_input_paths"] = tracked_inputs
        source["untracked_scientific_paths"] = ()
    return {
        "status": "PASS",
        "formal_ready_data_path": authority["paths"]["formal_ready_data"],
        "formal_ready_data_sha256": EXPECTED_DATA_SHA256,
        "scenario_count": 51,
        "commodities": list(EXPECTED_ITEMS),
        "B_ref": float(authority["ready"]["reference_budget"]),
        "F_bar": dict(authority["ready"]["flexible_capacity"]),
        "r6_experiment_config_path": authority["paths"]["r6_experiment_config"],
        "r6_experiment_config_identity_sha256": EXPECTED_CONFIG_IDENTITY,
        "r6_expanded_matrix_identity_sha256": EXPECTED_MATRIX_IDENTITY,
        "r6_human_spec_sha256": EXPECTED_HUMAN_SPEC_SHA256,
        "e1_case_count": 9,
        "e1_case_identities": [row["experiment_identity"] for row in authority["cases"]],
        "source": source,
    }


def licensed_preflight(repo_root: Path, *, execution_gate: bool = False) -> dict[str, Any]:
    result = solver_free_preflight(repo_root, execution_gate=execution_gate)
    environment = ensure_preflight_once().to_dict()
    solver = solver_configuration_identity()
    if environment.get("status") != "PASS" or not environment.get("license_available"):
        raise RuntimeError("Gurobi environment/license preflight failed")
    if (
        solver.get("solver_interface") != "gurobi_direct"
        or solver.get("threads") != 1
        or solver.get("no_fallback") is not True
    ):
        raise RuntimeError("frozen Gurobi solver configuration mismatch")
    result["environment"] = environment
    result["solver_configuration"] = solver
    return result


def _selected_level(first: Mapping[str, Any], item: str) -> int | None:
    selected = [int(level) for level, value in first["z"][item].items() if int(round(float(value))) == 1]
    return selected[0] if len(selected) == 1 else None


def _case_diagnostics(
    ready: Mapping[str, Any], data: QFRData, case: Mapping[str, Any],
    ef: Mapping[str, Any], a0: Mapping[str, Any], a1: Mapping[str, Any],
    certificate: Mapping[str, Any],
) -> dict[str, Any]:
    first, accounting, oracle = ef["first_stage"], ef["accounting"], ef["oracle"]
    levels = [int(level) for level in first["reliability_levels"]]
    f_total = {item: sum(float(first["f"][item][str(level)]) for level in levels) for item in data.items}
    selected = {item: _selected_level(first, item) for item in data.items}
    metadata = {row["scenario_id"]: row for row in ready["scenarios"]}
    probabilities = {row["scenario_id"]: float(row["probability"]) for row in ready["scenarios"]}
    scenarios: dict[str, Any] = {}
    for row in oracle["results"]:
        scenario = str(row["scenario_id"])
        shortage = {item: float(row["shortage"][item]) for item in data.items}
        total_shortage = sum(shortage.values())
        demand = {item: float(data.demand[scenario][item]) for item in data.items}
        total_demand = sum(demand.values())
        scenarios[scenario] = {
            "probability": probabilities[scenario],
            "hurricanes": list(metadata[scenario]["hurricanes"]),
            "category": int(metadata[scenario]["category"]),
            "rhoQ": {item: float(data.q_availability[scenario][item]) for item in data.items},
            "delta": {item: float(data.disruption[scenario][item]) for item in data.items},
            "demand": demand,
            "shortage": shortage,
            "total_shortage": total_shortage,
            "demand_satisfaction_rate": 1.0 if total_demand == 0 else 1.0 - total_shortage / total_demand,
            "exercise": {item: float(row["exercise"][item]) for item in data.items},
            "C_E": float(row["exercise_cost"]),
            "shortage_loss": float(row["shortage_loss"]),
            "recourse_loss": float(row["loss"]),
            "budget_expenditure": float(data.budget - float(row["unused_cash"])),
            "budget_utilization": float(data.budget - float(row["unused_cash"])) / float(data.budget),
            "maximum_feasibility_violation": float(row["maximum_feasibility_violation"]),
            "scenario_identity": row["scenario_identity"],
        }
    active_worst = str(oracle["worst_scenario"])
    shortage_worst = max(scenarios, key=lambda value: (scenarios[value]["total_shortage"], value))
    c_q, c_f, c_r, c_pre = (float(accounting[key]) for key in ("C_Q", "C_F", "C_R", "C_pre"))
    allocation = {}
    for item in data.items:
        q, f = float(first["q"][item]), f_total[item]
        quantity_total = q + f
        item_cq = (float(data.q_unit_cost[item]) + float(data.storage_cost[item]) * float(data.tau)) * q
        item_cf = float(data.reservation_cost[item]) * f
        item_cr = sum(float(data.reliability_cost[item][level]) * float(first["f"][item][str(level)]) for level in levels)
        allocation[item] = {
            "Q_i": q,
            "F_ir": dict(first["f"][item]),
            "aggregate_F_i": f,
            "R_decision": dict(first["z"][item]),
            "selected_R_level": selected[item],
            "reservation_allocation": dict(first["f"][item]),
            "Q_quantity_share": 0.0 if quantity_total == 0 else q / quantity_total,
            "F_quantity_share": 0.0 if quantity_total == 0 else f / quantity_total,
            "budget_components": {"C_Q": item_cq, "C_F": item_cf, "C_R": item_cr},
            "budget_shares": {
                "Q": item_cq / data.budget,
                "F": item_cf / data.budget,
                "R": item_cr / data.budget,
            },
        }
    service = {
        "active_worst_scenario_total_shortage": scenarios[active_worst]["total_shortage"],
        "active_worst_scenario_commodity_shortage": scenarios[active_worst]["shortage"],
        "active_worst_scenario_demand_satisfaction": scenarios[active_worst]["demand_satisfaction_rate"],
        "probability_weighted_total_shortage": sum(row["probability"] * row["total_shortage"] for row in scenarios.values()),
        "probability_weighted_commodity_shortage": {
            item: sum(row["probability"] * row["shortage"][item] for row in scenarios.values())
            for item in data.items
        },
        "maximum_shortage_scenario": shortage_worst,
        "worst_case_shortage": scenarios[shortage_worst]["total_shortage"],
    }
    return {
        "robust_result": {
            "robust_objective_T_COST": float(ef["objective"]),
            "formal_UB": float(a1["UB"]),
            "final_LB": float(a1["LB"]),
            "final_gap": max(0.0, float(a1["UB"]) - float(a1["LB"])),
            "convergence_status": str(a1["status"]),
            "certificate_status": str(certificate["status"]),
        },
        "allocation": allocation,
        "cost_decomposition": {
            "C_Q": c_q, "C_F": c_f, "C_R": c_r, "first_stage_expenditure": c_pre,
            "Q_F_R_budget_share": {"Q": c_q / data.budget, "F": c_f / data.budget, "R": c_r / data.budget},
            "scenario_emergency_exercise_expenditure": {key: row["C_E"] for key, row in scenarios.items()},
            "scenario_total_budget_expenditure": {key: row["budget_expenditure"] for key, row in scenarios.items()},
            "scenario_budget_utilization": {key: row["budget_utilization"] for key, row in scenarios.items()},
        },
        "service_outcome": service,
        "active_worst_scenario": {
            "scenario_id": active_worst,
            "hurricanes": scenarios[active_worst]["hurricanes"],
            "category": scenarios[active_worst]["category"],
            "rhoQ": scenarios[active_worst]["rhoQ"],
            "delta": scenarios[active_worst]["delta"],
        },
        "scenario_results": scenarios,
        "mechanism_activation": {
            "F_active": any(value > tolerance(value, 0.0) for value in f_total.values()),
            "paid_R_active": any(selected[item] not in (None, 0) and f_total[item] > tolerance(f_total[item], 0.0) for item in data.items),
            "selected_R_levels": selected,
            "Q_F_mix_commodities": [item for item in data.items if float(first["q"][item]) > tolerance(float(first["q"][item]), 0.0) and f_total[item] > tolerance(f_total[item], 0.0)],
        },
        "algorithm_diagnostics": {
            "EF_runtime_seconds": float(ef["runtime_seconds"]),
            "A0_runtime_seconds": float(a0["runtime_seconds"]),
            "A1_runtime_seconds": float(a1["runtime_seconds"]),
            "A0_iterations": int(a0["iterations"]),
            "A0_master_solves": int(a0["iterations"]),
            "A0_scenario_evaluations": int(a0["scenario_evaluations"]),
            "A1_iterations": int(a1["iterations"]),
            "A1_master_solves": int(a1["iterations"]),
            "A1_scenario_evaluations": int(a1["scenario_evaluations"]),
            "A1_memory_opportunities": int(a1["memory_opportunities"]),
            "A1_memory_hits": int(a1["memory_hits"]),
            "A1_candidate_hits": int(a1["candidate_hits"]),
            "A1_full_exact_certification_calls": int(a1["full_exact_certification_calls"]),
            "formal_UB_history": [
                {"iteration": int(row["iteration"]), "UB": float(row["UB"]), "incumbent_iteration": row["incumbent_iteration"]}
                for row in a1["trace"] if row.get("UB") is not None
            ],
            "incumbent_identity": a1["incumbent"]["first_stage_sha256"],
            "certificate_identity": certificate["certificate_sha256"],
            "full_exact_oracle_identity": a1["incumbent"]["oracle"]["oracle_sha256"],
        },
    }


def solve_case(ready: Mapping[str, Any], case: Mapping[str, Any]) -> dict[str, Any]:
    data = build_case_data(ready, float(case["budget_ratio"]))
    model = str(case["model_kind"])
    ef = solve_qfr_extensive_form(data, model)
    a0 = solve_qfr_standard_ccg(data, model)
    a1 = solve_qfr_improved_ccg(data, model, memory_phase_enabled=True)
    certificate = verify_ef_a0_a1(data, ef, a0, a1)
    validate_three_certificate(data, ef, a0, a1, certificate, expected_model_kind=model)
    result = {
        "schema_version": 1,
        "scope": "R7_E1_FORMAL_CASE",
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


def initialize_output_root(path: Path) -> None:
    if path.exists():
        raise FileExistsError(f"Formal output root already exists: {path}")
    (path / "raw").mkdir(parents=True, exist_ok=False)


def _summary(cases: list[Mapping[str, Any]]) -> dict[str, Any]:
    ordered = sorted(cases, key=lambda row: (float(row["case"]["budget_ratio"]), EXPECTED_MODELS.index(str(row["case"]["model_kind"]))))
    rows = []
    for case in ordered:
        d = case["diagnostics"]
        rows.append({
            "case_id": case["case_id"],
            "experiment_identity": case["case"]["experiment_identity"],
            "model_kind": case["case"]["model_kind"],
            "budget_ratio": case["case"]["budget_ratio"],
            "budget": case["budget"],
            "objective": d["robust_result"]["robust_objective_T_COST"],
            "formal_UB": d["robust_result"]["formal_UB"],
            "final_gap": d["robust_result"]["final_gap"],
            "certificate_status": d["robust_result"]["certificate_status"],
            "C_Q": d["cost_decomposition"]["C_Q"],
            "C_F": d["cost_decomposition"]["C_F"],
            "C_R": d["cost_decomposition"]["C_R"],
            "F_active": d["mechanism_activation"]["F_active"],
            "paid_R_active": d["mechanism_activation"]["paid_R_active"],
            "selected_R_levels": d["mechanism_activation"]["selected_R_levels"],
            "Q_F_mix_commodities": d["mechanism_activation"]["Q_F_mix_commodities"],
            "probability_weighted_total_shortage": d["service_outcome"]["probability_weighted_total_shortage"],
            "worst_case_shortage": d["service_outcome"]["worst_case_shortage"],
            "active_worst_scenario": d["active_worst_scenario"],
            "allocation": d["allocation"],
        })
    by_key = {(float(row["budget_ratio"]), str(row["model_kind"])): row for row in rows}
    expected_keys = {(budget, model) for budget in EXPECTED_BUDGETS for model in EXPECTED_MODELS}
    complete = set(by_key) == expected_keys
    model_contrasts = []
    if complete:
        for budget in EXPECTED_BUDGETS:
            for left, right, mechanism in (("M0", "M1", "F"), ("M1", "M2", "R")):
                a, b = by_key[(budget, left)], by_key[(budget, right)]
                model_contrasts.append({
                    "budget_ratio": budget, "contrast": f"{right}-{left}", "mechanism": mechanism,
                    "objective_change": b["objective"] - a["objective"],
                    "objective_improvement": a["objective"] - b["objective"],
                    "shortage_change": b["probability_weighted_total_shortage"] - a["probability_weighted_total_shortage"],
                })
    budget_paths = [
        {"model_kind": model, "cases": [by_key[(budget, model)] for budget in EXPECTED_BUDGETS if (budget, model) in by_key]}
        for model in EXPECTED_MODELS
    ]
    summary = {
        "schema_version": 1,
        "scope": "R7_E1_SUMMARY_ONLY",
        "status": "PASS" if complete and all(row["certificate_status"] == "PASS" for row in rows) else "FAIL",
        "case_count": len(rows),
        "rows": rows,
        "same_budget_model_contrasts": model_contrasts,
        "same_model_budget_paths": budget_paths,
        "formal_scientific_runs": len(rows),
        "e2_e5_runs": 0,
        "invalid_or_incomplete_runs": 0,
    }
    summary["summary_sha256"] = canonical_json_sha256(summary)
    return summary


def _load_and_validate_raw(path: Path, ready: Mapping[str, Any], expected_case: Mapping[str, Any]) -> dict[str, Any]:
    result = _load_json(path)
    bare = dict(result)
    seal = bare.pop("case_result_sha256", None)
    if seal != canonical_json_sha256(bare) or result.get("case") != expected_case:
        raise ValueError(f"raw E1 case seal/identity mismatch: {path.name}")
    if (
        result.get("scope") != "R7_E1_FORMAL_CASE"
        or result.get("certification_chain") != ["EF", "A0", "A1_full"]
        or result.get("formal_scientific_runs") != 1
        or result.get("timing_repetitions") != 0
        or result.get("formal_data_sha256") != EXPECTED_DATA_SHA256
    ):
        raise ValueError(f"raw E1 execution scope mismatch: {path.name}")
    data = build_case_data(ready, float(expected_case["budget_ratio"]))
    validate_three_certificate(data, result["ef"], result["a0"], result["a1"], result["certificate"], expected_model_kind=str(expected_case["model_kind"]))
    expected_diagnostics = _case_diagnostics(ready, data, expected_case, result["ef"], result["a0"], result["a1"], result["certificate"])
    if result["diagnostics"] != expected_diagnostics:
        raise ValueError(f"raw E1 diagnostics do not replay: {path.name}")
    return result


def _execution_report(manifest: Mapping[str, Any], summary: Mapping[str, Any]) -> str:
    rows = [
        "| Case | Objective | Formal UB | Gap | F active | Paid R active | Worst scenario |",
        "| --- | ---: | ---: | ---: | --- | --- | --- |",
    ]
    for row in summary["rows"]:
        rows.append(
            f"| {row['case_id']} | {row['objective']:.10g} | {row['formal_UB']:.10g} | "
            f"{row['final_gap']:.6g} | {row['F_active']} | {row['paid_R_active']} | "
            f"{row['active_worst_scenario']['scenario_id']} |"
        )
    source = manifest["source"]["git"]
    return "\n".join(
        [
            "# R7-E1 Formal Main Experiment 执行报告",
            "",
            "状态：**PASS — 等待独立复审**",
            "",
            "## Identity 与执行边界",
            "",
            f"- execution commit：`{source['commit_sha']}`",
            f"- execution tree：`{source['tree_sha']}`",
            f"- Formal-ready data SHA-256：`{manifest['formal_ready_data_sha256']}`",
            f"- R6-B config identity：`{manifest['r6_experiment_config_identity']}`",
            f"- E1 matrix identity：`{manifest['r6_expanded_matrix_identity']}`",
            "- E1 cases：9；Formal scientific runs：9；certificate PASS：9",
            "- E2–E5 runs：0；timing repetitions：0；`A1_no_memory` runs：0",
            "- INVALID/INCOMPLETE runs：0",
            "",
            "## Objective 与机制概览",
            "",
            *rows,
            "",
            "同 budget 的 `M1-M0` 与 `M2-M1`、同 model 的 budget path、逐 commodity "
            "allocation、shortage、worst-scenario identity 与完整 mechanism activation 均保存在 "
            "`summary.json`。每个 case 的完整 `EF/A0/A1/certificate` 与 scenario accounting "
            "保存在 `raw/`，summary 不替代 raw evidence。",
            "",
            "## 认证与重放",
            "",
            "9 个 cases 均通过 `verify_ef_a0_a1`、`validate_three_certificate` 与 Full Exact "
            "Certification。`HASHES.sha256` 覆盖 raw results、summary、manifest、run state 与本报告；"
            "deterministic non-solver summary regeneration 由 `replay` 验证。",
            "",
        ]
    )


def replay_delivery(repo_root: Path) -> dict[str, Any]:
    root = repo_root.resolve()
    authority = load_authorities(root)
    output = root / authority["execution"]["output_root"]
    raw_files = sorted((output / "raw").glob("*.json"))
    expected_names = [_raw_filename(case) for case in authority["cases"]]
    if [path.name for path in raw_files] != sorted(expected_names):
        raise ValueError("R7-E1 raw case inventory has missing, duplicate, or contaminated files")
    results = [
        _load_and_validate_raw(output / "raw" / _raw_filename(case), authority["ready"], case)
        for case in authority["cases"]
    ]
    summary = _summary(results)
    if _load_json(output / "summary.json") != summary:
        raise ValueError("R7-E1 summary deterministic regeneration mismatch")
    manifest = _load_json(output / "manifest.json")
    bare = dict(manifest)
    seal = bare.pop("manifest_sha256", None)
    if seal != EXPECTED_DELIVERY_MANIFEST_SHA256 or seal != canonical_json_sha256(bare):
        raise ValueError("R7-E1 manifest seal mismatch")
    if manifest["case_count"] != 9 or manifest["certificate_pass_count"] != 9 or manifest["formal_scientific_runs"] != 9:
        raise ValueError("R7-E1 manifest completeness mismatch")
    if manifest.get("e2_e5_runs") != 0 or manifest.get("invalid_or_incomplete_runs") != 0:
        raise ValueError("R7-E1 manifest contamination or invalid-run mismatch")
    source = manifest["source"]
    git = source["git"]
    commit = str(git["commit_sha"])
    if tuple(git["tracked_input_paths"]) != SOURCE_PATHS or git["tracked_dirty"] is not False or git["untracked_paths"]:
        raise ValueError("R7-E1 anchored execution source-state mismatch")
    if [row["path"] for row in source["files"]] != list(SOURCE_PATHS):
        raise ValueError("R7-E1 anchored source-file inventory mismatch")
    commit_available = subprocess.run(
        ["git", "-C", str(root), "cat-file", "-e", f"{commit}^{{commit}}"],
        capture_output=True,
    ).returncode == 0
    if commit_available:
        if _git(root, "show", "-s", "--format=%T", commit) != git["tree_sha"]:
            raise ValueError("R7-E1 anchored execution tree mismatch")
        for row in source["files"]:
            anchored = subprocess.run(
                ["git", "-C", str(root), "show", f"{commit}:{row['path']}"],
                check=True, capture_output=True,
            ).stdout
            if sha256_bytes(anchored) != row["sha256"]:
                raise ValueError(f"R7-E1 anchored source hash mismatch: {row['path']}")
    else:
        if _git(root, "rev-parse", "--is-shallow-repository") != "true":
            raise ValueError("R7-E1 anchored execution commit is unavailable in a non-shallow repository")
        # A depth-one delivery checkout cannot contain the historical execution
        # commit.  The fixed delivery-manifest seal above pins its tree SHA and
        # complete per-file source hash inventory without a network fetch.
    inventory_lines = (output / "HASHES.sha256").read_text(encoding="utf-8").splitlines()
    expected_inventory = sorted([
        *(f"raw/{name}" for name in expected_names),
        "summary.json", "manifest.json", "RUN_STATE.json", "REPORT.md",
    ])
    observed_inventory = sorted(line.split("  ", 1)[1] for line in inventory_lines)
    if observed_inventory != expected_inventory:
        raise ValueError("R7-E1 hash inventory path set mismatch")
    for line in inventory_lines:
        digest, relative = line.split("  ", 1)
        if sha256_file(output / relative) != digest:
            raise ValueError(f"R7-E1 hash inventory mismatch: {relative}")
    return {"status": "PASS", "case_count": 9, "certificate_pass_count": 9, "manifest_sha256": seal, "summary_sha256": summary["summary_sha256"]}


def run_e1(repo_root: Path) -> dict[str, Any]:
    root = repo_root.resolve()
    preflight = licensed_preflight(root, execution_gate=True)
    authority = load_authorities(root)
    output = root / authority["execution"]["output_root"]
    initialize_output_root(output)
    source = preflight["source"]
    started = datetime.now(timezone.utc).isoformat()
    completed: list[str] = []
    state = {
        "schema_version": 1, "scope": "R7_E1_RUN_STATE", "status": "RUNNING",
        "started_at_utc": started, "completed_case_identities": completed,
        "formal_scientific_runs_started": 0, "formal_scientific_runs_completed": 0,
        "invalid_or_incomplete_runs": 0,
    }
    atomic_write_json(output / "RUN_STATE.json", state)
    results: list[dict[str, Any]] = []
    try:
        for case in authority["cases"]:
            state["formal_scientific_runs_started"] += 1
            atomic_write_json(output / "RUN_STATE.json", state)
            result = solve_case(authority["ready"], case)
            atomic_write_json(output / "raw" / _raw_filename(case), result)
            results.append(result)
            completed.append(str(case["experiment_identity"]))
            state["formal_scientific_runs_completed"] = len(completed)
            atomic_write_json(output / "RUN_STATE.json", state)
    except Exception as exc:
        state.update({
            "status": "INVALID", "failed_at_utc": datetime.now(timezone.utc).isoformat(),
            "error_type": type(exc).__name__, "error": str(exc),
            "invalid_or_incomplete_runs": int(state["formal_scientific_runs_started"]) - len(completed),
        })
        atomic_write_json(output / "RUN_STATE.json", state)
        raise
    summary = _summary(results)
    if summary["status"] != "PASS":
        raise RuntimeError("R7-E1 summary completeness/certificate gate failed")
    atomic_write_json(output / "summary.json", summary)
    source_files = [{"path": path, "sha256": sha256_file(root / path)} for path in SOURCE_PATHS]
    manifest = {
        "schema_version": 1,
        "scope": "R7_E1_FORMAL_MAIN_EXPERIMENT",
        "status": "PASS",
        "source": {"git": source, "files": source_files},
        "preflight": preflight,
        "execution_config_path": EXECUTION_CONFIG_PATH,
        "execution_config_identity": authority["execution_config_identity"],
        "formal_ready_data_sha256": EXPECTED_DATA_SHA256,
        "r6_experiment_config_identity": EXPECTED_CONFIG_IDENTITY,
        "r6_expanded_matrix_identity": EXPECTED_MATRIX_IDENTITY,
        "case_count": 9,
        "certificate_pass_count": 9,
        "formal_scientific_runs": 9,
        "e2_e5_runs": 0,
        "invalid_or_incomplete_runs": 0,
        "case_files": [
            {"case_id": result["case_id"], "experiment_identity": result["case"]["experiment_identity"], "path": f"raw/{_raw_filename(result['case'])}", "case_result_sha256": result["case_result_sha256"]}
            for result in results
        ],
        "summary_path": "summary.json",
        "summary_sha256": summary["summary_sha256"],
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
    atomic_write_text(output / "REPORT.md", _execution_report(manifest, summary))
    inventory_paths = [Path(row["path"]) for row in manifest["case_files"]] + [
        Path("summary.json"), Path("manifest.json"), Path("RUN_STATE.json"), Path("REPORT.md")
    ]
    inventory = "".join(f"{sha256_file(output / path)}  {path.as_posix()}\n" for path in inventory_paths)
    atomic_write_text(output / "HASHES.sha256", inventory)
    replay = replay_delivery(root)
    return {"preflight": preflight, "manifest": manifest, "summary": summary, "replay": replay}
