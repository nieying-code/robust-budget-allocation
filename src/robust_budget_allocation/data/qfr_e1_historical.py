"""Deterministic E1-Historical Rawls-15 dataset derivation; never invokes a solver."""

from __future__ import annotations

from copy import deepcopy
import json
import math
from pathlib import Path
from typing import Any

from robust_budget_allocation.data.qfr_data import QFRData
from robust_budget_allocation.data.qfr_formal import economic_scale_audit
from robust_budget_allocation.io.hashing import canonical_json_sha256, sha256_file


DATASET_KIND = "rawls_15_single_hurricane_historical"
EXPECTED_SCENARIOS = tuple(f"omega_{index:02d}" for index in range(1, 16))
EXPECTED_ITEMS = ("Water", "Seasonal Influenza Vaccine", "Crackers")
SOURCE_PATH = "configs/r6c_formal_ready_data_v2.json"
SOURCE_DATA_SHA256 = "59f4b89d8706f9af06aef46455292335b8b8b095f4a2a0ce0f700e5d219ed16f"
SOURCE_FILE_SHA256 = "eae86e57da22765cb097d168fcc76b1798f8c1417f00a5f40280cc3e47bd1e02"


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def _stable(value: Any) -> Any:
    if isinstance(value, float):
        return float(format(value, ".15g"))
    if isinstance(value, dict):
        return {key: _stable(member) for key, member in value.items()}
    if isinstance(value, list):
        return [_stable(member) for member in value]
    return value


def build_e1_historical_data(repo_root: Path) -> dict[str, Any]:
    """Condition the frozen R6-C v2 source on its 15 original single scenarios."""

    root = repo_root.resolve()
    source_path = root / SOURCE_PATH
    if sha256_file(source_path) != SOURCE_FILE_SHA256:
        raise ValueError("R6-C v2 source file identity mismatch")
    source = _load(source_path)
    if source.get("data_sha256") != SOURCE_DATA_SHA256:
        raise ValueError("R6-C v2 source data identity mismatch")
    if tuple(source["qfr_data"]["items"]) != EXPECTED_ITEMS:
        raise ValueError("frozen commodity identity mismatch")

    rows = [deepcopy(row) for row in source["scenarios"] if row["scenario_type"] == "single"]
    if tuple(row["scenario_id"] for row in rows) != EXPECTED_SCENARIOS:
        raise ValueError("Rawls single-hurricane scenario identity/order mismatch")
    if any(len(row["hurricanes"]) != 1 for row in rows):
        raise ValueError("non-single scenario contamination")
    source_probability_sum = sum(float(row["probability"]) for row in rows)
    if not math.isclose(source_probability_sum, 0.75, abs_tol=1e-12):
        raise ValueError("Rawls single-scenario source probability mass mismatch")
    for row in rows:
        row["source_probability"] = float(row["probability"])
        row["probability"] = float(row["probability"]) / source_probability_sum
        row["probability_derivation"] = "rawls_original_probability_divided_by_single_scenario_mass_0.75"

    product = deepcopy(source)
    product.pop("data_sha256", None)
    product.update({
        "schema_version": 1,
        "scope": "E1_HISTORICAL_FORMAL_READY_DATA_NO_SOLVES",
        "dataset_kind": DATASET_KIND,
        "scientific_runs": 0,
        "source_file_identity": {
            "path": SOURCE_PATH,
            "file_sha256": SOURCE_FILE_SHA256,
            "data_sha256": SOURCE_DATA_SHA256,
        },
        "scenario_counts": {"single": 15, "combined": 0, "no_hurricane": 0, "total": 15},
        "scenario_ordering": list(EXPECTED_SCENARIOS),
        "source_single_probability_sum": source_probability_sum,
        "probability_rule": "condition_frozen_Rawls_probabilities_on_single_hurricane_subset",
        "probability_sum": sum(float(row["probability"]) for row in rows),
        "scenarios": rows,
        "identity_boundary": "FORMAL_E1_HISTORICAL_ONLY_NOT_OLD_51_NOT_CARIBBEAN_NOT_E1_EXTENDED",
    })

    qfr = deepcopy(source["qfr_data"])
    qfr["scenarios"] = list(EXPECTED_SCENARIOS)
    for field in ("demand", "q_availability", "disruption"):
        qfr[field] = {scenario: deepcopy(qfr[field][scenario]) for scenario in EXPECTED_SCENARIOS}

    q_cost = product["parameters"]["q_unit_cost"]
    horizon_storage = product["parameters"]["storage_horizon_cost"]
    retention = product["parameters"]["retention"]
    shortage = product["parameters"]["shortage_cost"]
    reference_demand = {
        item: sum(float(row["probability"]) * float(row["formal_demand"][item]) for row in rows)
        for item in EXPECTED_ITEMS
    }
    flexible_capacity = {
        item: max(float(row["formal_demand"][item]) for row in rows)
        for item in EXPECTED_ITEMS
    }
    components = {
        item: (float(q_cost[item]) + float(horizon_storage[item]))
        * reference_demand[item] / float(retention[item])
        for item in EXPECTED_ITEMS
    }
    reference_budget = sum(components.values())
    qfr["budget"] = reference_budget
    qfr["flexible_capacity"] = deepcopy(flexible_capacity)
    data = QFRData.from_dict(qfr)
    data.validate()

    scenario_identity_payload = [
        {
            "scenario_id": row["scenario_id"],
            "hurricanes": row["hurricanes"],
            "category": row["category"],
            "source_probability": row["source_probability"],
            "conditional_probability": row["probability"],
            "formal_demand": row["formal_demand"],
            "q_availability": row["q_availability"],
            "disruption": row["disruption"],
        }
        for row in rows
    ]
    parameter_identity_payload = {
        "parameters": product["parameters"],
        "items": list(EXPECTED_ITEMS),
        "model_mechanism_validation": product["model_mechanism_validation"],
    }
    product.update({
        "qfr_data": qfr,
        "reference_demand": reference_demand,
        "reference_demand_rule": "conditional_probability_weighted_mean_over_15_Rawls_single_hurricane_scenarios",
        "reference_budget_rule": "sum_i((cQ_i+h_i*tau)*Dref_i/a_i)",
        "reference_budget_components": components,
        "reference_budget": reference_budget,
        "reference_budget_regeneration": "SAME_FROZEN_FORMULA_MECHANICALLY_RECOMPUTED_ON_CONDITIONAL_RAWLS_15_DATASET",
        "flexible_capacity": flexible_capacity,
        "flexible_capacity_rule": "max_transformed_demand_over_15_Rawls_single_hurricane_scenarios",
        "old_51_reference_budget": float(source["reference_budget"]),
        "old_51_flexible_capacity": deepcopy(source["flexible_capacity"]),
        "reference_budget_difference_from_old_51": reference_budget - float(source["reference_budget"]),
        "flexible_capacity_difference_from_old_51": {
            item: flexible_capacity[item] - float(source["flexible_capacity"][item]) for item in EXPECTED_ITEMS
        },
        "economic_scale_audit": economic_scale_audit(rows, q_cost, horizon_storage, retention, shortage),
        "scenario_sha256": data.scenario_sha256,
        "scenario_set_sha256": canonical_json_sha256(scenario_identity_payload),
        "parameter_sha256": canonical_json_sha256(parameter_identity_payload),
    })
    product = _stable(product)
    product["data_sha256"] = canonical_json_sha256(product)
    return product
