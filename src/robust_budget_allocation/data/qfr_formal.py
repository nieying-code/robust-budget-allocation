"""Deterministic R6-A Gulf Coast data transformation; never solves a model."""

from __future__ import annotations

from collections.abc import Mapping
import json
import math
from pathlib import Path
from statistics import mean, median
from typing import Any

from robust_budget_allocation.data.qfr_data import QFRData, RELIABILITY_LEVELS
from robust_budget_allocation.io.hashing import canonical_json_sha256


ACTIVE_ITEMS = ("Water", "Seasonal Influenza Vaccine", "Crackers")
FORMAL_CONFIG_PATH = Path("configs/r6_formal_data_v1.json")


def _stable_numbers(value: Any) -> Any:
    """Normalize derived floats so artifacts are stable across supported CPython builds."""

    if isinstance(value, float):
        return float(format(value, ".15g"))
    if isinstance(value, dict):
        return {key: _stable_numbers(member) for key, member in value.items()}
    if isinstance(value, list):
        return [_stable_numbers(member) for member in value]
    return value


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("formal configuration must be a JSON object")
    return payload


def _require_close(actual: float, expected: float, label: str, tolerance: float = 1e-10) -> None:
    if not math.isclose(actual, expected, rel_tol=0.0, abs_tol=tolerance):
        raise ValueError(f"{label} mismatch: {actual!r} != {expected!r}")


def build_formal_data(config_path: Path) -> dict[str, Any]:
    """Build the complete 51-scenario R6-A data product without optimization."""

    payload = _load_json(config_path)
    if payload.get("scope") != "R6_A_FORMAL_DATA_PREPARATION_NO_SCIENTIFIC_SOLVES":
        raise ValueError("not the registered R6-A formal-data configuration")
    if tuple(payload.get("active_commodities", ())) != ACTIVE_ITEMS:
        raise ValueError("active Formal commodities must be Water, Vaccine, and Crackers")

    hurricanes = {row["id"]: row for row in payload["hurricanes"]}
    if len(hurricanes) != 15 or len(hurricanes) != len(payload["hurricanes"]):
        raise ValueError("exactly 15 unique source hurricanes are required")
    scenarios = payload["scenarios"]
    if len(scenarios) != 51 or len({row["id"] for row in scenarios}) != 51:
        raise ValueError("exactly 51 unique scenarios are required")
    counts = {"single": 0, "combined": 0, "no_hurricane": 0}
    probability_sum = 0.0
    normalized_rows: list[dict[str, Any]] = []
    normalization = payload["demand_normalization"]
    vaccine_multiplier = (
        float(normalization["vaccine_multiplier_numerator"])
        / float(normalization["vaccine_multiplier_denominator"])
    )

    for scenario in scenarios:
        members = tuple(scenario["hurricanes"])
        if any(member not in hurricanes for member in members) or len(set(members)) != len(members):
            raise ValueError(f"invalid hurricane composition for {scenario['id']}")
        if len(members) == 0:
            kind = "no_hurricane"
            category = 0
        elif len(members) == 1:
            kind = "single"
            category = int(hurricanes[members[0]]["category"])
        elif len(members) == 2:
            kind = "combined"
            category = max(int(hurricanes[member]["category"]) for member in members)
        else:
            raise ValueError("R6-A source scenarios may contain zero, one, or two hurricanes")
        counts[kind] += 1
        probability = float(scenario["probability"])
        if probability <= 0:
            raise ValueError("scenario probability must be positive")
        probability_sum += probability
        raw = {
            field: sum(float(hurricanes[member][field]) for member in members)
            for field in ("water", "mre", "medical")
        }
        category_values = payload["category_mapping"][str(category)]
        demand = {
            "Water": float(normalization["water_multiplier"]) * raw["water"],
            "Seasonal Influenza Vaccine": vaccine_multiplier * raw["medical"],
            "Crackers": float(normalization["crackers_multiplier"]) * raw["mre"],
        }
        normalized_rows.append({
            "scenario_id": scenario["id"],
            "scenario_type": kind,
            "probability": probability,
            "hurricanes": list(members),
            "category": category,
            "raw_demand": raw,
            "formal_demand": demand,
            "q_availability": float(category_values["q_availability"]),
            "disruption": float(category_values["disruption"]),
        })

    if counts != {"single": 15, "combined": 35, "no_hurricane": 1}:
        raise ValueError(f"scenario composition mismatch: {counts}")
    _require_close(probability_sum, 1.0, "scenario probability sum")

    parameters = payload["commodity_parameters"]
    tau = float(payload["tau_months"])
    q_cost = {item: float(parameters[item]["q_unit_cost"]) for item in ACTIVE_ITEMS}
    horizon_storage = {
        item: float(parameters[item]["storage_horizon_cost"]) for item in ACTIVE_ITEMS
    }
    storage = {item: horizon_storage[item] / tau for item in ACTIVE_ITEMS}
    retention = {item: float(parameters[item]["retention"]) for item in ACTIVE_ITEMS}
    beta = float(payload["shortage_beta"])
    shortage = {
        item: beta * float(parameters[item]["priority"]) * q_cost[item]
        for item in ACTIVE_ITEMS
    }
    phi = float(payload["flexibility"]["baseline_phi"])
    psi = float(payload["flexibility"]["baseline_psi"])
    _require_close(phi + psi, 1.05, "F split sum")
    reservation = {item: phi * q_cost[item] for item in ACTIVE_ITEMS}
    exercise = {item: psi * q_cost[item] for item in ACTIVE_ITEMS}
    eta = tuple(float(value) for value in payload["reliability"]["eta"])
    r_ratios = tuple(float(value) for value in payload["reliability"]["cost_ratios"])
    if eta != (0.0, 0.5, 0.8) or r_ratios != (0.0, 0.1, 0.25):
        raise ValueError("R6-A reliability levels or cost ratios changed")
    demand = {row["scenario_id"]: row["formal_demand"] for row in normalized_rows}
    fbar = {item: max(demand[row["scenario_id"]][item] for row in normalized_rows) for item in ACTIVE_ITEMS}
    reference_demand = {
        item: sum(row["probability"] * row["formal_demand"][item] for row in normalized_rows)
        for item in ACTIVE_ITEMS
    }
    b_ref_components = {
        item: (q_cost[item] + horizon_storage[item]) * reference_demand[item] / retention[item]
        for item in ACTIVE_ITEMS
    }
    b_ref = sum(b_ref_components.values())

    qfr_data = QFRData(
        items=ACTIVE_ITEMS,
        scenarios=tuple(row["scenario_id"] for row in normalized_rows),
        budget=b_ref,
        tau=tau,
        q_unit_cost=q_cost,
        storage_cost=storage,
        retention=retention,
        flexible_capacity=fbar,
        reservation_cost=reservation,
        reliability_cost={
            item: {level: r_ratios[level] * q_cost[item] for level in RELIABILITY_LEVELS}
            for item in ACTIVE_ITEMS
        },
        reliability_mitigation={
            item: {level: eta[level] for level in RELIABILITY_LEVELS}
            for item in ACTIVE_ITEMS
        },
        exercise_cost=exercise,
        shortage_cost=shortage,
        demand=demand,
        q_availability={
            row["scenario_id"]: {item: row["q_availability"] for item in ACTIVE_ITEMS}
            for row in normalized_rows
        },
        disruption={
            row["scenario_id"]: {item: row["disruption"] for item in ACTIVE_ITEMS}
            for row in normalized_rows
        },
        schema_version=3,
    )
    audit = economic_scale_audit(normalized_rows, q_cost, horizon_storage, retention, shortage)
    result = {
        "schema_version": 1,
        "scope": "R6_A_FORMAL_READY_DATA_NO_SCIENTIFIC_SOLVES",
        "scientific_runs": 0,
        "scenario_counts": counts,
        "probability_sum": probability_sum,
        "demand_normalization": {
            "water": 1000.0,
            "vaccine": vaccine_multiplier,
            "crackers": 14000.0,
        },
        "reference_demand_rule": "probability_weighted_mean_over_51_source_scenarios",
        "reference_demand": reference_demand,
        "flexible_capacity_rule": "maximum_transformed_demand_over_51_source_scenarios",
        "flexible_capacity": fbar,
        "reference_budget_rule": "sum_i((cQ_i+h_i*tau)*Dref_i/a_i)",
        "reference_budget_components": b_ref_components,
        "reference_budget": b_ref,
        "parameters": {
            "tau": tau,
            "q_unit_cost": q_cost,
            "storage_cost_per_month": storage,
            "storage_horizon_cost": horizon_storage,
            "retention": retention,
            "reservation_cost": reservation,
            "exercise_cost": exercise,
            "shortage_cost": shortage,
            "reliability_mitigation": list(eta),
            "reliability_cost_ratios": list(r_ratios),
            "f_split_sensitivity": payload["flexibility"]["split_sensitivity"],
        },
        "scenarios": normalized_rows,
        "economic_scale_audit": audit,
        "qfr_data": qfr_data.to_dict(),
    }
    result = _stable_numbers(result)
    result["data_sha256"] = canonical_json_sha256(result)
    return result


def _summary(values: list[float], weights: list[float]) -> dict[str, float]:
    return {
        "min": min(values),
        "median": median(values),
        "mean": mean(values),
        "max": max(values),
        "probability_weighted_mean": sum(value * weight for value, weight in zip(values, weights, strict=True)),
    }


def economic_scale_audit(
    rows: list[dict[str, Any]],
    q_cost: Mapping[str, float],
    horizon_storage: Mapping[str, float],
    retention: Mapping[str, float],
    shortage: Mapping[str, float],
) -> dict[str, Any]:
    """Calculate deterministic, non-result-driven 51-scenario scale diagnostics."""

    weights = [row["probability"] for row in rows]
    q_exposure = {
        item: [
            (q_cost[item] + horizon_storage[item]) * row["formal_demand"][item] / retention[item]
            for row in rows
        ]
        for item in ACTIVE_ITEMS
    }
    shortage_exposure = {
        item: [shortage[item] * row["formal_demand"][item] for row in rows]
        for item in ACTIVE_ITEMS
    }
    positive = [
        index for index in range(len(rows))
        if sum(q_exposure[item][index] for item in ACTIVE_ITEMS) > 0
    ]

    def share_summary(exposures: Mapping[str, list[float]]) -> dict[str, Any]:
        shares: dict[str, list[float]] = {item: [] for item in ACTIVE_ITEMS}
        for index in positive:
            total = sum(exposures[item][index] for item in ACTIVE_ITEMS)
            for item in ACTIVE_ITEMS:
                shares[item].append(exposures[item][index] / total)
        aggregate = {
            item: sum(weights[index] * exposures[item][index] for index in range(len(rows)))
            for item in ACTIVE_ITEMS
        }
        aggregate_total = sum(aggregate.values())
        return {
            "scenario_share": {
                item: {
                    "min": min(shares[item]),
                    "median": median(shares[item]),
                    "mean": mean(shares[item]),
                    "max": max(shares[item]),
                }
                for item in ACTIVE_ITEMS
            },
            "probability_weighted_aggregate_share": {
                item: aggregate[item] / aggregate_total for item in ACTIVE_ITEMS
            },
            "zero_total_scenarios_excluded_from_shares": len(rows) - len(positive),
        }

    def outliers(exposures: Mapping[str, list[float]]) -> dict[str, str]:
        result: dict[str, str] = {}
        for item in ACTIVE_ITEMS:
            best = max(
                positive,
                key=lambda index: exposures[item][index]
                / sum(exposures[other][index] for other in ACTIVE_ITEMS),
            )
            result[item] = rows[best]["scenario_id"]
        return result

    result = {
        "effective_q_exposure": {
            "absolute": {item: _summary(q_exposure[item], weights) for item in ACTIVE_ITEMS},
            **share_summary(q_exposure),
            "commodity_heavy_scenarios": outliers(q_exposure),
        },
        "shortage_exposure": {
            "absolute": {item: _summary(shortage_exposure[item], weights) for item in ACTIVE_ITEMS},
            **share_summary(shortage_exposure),
            "commodity_heavy_scenarios": outliers(shortage_exposure),
        },
    }
    for family in ("effective_q_exposure", "shortage_exposure"):
        shares = result[family]["scenario_share"]
        for item in ACTIVE_ITEMS:
            if shares[item]["max"] > 0.99 or shares[item]["min"] < 0.0001:
                result.setdefault("scale_guard_flags", []).append(
                    {"family": family, "item": item, "min": shares[item]["min"], "max": shares[item]["max"]}
                )
    return result
