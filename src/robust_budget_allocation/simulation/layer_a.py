"""Layer A constrained LHS, neutral fixture, validation, and result adapters."""

from __future__ import annotations

from copy import deepcopy
import csv
from decimal import Decimal, localcontext
import io
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from robust_budget_allocation.data.qfr_data import QFRData
from robust_budget_allocation.io.hashing import canonical_json_sha256, sha256_file


PARAMETERS = (
    "rho_Q1", "rho_Q2", "rho_Q3", "rho_Q4", "rho_Q5",
    "rho_F1", "rho_F2", "rho_F3", "rho_F4", "rho_F5",
    "eta_1", "eta_2", "phi", "psi", "c_R1_ratio", "c_R2_ratio",
)
ITEMS = ("Water", "Seasonal Influenza Vaccine", "Crackers")
POLICY_LABELS = ("P1", "P2", "P3a", "P3b", "P4", "P5")


def load_config(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    validate_config(value)
    return value


def validate_config(config: Mapping[str, Any]) -> None:
    if config.get("scope") not in {
        "QFR_MECHANISM_SIMULATION_LAYER_A_N1000",
        "QFR_MECHANISM_SIMULATION_LAYER_A_RAWLS24_N1000",
        "QFR_COMMODITY_HETEROGENEITY_LAYER_B_RAWLS24_N1000",
    }:
        raise ValueError("wrong Layer A scope")
    if config.get("sample_size") != 1000 or type(config.get("seed")) is not int:
        raise ValueError("Layer A requires N=1000 and an integer seed")
    if config.get("model_kind") != "M2" or config.get("algorithm_kind") != "A1_full":
        raise ValueError("Layer A requires production M2+A1_full")
    bounds = config.get("bounds")
    if not isinstance(bounds, Mapping) or set(bounds) != set(PARAMETERS):
        raise ValueError("parameter bounds are incomplete")
    for name in PARAMETERS:
        pair = bounds[name]
        if not isinstance(pair, list) or len(pair) != 2:
            raise ValueError(f"invalid bounds for {name}")
        low, high = map(float, pair)
        if not math.isfinite(low) or not math.isfinite(high) or low >= high:
            raise ValueError(f"invalid bounds for {name}")
    if float(config.get("policy_tolerance", 0)) <= 0:
        raise ValueError("policy tolerance must be positive")


def _lhs_values(rng: np.random.Generator, n: int, low: float, high: float) -> list[float]:
    unit = (np.arange(n, dtype=float) + rng.random(n)) / n
    values = low + (high - low) * unit
    rng.shuffle(values)
    return [float(value) for value in values]


def _assign_below(
    rng: np.random.Generator, upper: Sequence[float], values: Sequence[float]
) -> list[float]:
    ordered_values = sorted(float(value) for value in values)
    pool: list[float] = []
    cursor = 0
    result = [0.0] * len(upper)
    for row in sorted(range(len(upper)), key=lambda idx: (upper[idx], idx)):
        while cursor < len(ordered_values) and ordered_values[cursor] <= upper[row]:
            pool.append(ordered_values[cursor])
            cursor += 1
        if not pool:
            raise ValueError("constrained LHS matching failed for descending curve")
        result[row] = pool.pop(int(rng.integers(len(pool))))
    if cursor != len(ordered_values) or pool:
        raise ValueError("constrained LHS matching left unmatched curve values")
    return result


def _assign_above(
    rng: np.random.Generator, lower: Sequence[float], values: Sequence[float]
) -> list[float]:
    ordered_values = sorted((float(value) for value in values), reverse=True)
    pool: list[float] = []
    cursor = 0
    result = [0.0] * len(lower)
    for row in sorted(range(len(lower)), key=lambda idx: (-lower[idx], idx)):
        while cursor < len(ordered_values) and ordered_values[cursor] >= lower[row]:
            pool.append(ordered_values[cursor])
            cursor += 1
        if not pool:
            raise ValueError("constrained LHS matching failed for ordered pair")
        result[row] = pool.pop(int(rng.integers(len(pool))))
    if cursor != len(ordered_values) or pool:
        raise ValueError("constrained LHS matching left unmatched ordered values")
    return result


def _curve(
    rng: np.random.Generator,
    n: int,
    names: Sequence[str],
    bounds: Mapping[str, Sequence[float]],
) -> dict[str, list[float]]:
    columns = {
        name: _lhs_values(rng, n, float(bounds[name][0]), float(bounds[name][1]))
        for name in names
    }
    assigned = {names[0]: columns[names[0]]}
    for previous, name in zip(names, names[1:], strict=False):
        assigned[name] = _assign_below(rng, assigned[previous], columns[name])
    return assigned


def generate_samples(config: Mapping[str, Any]) -> list[dict[str, Any]]:
    validate_config(config)
    n, seed, bounds = int(config["sample_size"]), int(config["seed"]), config["bounds"]
    rng = np.random.Generator(np.random.PCG64(seed))
    q = _curve(rng, n, [f"rho_Q{i}" for i in range(1, 6)], bounds)
    f = _curve(rng, n, [f"rho_F{i}" for i in range(1, 6)], bounds)
    eta1 = _lhs_values(rng, n, *map(float, bounds["eta_1"]))
    eta2 = _assign_above(
        rng, [value + 0.05 for value in eta1],
        _lhs_values(rng, n, *map(float, bounds["eta_2"])),
    )
    premium1 = _lhs_values(rng, n, *map(float, bounds["c_R1_ratio"]))
    premium2 = _assign_above(
        rng, [value + 0.05 for value in premium1],
        _lhs_values(rng, n, *map(float, bounds["c_R2_ratio"])),
    )
    phi = _lhs_values(rng, n, *map(float, bounds["phi"]))
    psi = _lhs_values(rng, n, *map(float, bounds["psi"]))
    rows = []
    for index in range(n):
        row: dict[str, Any] = {
            "simulation_id": f"LA-{index + 1:04d}",
            "sample_index": index + 1,
            "simulation_seed": seed,
        }
        for name in [*q, *f]:
            row[name] = q[name][index] if name in q else f[name][index]
        row.update({
            "eta_1": eta1[index], "eta_2": eta2[index],
            "phi": phi[index], "psi": psi[index],
            "c_R1_ratio": premium1[index], "c_R2_ratio": premium2[index],
        })
        row["input_sha256"] = canonical_json_sha256(row)
        rows.append(row)
    return rows


def validate_samples(rows: Sequence[Mapping[str, Any]], config: Mapping[str, Any]) -> dict[str, Any]:
    validate_config(config)
    n, bounds = int(config["sample_size"]), config["bounds"]
    checks: dict[str, bool] = {
        "sample_count_1000": len(rows) == n,
        "unique_simulation_ids": len({row.get("simulation_id") for row in rows}) == n,
        "unique_parameter_vectors": len({tuple(float(row[name]) for name in PARAMETERS) for row in rows}) == n,
        "no_nan": True, "no_inf": True, "all_bounds": True,
        "q_monotonicity": True, "f_monotonicity": True,
        "eta_ordering_and_gap": True, "premium_ordering_and_gap": True,
        "input_hashes": True, "lhs_stratum_coverage": True,
    }
    for index, row in enumerate(rows, 1):
        if row.get("simulation_id") != f"LA-{index:04d}" or row.get("sample_index") != index:
            checks["unique_simulation_ids"] = False
        for name in PARAMETERS:
            value = float(row[name])
            checks["no_nan"] &= not math.isnan(value)
            checks["no_inf"] &= math.isfinite(value)
            checks["all_bounds"] &= float(bounds[name][0]) <= value <= float(bounds[name][1])
        checks["q_monotonicity"] &= all(float(row[f"rho_Q{i}"]) >= float(row[f"rho_Q{i+1}"]) for i in range(1, 5))
        checks["f_monotonicity"] &= all(float(row[f"rho_F{i}"]) >= float(row[f"rho_F{i+1}"]) for i in range(1, 5))
        checks["eta_ordering_and_gap"] &= float(row["eta_2"]) - float(row["eta_1"]) >= 0.05 - 1e-14
        checks["premium_ordering_and_gap"] &= float(row["c_R2_ratio"]) - float(row["c_R1_ratio"]) >= 0.05 - 1e-14
        bare = {key: value for key, value in row.items() if key != "input_sha256"}
        checks["input_hashes"] &= row.get("input_sha256") == canonical_json_sha256(bare)
    for name in PARAMETERS:
        low, high = map(float, bounds[name])
        strata = {
            min(n - 1, int((float(row[name]) - low) / (high - low) * n)) for row in rows
        }
        checks["lhs_stratum_coverage"] &= len(strata) == n
    report = {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "sample_count": len(rows),
        "parameter_min": {name: min(float(row[name]) for row in rows) for name in PARAMETERS},
        "parameter_max": {name: max(float(row[name]) for row in rows) for name in PARAMETERS},
    }
    report["validation_sha256"] = canonical_json_sha256(report)
    if report["status"] != "PASS":
        raise ValueError(f"sample validation failed: {checks}")
    return report


def samples_csv_bytes(rows: Sequence[Mapping[str, Any]]) -> bytes:
    fields = ["simulation_id", "sample_index", "simulation_seed", *PARAMETERS, "input_sha256"]
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def load_neutral_fixture(repo_root: Path, config: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    root = repo_root.resolve()
    source = config["source"]
    path = root / source["formal_ready_path"]
    if sha256_file(path) != source["formal_ready_file_sha256"]:
        raise ValueError("Formal-ready source file hash mismatch")
    ready = json.loads(path.read_text(encoding="utf-8"))
    if ready["data_sha256"] != source["formal_data_sha256"] or ready["scenario_sha256"] != source["scenario_sha256"]:
        raise ValueError("Formal-ready scientific identity mismatch")
    payload = deepcopy(ready["qfr_data"])
    payload["budget"] = float(config["fixed_environment"]["budget"])
    payload["storage_cost"] = dict.fromkeys(ITEMS, 0.0)
    payload["retention"] = dict.fromkeys(ITEMS, 1.0)
    neutral = QFRData.from_dict(payload)
    metadata = {row["scenario_id"]: {"category": int(row["category"]), "hurricanes": list(row["hurricanes"]), "scenario_type": row["scenario_type"]} for row in ready["scenarios"]}
    return neutral.to_dict(), {
        "formal_ready_file_sha256": source["formal_ready_file_sha256"],
        "formal_data_sha256": source["formal_data_sha256"],
        "source_scenario_sha256": source["scenario_sha256"],
        "neutral_fixture_sha256": neutral.data_sha256,
        "scenario_count": len(neutral.scenarios),
        "budget": neutral.budget,
        "shortage_cost": dict(neutral.shortage_cost),
        "demand_scale": ready.get("demand_normalization"),
        "h": dict(neutral.storage_cost), "a": dict(neutral.retention),
        "metadata": metadata,
    }


def load_rawls24_neutral_fixture(
    repo_root: Path, config: Mapping[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build the 24-event neutral fixture from audited data and frozen reference weights."""

    root = repo_root.resolve()
    source = config["source"]
    for key in ("input", "demand", "manifest", "economic_template"):
        identity = source[key]
        if sha256_file(root / identity["path"]) != identity["sha256"]:
            raise ValueError(f"Rawls24 {key} source hash mismatch")
    rawls_manifest = json.loads((root / source["manifest"]["path"]).read_text(encoding="utf-8"))
    if rawls_manifest["canonical_data_sha256"] != source["canonical_data_sha256"]:
        raise ValueError("Rawls24 canonical data identity mismatch")
    with (root / source["input"]["path"]).open("r", encoding="utf-8", newline="") as handle:
        inputs = list(csv.DictReader(handle))
    with (root / source["demand"]["path"]).open("r", encoding="utf-8", newline="") as handle:
        demands = list(csv.DictReader(handle))
    ids = [row["scenario_id"] for row in inputs]
    if len(ids) != 24 or ids != [f"h{index:02d}" for index in range(1, 25)]:
        raise ValueError("Rawls24 scenario identity/order is not exactly h01..h24")
    if [row["scenario_id"] for row in demands] != ids:
        raise ValueError("Rawls24 input/demand scenario ordering mismatch")
    if any(row["scenario_type"] != "single_hurricane" for row in inputs):
        raise ValueError("Rawls24 fixture contains a non-single-hurricane scenario")

    reference = config["reference_weight"]
    group_by_id = {
        scenario: group
        for group, scenarios in reference["groups"].items()
        for scenario in scenarios
    }
    if set(group_by_id) != set(ids):
        raise ValueError("Rawls24 reference-weight groups do not partition all scenarios")
    florida = set(reference["groups"]["florida_major"]) | set(reference["groups"]["florida_minor"])
    major = set(reference["groups"]["florida_major"]) | set(reference["groups"]["nonflorida_major"])
    with localcontext() as decimal_context:
        decimal_context.prec = 80
        weights_decimal = {
            scenario: Decimal(reference["per_event_weight"][group_by_id[scenario]])
            for scenario in ids
        }
        total_weight = sum(weights_decimal.values())
        florida_weight = sum(weights_decimal[s] for s in florida)
        major_weight = sum(weights_decimal[s] for s in major)
        weight_tolerance = Decimal("1e-48")
        if abs(total_weight - Decimal("1")) > weight_tolerance:
            raise ValueError("Rawls24 reference weights do not sum to one")
        if abs(florida_weight - Decimal(reference["florida_mass"])) > weight_tolerance:
            raise ValueError("Rawls24 Florida reference-weight mass mismatch")
        if abs(major_weight - Decimal(reference["major_mass"])) > weight_tolerance:
            raise ValueError("Rawls24 major reference-weight mass mismatch")

    template_ready = json.loads((root / source["economic_template"]["path"]).read_text(encoding="utf-8"))
    payload = deepcopy(template_ready["qfr_data"])
    normalization = template_ready["demand_normalization"]
    by_id = {row["scenario_id"]: row for row in demands}
    mapped_demand = {
        scenario: {
            "Water": float(by_id[scenario]["water_unified"]),
            "Seasonal Influenza Vaccine": float(by_id[scenario]["medical_unified"]) * float(normalization["vaccine"]),
            "Crackers": float(by_id[scenario]["food_unified"]) * 14.0,
        }
        for scenario in ids
    }
    dref = {
        item: sum(float(weights_decimal[scenario]) * mapped_demand[scenario][item] for scenario in ids)
        for item in ITEMS
    }
    payload.update(
        scenarios=ids,
        demand=mapped_demand,
        q_availability={scenario: dict.fromkeys(ITEMS, 1.0) for scenario in ids},
        disruption={scenario: dict.fromkeys(ITEMS, 0.0) for scenario in ids},
        flexible_capacity={item: max(mapped_demand[s][item] for s in ids) for item in ITEMS},
        storage_cost=dict.fromkeys(ITEMS, 0.0),
        retention=dict.fromkeys(ITEMS, 1.0),
    )
    b_ref = sum(float(payload["q_unit_cost"][item]) * dref[item] for item in ITEMS)
    payload["budget"] = b_ref
    neutral = QFRData.from_dict(payload)
    metadata = {
        row["scenario_id"]: {
            "category": int(row["category"]),
            "hurricanes": [row["hurricane_name"]],
            "scenario_type": row["scenario_type"],
            "hurricane_name": row["hurricane_name"],
            "year": int(row["year"]),
            "evidence_status": row["evidence_status"],
        }
        for row in inputs
    }
    return neutral.to_dict(), {
        "dataset_identity": rawls_manifest["dataset_identity"],
        "canonical_data_sha256": rawls_manifest["canonical_data_sha256"],
        "neutral_fixture_sha256": neutral.data_sha256,
        "scenario_count": 24,
        "scenario_order": ids,
        "metadata": metadata,
        "reference_weight_method": reference["method"],
        "reference_weights": {scenario: float(weights_decimal[scenario]) for scenario in ids},
        "reference_weight_decimal_strings": {scenario: str(weights_decimal[scenario]) for scenario in ids},
        "reference_weight_sum": float(total_weight),
        "florida_mass": float(florida_weight),
        "major_mass": float(major_weight),
        "reference_demand": dref,
        "B_ref_formula": "sum_i((cQ_i+h_i*tau)*Dref_i/a_i), with Layer A h=0 and a=1",
        "budget": b_ref,
        "flexible_capacity": dict(neutral.flexible_capacity),
        "demand_mapping": {
            "Water": "water_unified",
            "Seasonal Influenza Vaccine": f"medical_unified * {normalization['vaccine']}",
            "Crackers": "food_unified * 14",
        },
        "demand_scale": {
            "gamma_D": 1.0,
            "water": 1.0,
            "vaccine_from_rawls_medical": float(normalization["vaccine"]),
            "crackers_from_unified_food": 14.0,
        },
        "shortage_cost": dict(neutral.shortage_cost),
        "h": dict(neutral.storage_cost),
        "a": dict(neutral.retention),
        "source_hashes": {key: source[key]["sha256"] for key in ("input", "demand", "manifest", "economic_template")},
    }


def load_rawls24_heterogeneous_fixture(
    repo_root: Path, config: Mapping[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Restore the frozen commodity h/a baseline on the audited Rawls24 fixture."""

    neutral_payload, neutral_fixture = load_rawls24_neutral_fixture(repo_root, config)
    root = repo_root.resolve()
    source = config["source"]
    template_path = root / source["economic_template"]["path"]
    template = json.loads(template_path.read_text(encoding="utf-8"))
    formal = template["qfr_data"]
    storage_cost = {item: float(formal["storage_cost"][item]) for item in ITEMS}
    retention = {item: float(formal["retention"][item]) for item in ITEMS}
    expected_storage = {
        "Water": 0.0,
        "Seasonal Influenza Vaccine": 0.0833333333333333,
        "Crackers": 0.0,
    }
    expected_retention = {
        "Water": 1.0,
        "Seasonal Influenza Vaccine": 1.0,
        "Crackers": 0.9,
    }
    if storage_cost != expected_storage or retention != expected_retention:
        raise ValueError("formal commodity heterogeneity conflicts with the frozen Layer B baseline")
    payload = deepcopy(neutral_payload)
    payload["storage_cost"] = storage_cost
    payload["retention"] = retention
    tau = float(payload["tau"])
    dref = neutral_fixture["reference_demand"]
    b_ref = sum(
        (float(payload["q_unit_cost"][item]) + storage_cost[item] * tau)
        * float(dref[item])
        / retention[item]
        for item in ITEMS
    )
    payload["budget"] = b_ref
    heterogeneous = QFRData.from_dict(payload)
    fixture = deepcopy(neutral_fixture)
    fixture.update(
        neutral_fixture_sha256=neutral_fixture["neutral_fixture_sha256"],
        heterogeneous_fixture_sha256=heterogeneous.data_sha256,
        B_ref_formula="sum_i((cQ_i+h_i*tau)*Dref_i/a_i)",
        budget=b_ref,
        h=storage_cost,
        a=retention,
        tau=tau,
        heterogeneity_source={
            "formal_ready_path": source["economic_template"]["path"],
            "formal_ready_sha256": source["economic_template"]["sha256"],
            "formal_matrix_path": config["heterogeneity"]["formal_matrix"]["path"],
            "formal_matrix_sha256": config["heterogeneity"]["formal_matrix"]["sha256"],
            "vaccine_six_month_cold_chain_cost": storage_cost["Seasonal Influenza Vaccine"] * tau,
            "crackers_retention": retention["Crackers"],
        },
    )
    matrix_identity = config["heterogeneity"]["formal_matrix"]
    matrix_path = root / matrix_identity["path"]
    if sha256_file(matrix_path) != matrix_identity["sha256"]:
        raise ValueError("formal experiment-matrix heterogeneity source hash mismatch")
    matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
    if (
        float(matrix["baseline"]["vaccine_six_month_cold_chain_cost"]) != 0.5
        or float(matrix["baseline"]["crackers_retention"]) != 0.9
    ):
        raise ValueError("formal experiment matrix conflicts with the frozen Layer B baseline")
    return heterogeneous.to_dict(), fixture


def data_for_sample(
    neutral_payload: Mapping[str, Any], metadata: Mapping[str, Any], sample: Mapping[str, Any]
) -> QFRData:
    payload = deepcopy(dict(neutral_payload))
    payload["reservation_cost"] = {item: float(sample["phi"]) * float(payload["q_unit_cost"][item]) for item in ITEMS}
    payload["exercise_cost"] = {item: float(sample["psi"]) * float(payload["q_unit_cost"][item]) for item in ITEMS}
    payload["reliability_cost"] = {
        item: {"0": 0.0, "1": float(sample["c_R1_ratio"]) * float(payload["q_unit_cost"][item]), "2": float(sample["c_R2_ratio"]) * float(payload["q_unit_cost"][item])}
        for item in ITEMS
    }
    payload["reliability_mitigation"] = {
        item: {"0": 0.0, "1": float(sample["eta_1"]), "2": float(sample["eta_2"])} for item in ITEMS
    }
    q_availability, disruption = {}, {}
    for scenario in payload["scenarios"]:
        category = int(metadata[scenario]["category"])
        q_value = 1.0 if category == 0 else float(sample[f"rho_Q{category}"])
        f_value = 1.0 if category == 0 else float(sample[f"rho_F{category}"])
        q_availability[scenario] = dict.fromkeys(ITEMS, q_value)
        disruption[scenario] = dict.fromkeys(ITEMS, 1.0 - f_value)
    payload["q_availability"] = q_availability
    payload["disruption"] = disruption
    return QFRData.from_dict(payload)


def classify_policy(first_stage: Mapping[str, Any], tolerance: float) -> str:
    q_active = any(float(value) > tolerance for value in first_stage["q"].values())
    levels = [int(value) for value in first_stage["reliability_levels"]]
    active_levels = {
        level for item in first_stage["f"].values() for level in levels
        if float(item[str(level)]) > tolerance
    }
    f_active = bool(active_levels)
    if q_active and not f_active:
        return "P1"
    if f_active and not q_active:
        return "P4"
    if q_active and f_active:
        if 2 in active_levels:
            return "P3b"
        if 1 in active_levels:
            return "P3a"
        if active_levels == {0}:
            return "P2"
    return "P5"


def validate_output_traceability(
    samples: Sequence[Mapping[str, Any]],
    scientific_rows: Sequence[Mapping[str, Any]],
    computational_rows: Sequence[Mapping[str, Any]],
) -> None:
    expected = [row["simulation_id"] for row in samples]
    if [row.get("simulation_id") for row in scientific_rows] != expected:
        raise ValueError("scientific output silently dropped or reordered a draw")
    if [row.get("simulation_id") for row in computational_rows] != expected:
        raise ValueError("computational output silently dropped or reordered a draw")
    by_id = {row["simulation_id"]: row for row in samples}
    for row in scientific_rows:
        source = by_id[row["simulation_id"]]
        if row.get("input_sha256") != source["input_sha256"]:
            raise ValueError("output/input draw identity mismatch")
        if row.get("status") == "FAILED" and not row.get("failure_type"):
            raise ValueError("failed draw was retained without failure identity")
