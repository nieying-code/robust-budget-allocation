"""Deterministic R6-C scientific re-freeze builders; never invokes a solver."""

from __future__ import annotations

from copy import deepcopy
import json
import math
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from robust_budget_allocation.data.qfr_data import QFRData, RELIABILITY_LEVELS
from robust_budget_allocation.data.qfr_formal import economic_scale_audit
from robust_budget_allocation.io.hashing import canonical_json_sha256, sha256_file


ACTIVE_ITEMS = ("Water", "Seasonal Influenza Vaccine", "Crackers")
MODEL_KINDS = ("M0", "M1", "M2")
E5_ALGORITHMS = ("A0", "A1_no_memory", "A1_full")
REVISION_SCOPE = "R6_C_SCIENTIFIC_REVISION_REFREEZE_NO_SCIENTIFIC_SOLVES"
MATRIX_SCOPE = "R6_C_REVISED_FORMAL_EXPERIMENT_MATRIX_FREEZE_NO_SCIENTIFIC_SOLVES"


def _load(path: Path) -> dict[str, Any]:
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


def _close(actual: float, expected: float, label: str, tolerance: float = 1e-12) -> None:
    if not math.isclose(float(actual), float(expected), rel_tol=0.0, abs_tol=tolerance):
        raise ValueError(f"{label} mismatch: {actual!r} != {expected!r}")


def _validate_revision(revision: Mapping[str, Any]) -> None:
    if revision.get("scope") != REVISION_SCOPE or revision.get("stage") != "R6":
        raise ValueError("not the registered R6-C scientific revision")
    if revision.get("scientific_runs") != 0:
        raise ValueError("R6-C must have zero scientific runs")
    scenarios = revision["scenario_rules"]
    if scenarios["counts"] != {"single": 15, "combined": 35, "no_hurricane": 1, "total": 51}:
        raise ValueError("R6-C scenario counts changed")
    if scenarios["q_survivability_cat1_to_cat5"] != [0.9, 0.85, 0.8, 0.75, 0.7]:
        raise ValueError("R6-C rhoQ mapping mismatch")
    if scenarios["f_disruption_cat1_to_cat5"] != [0.1, 0.3, 0.6, 0.8, 1.0]:
        raise ValueError("R6-C delta mapping mismatch")
    if revision["reliability"]["eta"] != [0.2, 0.5, 0.8]:
        raise ValueError("R6-C eta tiers mismatch")
    if revision["reliability"]["premium_ratios"] != [0.0, 0.1, 0.25]:
        raise ValueError("R6-C reliability premiums mismatch")
    pricing = revision["pricing"]
    if (pricing["phi"], pricing["psi"], pricing["shortage_beta"]) != (0.2, 0.85, 4.0):
        raise ValueError("R6-C baseline pricing mismatch")
    if pricing["shortage_priority_lambda"] != dict.fromkeys(ACTIVE_ITEMS, 1.0):
        raise ValueError("R6-C neutral lambda baseline mismatch")


def build_revised_formal_data(revision_path: Path, repo_root: Path) -> dict[str, Any]:
    """Build the revised Formal-ready product from immutable old source evidence."""

    revision = _load(revision_path)
    _validate_revision(revision)
    old = revision["old_formal_source"]
    source_config_path = repo_root / old["config_path"]
    old_ready_path = repo_root / old["formal_ready_path"]
    if sha256_file(source_config_path) != old["config_file_sha256"]:
        raise ValueError("old R6 source config file identity mismatch")
    if sha256_file(old_ready_path) != old["formal_ready_file_sha256"]:
        raise ValueError("old R6 Formal-ready file identity mismatch")
    source = _load(source_config_path)
    prior = _load(old_ready_path)
    if prior.get("data_sha256") != old["data_sha256"]:
        raise ValueError("old R6 data identity mismatch")
    if tuple(prior["qfr_data"]["items"]) != ACTIVE_ITEMS or len(prior["scenarios"]) != 51:
        raise ValueError("old R6 source structure mismatch")

    product = deepcopy(prior)
    product.pop("data_sha256", None)
    product["schema_version"] = 2
    product["scope"] = "R6_C_FORMAL_READY_DATA_NO_SCIENTIFIC_SOLVES"
    product["stage"] = "R6-C"
    product["scientific_runs"] = 0
    product["revision_config_sha256"] = canonical_json_sha256(revision)
    product["old_formal_identity"] = deepcopy(old)
    product["identity_boundary"] = "REVISED_FORMAL_V2_SUPERSEDES_OLD_FORMAL_FOR_FUTURE_EXECUTION_ONLY"

    rho = [1.0, *revision["scenario_rules"]["q_survivability_cat1_to_cat5"]]
    delta = [0.0, *revision["scenario_rules"]["f_disruption_cat1_to_cat5"]]
    for row in product["scenarios"]:
        category = int(row["category"])
        row["q_availability"] = rho[category]
        row["disruption"] = delta[category]
        if row["scenario_type"] == "no_hurricane":
            if any(float(value) != 0.0 for value in row["formal_demand"].values()):
                raise ValueError("no-hurricane demand must remain zero")
            if (category, row["q_availability"], row["disruption"]) != (0, 1.0, 0.0):
                raise ValueError("no-hurricane supply state mismatch")

    q_cost = product["parameters"]["q_unit_cost"]
    horizon_storage = product["parameters"]["storage_horizon_cost"]
    retention = product["parameters"]["retention"]
    beta = float(revision["pricing"]["shortage_beta"])
    priorities = revision["pricing"]["shortage_priority_lambda"]
    shortage = {item: beta * float(priorities[item]) * float(q_cost[item]) for item in ACTIVE_ITEMS}
    eta = list(revision["reliability"]["eta"])
    premiums = list(revision["reliability"]["premium_ratios"])
    product["parameters"]["shortage_cost"] = shortage
    product["parameters"]["shortage_beta"] = beta
    product["parameters"]["shortage_priority_lambda"] = deepcopy(priorities)
    product["parameters"]["reliability_mitigation"] = eta
    product["parameters"]["reliability_cost_ratios"] = premiums
    product["parameters"]["q_survivability_cat1_to_cat5"] = rho[1:]
    product["parameters"]["f_disruption_cat1_to_cat5"] = delta[1:]

    reference_demand = {
        item: sum(float(row["probability"]) * float(row["formal_demand"][item]) for row in product["scenarios"])
        for item in ACTIVE_ITEMS
    }
    fbar = {
        item: max(float(row["formal_demand"][item]) for row in product["scenarios"])
        for item in ACTIVE_ITEMS
    }
    components = {
        item: (float(q_cost[item]) + float(horizon_storage[item])) * reference_demand[item] / float(retention[item])
        for item in ACTIVE_ITEMS
    }
    reference_budget = sum(components.values())
    product["reference_demand"] = reference_demand
    product["flexible_capacity"] = fbar
    product["reference_budget_components"] = components
    product["reference_budget"] = reference_budget
    product["reference_budget_regeneration"] = "RECOMPUTED_FROM_REVISED_FREEZE_INPUTS_NOT_CARRIED_FORWARD"
    product["economic_scale_audit"] = economic_scale_audit(
        product["scenarios"], q_cost, horizon_storage, retention, shortage
    )

    qfr = product["qfr_data"]
    qfr["budget"] = reference_budget
    qfr["flexible_capacity"] = deepcopy(fbar)
    qfr["shortage_cost"] = deepcopy(shortage)
    qfr["reliability_mitigation"] = {
        item: {str(level): eta[level] for level in RELIABILITY_LEVELS} for item in ACTIVE_ITEMS
    }
    qfr["reliability_cost"] = {
        item: {str(level): premiums[level] * float(q_cost[item]) for level in RELIABILITY_LEVELS}
        for item in ACTIVE_ITEMS
    }
    qfr["q_availability"] = {
        row["scenario_id"]: {item: row["q_availability"] for item in ACTIVE_ITEMS}
        for row in product["scenarios"]
    }
    qfr["disruption"] = {
        row["scenario_id"]: {item: row["disruption"] for item in ACTIVE_ITEMS}
        for row in product["scenarios"]
    }
    product["scenario_sha256"] = QFRData.from_dict(qfr).scenario_sha256
    product["source_scenario_sha256"] = canonical_json_sha256({
        "hurricanes": source["hurricanes"], "scenarios": source["scenarios"]
    })
    product["provenance_classes"] = deepcopy(revision["provenance_classes"])
    product["model_mechanism_validation"] = {
        "availability_rule": "1-(1-eta_r)*delta_omega",
        "M1_levels": [0], "M2_levels": [0, 1, 2], "R0_premium_ratio": 0.0,
    }
    product = _stable(product)
    product["data_sha256"] = canonical_json_sha256(product)
    return product


def _physical_baseline(config: Mapping[str, Any]) -> dict[str, Any]:
    baseline = config["baseline"]
    return {
        "model_kind": "M2", "budget_ratio": 1.0,
        "vaccine_six_month_cold_chain_cost": baseline["vaccine_six_month_cold_chain_cost"],
        "crackers_retention": baseline["crackers_retention"],
        "phi_psi": [baseline["phi"], baseline["psi"]],
        "reliability_premium_ratios": baseline["reliability_premium_ratios"],
        "eta": baseline["eta"],
        "delta_cat1_to_cat5": baseline["f_disruption_cat1_to_cat5"],
        "beta": baseline["shortage_beta"],
        "lambda": [baseline["shortage_priority"][item] for item in ACTIVE_ITEMS],
    }


def _physical_identity(values: Mapping[str, Any], data_sha256: str) -> str:
    return canonical_json_sha256({"data_sha256": data_sha256, **_stable(deepcopy(dict(values)))})


def _logical_case(family: str, membership: str, physical: Mapping[str, Any], data_sha256: str) -> dict[str, Any]:
    row = {
        "family": family, "logical_membership": membership,
        "physical_configuration": _stable(deepcopy(dict(physical))),
        "physical_configuration_identity": _physical_identity(physical, data_sha256),
        "data_sha256": data_sha256,
    }
    row["logical_configuration_identity"] = canonical_json_sha256(row)
    return row


def _renormalize(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    total = sum(float(row["probability"]) for row in rows)
    return [{"scenario_id": row["scenario_id"], "probability": float(row["probability"]) / total} for row in rows]


def build_loho_folds(scenarios: list[dict[str, Any]], hurricanes: list[str]) -> list[dict[str, Any]]:
    folds = []
    all_ids = {row["scenario_id"] for row in scenarios}
    for hurricane in hurricanes:
        test = [row for row in scenarios if hurricane in row["hurricanes"]]
        train = [row for row in scenarios if hurricane not in row["hurricanes"]]
        if not test or ({row["scenario_id"] for row in train} | {row["scenario_id"] for row in test}) != all_ids:
            raise ValueError(f"invalid LOHO split for {hurricane}")
        fold = {"fold_id": f"LOHO_{hurricane}", "held_out_hurricane": hurricane,
                "training": _renormalize(train), "test": _renormalize(test)}
        fold["fold_identity"] = canonical_json_sha256(fold)
        folds.append(_stable(fold))
    return folds


def _draw_truncated_normal(rng: Any, settings: Mapping[str, Any]) -> float:
    while True:
        value = float(rng.normal(settings["mean"], settings["standard_deviation"]))
        if float(settings["lower"]) <= value <= float(settings["upper"]):
            return value


def generate_synthetic_oos(formal: Mapping[str, Any], config: Mapping[str, Any], seed: int, *, realizations: int | None = None) -> dict[str, Any]:
    count = int(config["realizations_per_seed"]) if realizations is None else realizations
    if type(seed) is not int or seed not in config["seeds"] or type(count) is not int or count <= 0:
        raise ValueError("invalid frozen synthetic registry request")
    scenarios = list(formal["scenarios"])
    probabilities = np.asarray([float(row["probability"]) for row in scenarios])
    rng = np.random.Generator(np.random.PCG64(seed))
    rows = []
    for index in range(1, count + 1):
        base = scenarios[int(rng.choice(len(scenarios), p=probabilities))]
        z = _draw_truncated_normal(rng, config["demand_perturbation"])
        multiplier = 1.0 + z
        demand = ({item: 0.0 for item in ACTIVE_ITEMS} if base["scenario_type"] == "no_hurricane" else
                  {item: multiplier * float(base["formal_demand"][item]) for item in ACTIVE_ITEMS})
        row = _stable({"realization_id": index, "base_scenario_id": base["scenario_id"],
                       "base_scenario_type": base["scenario_type"], "category": base["category"],
                       "z": z, "shared_demand_multiplier": multiplier, "demand": demand,
                       "q_availability": base["q_availability"], "disruption": base["disruption"]})
        if base["scenario_type"] == "no_hurricane" and (set(demand.values()) != {0.0} or (row["q_availability"], row["disruption"]) != (1.0, 0.0)):
            raise ValueError("synthetic no-hurricane rule violated")
        row["realization_identity"] = canonical_json_sha256(row)
        rows.append(row)
    product = _stable({"schema_version": 2, "scope": "R6_C_SYNTHETIC_OOS_NO_POLICY_OPTIMIZATION",
                       "formal_ready_data_sha256": formal["data_sha256"], "seed": seed,
                       "realizations": count, "rows": rows, "scientific_runs": 0})
    product["dataset_sha256"] = canonical_json_sha256(product)
    return product


def build_revised_experiment_matrix(config_path: Path, repo_root: Path) -> dict[str, Any]:
    config = _load(config_path)
    if config.get("scope") != MATRIX_SCOPE or config.get("scientific_runs") != 0 or config.get("r7_started") is not False:
        raise ValueError("not the registered zero-run R6-C matrix")
    formal = _load(repo_root / config["formal_ready_data_path"])
    data_sha = formal.get("data_sha256")
    if data_sha != config.get("formal_ready_data_sha256"):
        raise ValueError("R6-C matrix/data identity mismatch")
    baseline = _physical_baseline(config)

    e1 = []
    for budget in config["E1"]["budget_ratios"]:
        for model in config["E1"]["models"]:
            physical = deepcopy(baseline)
            physical.update({"model_kind": model, "budget_ratio": budget})
            e1.append(_logical_case("E1", f"{model}@B{budget:.2f}", physical, data_sha))

    e2 = []
    for family, definition in config["E2"]["families"].items():
        for index, level in enumerate(definition["levels"]):
            physical = deepcopy(baseline)
            field = definition["field"]
            if field == "gamma_R":
                physical["reliability_premium_ratios"] = [0.0, 0.1 * level, 0.25 * level]
            elif field == "gamma_delta":
                physical["delta_cat1_to_cat5"] = definition["mapped_levels"][index]
            else:
                physical[field] = level
            e2.append(_logical_case("E2", f"{family}:level_{index}", physical, data_sha))

    e3_i1 = []
    values = config["E3"]["interactions"]["I1_cold_chain_x_f_split"]
    for cold in values["vaccine_six_month_cold_chain_cost"]:
        for split in values["phi_psi"]:
            physical = deepcopy(baseline)
            physical.update({"vaccine_six_month_cold_chain_cost": cold, "phi_psi": split})
            e3_i1.append(_logical_case("E3-I1", f"cold_{cold}:split_{split[0]}_{split[1]}", physical, data_sha))
    e3_i2 = []
    values = config["E3"]["interactions"]["I2_f_disruption_x_r_premium"]
    for gamma_delta in values["gamma_delta"]:
        mapped = [min(1.0, gamma_delta * value) for value in baseline["delta_cat1_to_cat5"]]
        for gamma_r in values["gamma_R"]:
            physical = deepcopy(baseline)
            physical.update({"delta_cat1_to_cat5": mapped,
                             "reliability_premium_ratios": [0.0, 0.1 * gamma_r, 0.25 * gamma_r]})
            e3_i2.append(_logical_case("E3-I2", f"delta_{gamma_delta}:premium_{gamma_r}", physical, data_sha))

    folds = build_loho_folds(formal["scenarios"], config["E4"]["historical"]["hurricanes"])
    synthetic = config["E4"]["synthetic"]
    registry = []
    for seed in synthetic["seeds"]:
        dataset = generate_synthetic_oos(formal, synthetic, seed)
        registry.append({"seed": seed, "realizations": dataset["realizations"],
                         "dataset_sha256": dataset["dataset_sha256"], "shared_by_models": list(MODEL_KINDS)})

    e5 = []
    for e1_case in e1:
        for algorithm in config["E5"]["algorithms"]:
            row = {"family": "E5", "source_e1_physical_configuration_identity": e1_case["physical_configuration_identity"],
                   "model_kind": e1_case["physical_configuration"]["model_kind"],
                   "budget_ratio": e1_case["physical_configuration"]["budget_ratio"],
                   "algorithm": algorithm, "timing_repetitions": config["E5"]["timing_repetitions"],
                   "actual_timing_runs": 0, "data_sha256": data_sha}
            row["experiment_identity"] = canonical_json_sha256(row)
            e5.append(row)

    e2_unique = len({row["physical_configuration_identity"] for row in e2})
    e3_all = e3_i1 + e3_i2
    e3_unique = len({row["physical_configuration_identity"] for row in e3_all})
    all_science = e1 + e2 + e3_all
    registry_ids = {row["physical_configuration_identity"] for row in all_science}
    result = _stable({"schema_version": 2, "scope": "R6_C_REVISED_EXPANDED_FORMAL_MATRIX_NO_SCIENTIFIC_SOLVES",
        "formal_ready_data_sha256": data_sha, "scenario_sha256": formal["scenario_sha256"],
        "config_sha256": canonical_json_sha256(config), "E1_cases": e1, "E2_logical_cases": e2,
        "E3_I1_logical_cases": e3_i1, "E3_I2_logical_cases": e3_i2,
        "E4_A_folds": folds, "E4_B_dataset_registry": registry, "E5_algorithm_cases": e5,
        "deduplication": {"rule": "ONE_SOLVE_PER_PHYSICAL_CONFIGURATION_IDENTITY_WITH_ALL_LOGICAL_MEMBERSHIPS_RETAINED",
            "E2_logical": len(e2), "E2_unique_physical": e2_unique, "E2_baseline_dedup_count": len(e2)-e2_unique,
            "E3_logical": len(e3_all), "E3_unique_physical": e3_unique, "E3_baseline_dedup_count": len(e3_all)-e3_unique,
            "E1_E2_E3_logical": len(all_science), "E1_E2_E3_unique_physical": len(registry_ids)},
        "counts": {"E1": len(e1), "E2_families": len(config["E2"]["families"]), "E2_logical": len(e2),
            "E2_unique_physical": e2_unique, "E3_I1": len(e3_i1), "E3_I2": len(e3_i2),
            "E3_unique_physical": e3_unique, "E4_A_folds": len(folds), "E4_B_seeds": len(registry),
            "E4_B_realizations_per_seed": synthetic["realizations_per_seed"], "E5_algorithm_cases": len(e5),
            "E5_timing_repetitions": config["E5"]["timing_repetitions"], "E5_planned_timing_runs": 81},
        "execution_counts": {"E1": 0, "E2": 0, "E3": 0, "E4": 0, "E5": 0, "formal_scientific_runs": 0},
        "r7_started": False})
    result["matrix_sha256"] = canonical_json_sha256(result)
    return result
