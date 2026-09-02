"""Build the temporary 24-scenario Q-F-R availability diagnostic."""

from __future__ import annotations

import csv
from copy import deepcopy
import json
import math
from pathlib import Path
from typing import Any

from robust_budget_allocation.data.qfr_data import QFRData, RELIABILITY_LEVELS
from robust_budget_allocation.io.hashing import canonical_json_sha256, sha256_file


ITEMS = ("Water", "Seasonal Influenza Vaccine", "Crackers")
MODELS = ("M0", "M1", "M2")
BUDGET_RATIOS = (0.75, 1.0, 1.25)


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def _load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _close(actual: float, expected: float, label: str) -> None:
    if not math.isclose(actual, expected, rel_tol=0.0, abs_tol=1e-12):
        raise ValueError(f"{label} mismatch: {actual!r} != {expected!r}")


def build_diagnostic_authority(repo_root: Path) -> dict[str, Any]:
    root = repo_root.resolve()
    config_path = root / "configs/qfr24_availability_diagnostic_v1.json"
    input_path = root / "data/r6_rawls24/unified_hurricane_input.csv"
    demand_path = root / "data/r6_rawls24/unified_rawls_demand.csv"
    manifest_path = root / "data/r6_rawls24/provenance_manifest.json"
    formal_path = root / "configs/r6c_formal_ready_data_v2.json"
    config = _load_json(config_path)
    manifest = _load_json(manifest_path)
    formal = _load_json(formal_path)
    inputs = _load_csv(input_path)
    raw_demands = _load_csv(demand_path)

    if config["scope"] != "TEMPORARY_QFR_24SCENARIO_AVAILABILITY_DIAGNOSTIC":
        raise ValueError("wrong diagnostic scope")
    if config["dataset_identity"] != manifest["dataset_identity"]:
        raise ValueError("Rawls24 dataset identity mismatch")
    if len(inputs) != 24 or len(raw_demands) != 24:
        raise ValueError("diagnostic requires exactly 24 scenarios")
    if tuple(config["models"]) != MODELS or tuple(config["budget_ratios"]) != BUDGET_RATIOS:
        raise ValueError("diagnostic matrix must contain exactly 9 cases")
    _close(float(config["scenario_weight"]), 1.0 / 24.0, "uniform reference weight")
    if config["scenario_weight_role"] != "B_REF_NEUTRAL_NORMALIZATION_ONLY_NOT_EMPIRICAL_PROBABILITY":
        raise ValueError("uniform weights must be limited to B_ref normalization")

    qfr = formal["qfr_data"]
    if tuple(qfr["items"]) != ITEMS:
        raise ValueError("Formal commodity identity mismatch")
    parameters = formal["parameters"]
    _close(parameters["reservation_cost"]["Water"] / parameters["q_unit_cost"]["Water"], 0.20, "phi")
    _close(parameters["exercise_cost"]["Water"] / parameters["q_unit_cost"]["Water"], 0.85, "psi")
    if parameters["reliability_cost_ratios"] != [0.0, 0.1, 0.25]:
        raise ValueError("reliability premiums changed")
    if parameters["shortage_beta"] != 4.0 or set(parameters["shortage_priority_lambda"].values()) != {1.0}:
        raise ValueError("shortage economics changed")

    input_by_id = {row["scenario_id"]: row for row in inputs}
    raw_by_id = {row["scenario_id"]: row for row in raw_demands}
    scenario_ids = tuple(row["scenario_id"] for row in inputs)
    if scenario_ids != tuple(raw_by_id) or scenario_ids != tuple(f"h{i:02d}" for i in range(1, 25)):
        raise ValueError("scenario ordering mismatch")
    demand: dict[str, dict[str, float]] = {}
    metadata: dict[str, dict[str, Any]] = {}
    rho_q: dict[str, dict[str, float]] = {}
    disruption: dict[str, dict[str, float]] = {}
    q_schedule = [float(value) for value in config["q_availability_cat1_to_cat5"]]
    severity = [float(value) for value in config["severity_L_cat1_to_cat5"]]
    e_f = [float(config["f_exposure"][f"R{level}"]) for level in RELIABILITY_LEVELS]
    mitigation = [0.0, 1.0 - e_f[1] / e_f[0], 1.0 - e_f[2] / e_f[0]]

    for scenario in scenario_ids:
        source = input_by_id[scenario]
        row = raw_by_id[scenario]
        category = int(source["category"])
        demand[scenario] = {
            "Water": float(row["water_unified"]),
            "Seasonal Influenza Vaccine": (140.0 / 13.916) * float(row["medical_unified"]),
            "Crackers": 14.0 * float(row["food_unified"]),
        }
        metadata[scenario] = {
            "hurricane_name": source["hurricane_name"],
            "year": int(source["year"]),
            "category": category,
            "evidence_status": source["evidence_status"],
        }
        rho_q[scenario] = dict.fromkeys(ITEMS, q_schedule[category - 1])
        disruption[scenario] = dict.fromkeys(ITEMS, e_f[0] * severity[category - 1])

    for category in range(1, 6):
        for level in RELIABILITY_LEVELS:
            actual = 1.0 - (1.0 - mitigation[level]) * e_f[0] * severity[category - 1]
            expected = float(config["expected_f_availability"][f"R{level}"][category - 1])
            _close(actual, expected, f"F availability Cat{category}/R{level}")

    fbar = {item: max(demand[scenario][item] for scenario in scenario_ids) for item in ITEMS}
    reference_demand = {
        item: sum(demand[scenario][item] for scenario in scenario_ids) / 24.0 for item in ITEMS
    }
    q_cost = {item: float(qfr["q_unit_cost"][item]) for item in ITEMS}
    storage_horizon = {item: float(parameters["storage_horizon_cost"][item]) for item in ITEMS}
    retention = {item: float(qfr["retention"][item]) for item in ITEMS}
    components = {
        item: (q_cost[item] + storage_horizon[item]) * reference_demand[item] / retention[item]
        for item in ITEMS
    }
    b_ref = sum(components.values())
    base_payload = deepcopy(qfr)
    base_payload.update({
        "scenarios": list(scenario_ids),
        "budget": b_ref,
        "flexible_capacity": fbar,
        "demand": demand,
        "q_availability": rho_q,
        "disruption": disruption,
        "reliability_mitigation": {
            item: {str(level): mitigation[level] for level in RELIABILITY_LEVELS} for item in ITEMS
        },
    })
    data = QFRData.from_dict(base_payload)
    data.validate()
    authority = {
        "scope": config["scope"],
        "scientific_status": config["scientific_status"],
        "source_files": {
            path.relative_to(root).as_posix(): sha256_file(path)
            for path in (config_path, input_path, demand_path, manifest_path, formal_path)
        },
        "scenario_count": 24,
        "scenario_ids": list(scenario_ids),
        "metadata": metadata,
        "reference_weight": 1.0 / 24.0,
        "reference_weight_role": config["scenario_weight_role"],
        "reference_demand": reference_demand,
        "reference_budget_components": components,
        "B_ref": b_ref,
        "F_bar": fbar,
        "q_availability_cat1_to_cat5": q_schedule,
        "severity_L_cat1_to_cat5": severity,
        "f_exposure_R0_R1_R2": e_f,
        "model_equivalent_reliability_mitigation": mitigation,
        "f_availability": config["expected_f_availability"],
        "budget_ratios": list(BUDGET_RATIOS),
        "models": list(MODELS),
        "base_qfr_data": data.to_dict(),
    }
    authority["authority_sha256"] = canonical_json_sha256(authority)
    return authority


def case_data(authority: dict[str, Any], budget_ratio: float) -> QFRData:
    if float(budget_ratio) not in BUDGET_RATIOS:
        raise ValueError("unregistered diagnostic budget ratio")
    payload = deepcopy(authority["base_qfr_data"])
    payload["budget"] = float(authority["B_ref"]) * float(budget_ratio)
    data = QFRData.from_dict(payload)
    data.validate()
    return data
