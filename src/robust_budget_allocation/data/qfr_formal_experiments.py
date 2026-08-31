"""Deterministic R6-B experiment-matrix freeze; never solves an optimization model."""

from __future__ import annotations

from copy import deepcopy
import json
import math
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from robust_budget_allocation.io.hashing import canonical_json_sha256


FORMAL_EXPERIMENT_CONFIG_PATH = Path("configs/r6_formal_experiment_matrix_v1.json")
FORMAL_DATA_SHA256 = "3eaf0357d9d586198a8887c59b8e67ebeeb2ab8d7224923db854dca717f236f5"
MODEL_KINDS = ("M0", "M1", "M2")
E5_ALGORITHMS = ("A0", "A1_no_memory", "A1_full")


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _stable(value: Any) -> Any:
    if isinstance(value, float):
        return float(format(value, ".15g"))
    if isinstance(value, dict):
        return {key: _stable(member) for key, member in value.items()}
    if isinstance(value, list):
        return [_stable(member) for member in value]
    return value


def _case(family: str, values: Mapping[str, Any], data_sha256: str) -> dict[str, Any]:
    payload = {"family": family, "data_sha256": data_sha256, **deepcopy(dict(values))}
    payload["experiment_identity"] = canonical_json_sha256(payload)
    return payload


def _renormalize(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    total = sum(float(row["probability"]) for row in rows)
    if total <= 0:
        raise ValueError("cannot renormalize an empty or zero-probability scenario set")
    return [
        {"scenario_id": row["scenario_id"], "probability": float(row["probability"]) / total}
        for row in rows
    ]


def build_loho_folds(scenarios: list[dict[str, Any]], hurricanes: list[str]) -> list[dict[str, Any]]:
    """Build 15 leakage-free LOHO identities and conditional probabilities."""

    folds = []
    all_ids = {row["scenario_id"] for row in scenarios}
    for hurricane in hurricanes:
        test = [row for row in scenarios if hurricane in row["hurricanes"]]
        train = [row for row in scenarios if hurricane not in row["hurricanes"]]
        if not test or {row["scenario_id"] for row in train} & {row["scenario_id"] for row in test}:
            raise ValueError(f"invalid LOHO split for {hurricane}")
        if {row["scenario_id"] for row in train} | {row["scenario_id"] for row in test} != all_ids:
            raise ValueError(f"incomplete LOHO split for {hurricane}")
        if not any(row["scenario_type"] == "no_hurricane" for row in train):
            raise ValueError("no-hurricane scenario must remain in every LOHO training set")
        fold = {
            "fold_id": f"LOHO_{hurricane}",
            "held_out_hurricane": hurricane,
            "training": _renormalize(train),
            "test": _renormalize(test),
            "training_source_probability_sum": sum(float(row["probability"]) for row in train),
            "test_source_probability_sum": sum(float(row["probability"]) for row in test),
        }
        fold["fold_identity"] = canonical_json_sha256(fold)
        folds.append(_stable(fold))
    return folds


def _draw_truncated_normal(rng: Any, settings: Mapping[str, Any]) -> float:
    while True:
        value = float(rng.normal(settings["mean"], settings["standard_deviation"]))
        if float(settings["lower"]) <= value <= float(settings["upper"]):
            return value


def generate_synthetic_oos(
    formal_data: Mapping[str, Any],
    synthetic_config: Mapping[str, Any],
    seed: int,
    *,
    realizations: int | None = None,
) -> dict[str, Any]:
    """Generate the frozen joint synthetic OOS sample in serial RNG-call order."""

    configured = int(synthetic_config["realizations_per_seed"])
    count = configured if realizations is None else realizations
    if type(seed) is not int or seed not in synthetic_config["seeds"]:
        raise ValueError("seed is not in the frozen E4-B registry")
    if type(count) is not int or count <= 0 or count > configured:
        raise ValueError("realizations must be a positive integer within the frozen size")
    scenarios = list(formal_data["scenarios"])
    if len(scenarios) != 51:
        raise ValueError("E4-B requires all 51 frozen Formal scenarios")
    probabilities = np.asarray([float(row["probability"]) for row in scenarios])
    if not math.isclose(float(probabilities.sum()), 1.0, abs_tol=1e-12):
        raise ValueError("Formal scenario probabilities must sum to one")
    rng = np.random.Generator(np.random.PCG64(seed))
    perturbation = synthetic_config["demand_perturbation"]
    rows = []
    for index in range(1, count + 1):
        base_index = int(rng.choice(len(scenarios), p=probabilities))
        base = scenarios[base_index]
        z = _draw_truncated_normal(rng, perturbation)
        multiplier = 1.0 + z
        if base["scenario_type"] == "no_hurricane":
            demand = {item: 0.0 for item in formal_data["qfr_data"]["items"]}
        else:
            demand = {
                item: multiplier * float(base["formal_demand"][item])
                for item in formal_data["qfr_data"]["items"]
            }
        row = _stable({
            "realization_id": index,
            "base_scenario_id": base["scenario_id"],
            "base_scenario_type": base["scenario_type"],
            "category": int(base["category"]),
            "z": z,
            "shared_demand_multiplier": multiplier,
            "demand": demand,
            "q_availability": float(base["q_availability"]),
            "disruption": float(base["disruption"]),
        })
        row["realization_identity"] = canonical_json_sha256(row)
        rows.append(row)
    product = {
        "schema_version": 1,
        "scope": "R6_B_SYNTHETIC_OOS_DATA_NO_POLICY_OPTIMIZATION",
        "formal_ready_data_sha256": formal_data["data_sha256"],
        "seed": seed,
        "realizations": count,
        "rng": synthetic_config["rng"],
        "rows": rows,
        "scientific_runs": 0,
    }
    product = _stable(product)
    product["dataset_sha256"] = canonical_json_sha256(product)
    return product


def build_experiment_matrix(config_path: Path, repo_root: Path) -> dict[str, Any]:
    """Expand and validate the frozen R6-B matrix without any scientific solve."""

    config = _load_json(config_path)
    if config.get("scope") != "R6_B_FORMAL_EXPERIMENT_MATRIX_FREEZE_NO_SCIENTIFIC_SOLVES":
        raise ValueError("not the frozen R6-B experiment specification")
    if config.get("scientific_runs") != 0 or config.get("r7_started") is not False:
        raise ValueError("R6-B must not execute Formal science or start R7")
    data_path = repo_root / config["formal_ready_data_path"]
    formal_data = _load_json(data_path)
    if formal_data.get("data_sha256") != config.get("formal_ready_data_sha256"):
        raise ValueError("R6-B Formal-ready data identity mismatch")
    if config["formal_ready_data_sha256"] != FORMAL_DATA_SHA256:
        raise ValueError("R6-B is not bound to the independently reviewed R6-A data")

    e1 = [
        _case("E1", {"model_kind": model, "budget_ratio": budget}, FORMAL_DATA_SHA256)
        for budget in config["E1"]["budget_ratios"]
        for model in config["E1"]["models"]
    ]
    e2 = []
    for family, definition in config["E2"]["families"].items():
        for level_index, level in enumerate(definition["levels"]):
            e2.append(_case("E2", {
                "sensitivity_family": family,
                "level_index": level_index,
                "override": {definition["field"]: level},
                "model_kind": config["E2"]["model"],
                "budget_ratio": config["E2"]["budget_ratio"],
            }, FORMAL_DATA_SHA256))

    i1 = config["E3"]["interactions"]["I1_cold_chain_x_f_split"]
    e3_i1 = [
        _case("E3-I1", {
            "model_kind": "M2", "budget_ratio": 1.0,
            "vaccine_six_month_cold_chain_cost": cold,
            "phi_psi": split,
        }, FORMAL_DATA_SHA256)
        for cold in i1["vaccine_six_month_cold_chain_cost"]
        for split in i1["phi_psi"]
    ]
    i2 = config["E3"]["interactions"]["I2_f_disruption_x_r_premium"]
    base_delta = config["baseline"]["f_disruption_cat1_to_cat5"]
    e3_i2 = []
    for gamma_delta in i2["gamma_delta"]:
        mapped = [min(1.0, gamma_delta * value) for value in base_delta]
        for gamma_r in i2["gamma_R"]:
            e3_i2.append(_case("E3-I2", {
                "model_kind": "M2", "budget_ratio": 1.0,
                "gamma_delta": gamma_delta, "gamma_R": gamma_r,
                "delta_cat1_to_cat5": mapped,
                "q_survivability_cat1_to_cat5": config["baseline"]["q_survivability_cat1_to_cat5"],
                "no_hurricane_disruption": 0.0,
            }, FORMAL_DATA_SHA256))

    folds = build_loho_folds(formal_data["scenarios"], config["E4"]["historical"]["hurricanes"])
    synthetic = config["E4"]["synthetic"]
    synthetic_registry = []
    for seed in synthetic["seeds"]:
        dataset = generate_synthetic_oos(formal_data, synthetic, seed)
        synthetic_registry.append({
            "seed": seed,
            "realizations": dataset["realizations"],
            "dataset_sha256": dataset["dataset_sha256"],
            "shared_by_models": list(MODEL_KINDS),
        })

    e5 = [
        _case("E5", {
            "model_kind": model, "budget_ratio": budget, "algorithm": algorithm,
            "memory_phase_enabled": (
                False if algorithm == "A1_no_memory" else True if algorithm == "A1_full" else None
            ),
            "timing_repetitions": config["E5"]["timing_repetitions"],
        }, FORMAL_DATA_SHA256)
        for budget in config["E1"]["budget_ratios"]
        for model in config["E1"]["models"]
        for algorithm in config["E5"]["algorithms"]
    ]
    result = _stable({
        "schema_version": 1,
        "scope": "R6_B_EXPANDED_FORMAL_MATRIX_NO_SCIENTIFIC_SOLVES",
        "formal_ready_data_sha256": FORMAL_DATA_SHA256,
        "config_sha256": canonical_json_sha256(config),
        "E1_cases": e1,
        "E2_cases": e2,
        "E3_I1_cases": e3_i1,
        "E3_I2_cases": e3_i2,
        "E4_A_folds": folds,
        "E4_B_dataset_registry": synthetic_registry,
        "E5_cases": e5,
        "counts": {
            "E1": len(e1), "E2_families": len(config["E2"]["families"]),
            "E2_cells": len(e2), "E3_I1": len(e3_i1), "E3_I2": len(e3_i2),
            "E4_A_folds": len(folds), "E4_B_seeds": len(synthetic_registry),
            "E4_B_realizations_per_seed": synthetic["realizations_per_seed"],
            "E5_algorithm_cases": len(e5), "E5_timing_repetitions": config["E5"]["timing_repetitions"],
        },
        "scientific_runs": 0,
        "r7_started": False,
    })
    result["matrix_sha256"] = canonical_json_sha256(result)
    return result
