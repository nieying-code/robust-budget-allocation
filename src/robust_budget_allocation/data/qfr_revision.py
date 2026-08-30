"""Frozen Q-F-R availability-revision configuration construction; no pilot execution."""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
from typing import Any, Mapping

from .qfr_data import QFRData, RELIABILITY_LEVELS


@dataclass(frozen=True)
class QFRPilotBaseline:
    data: QFRData
    budget_ratio: float
    reference_budget: float


def _exact_fields(payload: Mapping[str, Any], expected: set[str], label: str) -> None:
    if set(payload) != expected:
        raise ValueError(f"{label} fields are incomplete or unexpected")


def load_pilot_baseline(path: Path, budget_ratio: float) -> QFRPilotBaseline:
    """Construct one frozen pilot input without solving it or rounding computations."""

    payload = json.loads(path.resolve().read_text(encoding="utf-8"))
    _exact_fields(
        payload,
        {
            "schema_version",
            "scope",
            "items",
            "tau_months",
            "nominal_demand",
            "q_unit_cost",
            "retention",
            "storage_horizon_cost",
            "reservation_cost_ratio",
            "exercise_cost_ratio",
            "shortage_cost_ratio",
            "reliability_mitigation",
            "reliability_cost_ratios",
            "scenarios",
            "budget_ratios",
            "expected_b_ref",
        },
        "Q-F-R pilot baseline",
    )
    if payload["schema_version"] != 1 or payload["scope"] != (
        "FROZEN_PILOT_BASELINE_CONFIGURATION_NOT_PILOT_EXECUTION"
    ):
        raise ValueError("not the frozen Q-F-R availability pilot baseline")
    ratio = float(budget_ratio)
    ratios = tuple(float(value) for value in payload["budget_ratios"])
    if ratio not in ratios:
        raise ValueError("budget ratio is not in the frozen pilot baseline")
    items = tuple(payload["items"])
    tau = float(payload["tau_months"])
    nominal = {item: float(payload["nominal_demand"][item]) for item in items}
    q_cost = {item: float(payload["q_unit_cost"][item]) for item in items}
    retention = {item: float(payload["retention"][item]) for item in items}
    horizon_storage = {
        item: float(payload["storage_horizon_cost"][item]) for item in items
    }
    storage = {item: horizon_storage[item] / tau for item in items}
    reference = sum(
        (q_cost[item] + storage[item] * tau) * nominal[item] / retention[item]
        for item in items
    )
    expected_reference = float(payload["expected_b_ref"])
    if not math.isclose(reference, expected_reference, rel_tol=0.0, abs_tol=1e-9):
        raise ValueError("computed B_ref does not match the frozen pilot baseline")

    scenario_rows = payload["scenarios"]
    scenarios = tuple(str(row["id"]) for row in scenario_rows)
    if len(scenarios) != 5 or len(set(scenarios)) != 5:
        raise ValueError("pilot baseline must contain exactly five unique scenarios")
    demand = {
        str(row["id"]): {
            item: nominal[item] * float(row["demand_multiplier"]) for item in items
        }
        for row in scenario_rows
    }
    q_availability = {
        str(row["id"]): {
            item: float(row["q_availability"]) for item in items
        }
        for row in scenario_rows
    }
    disruption = {
        str(row["id"]): {item: float(row["disruption"]) for item in items}
        for row in scenario_rows
    }
    fbar = {item: max(demand[scenario][item] for scenario in scenarios) for item in items}
    eta = tuple(float(value) for value in payload["reliability_mitigation"])
    r_cost = tuple(float(value) for value in payload["reliability_cost_ratios"])
    if len(eta) != len(RELIABILITY_LEVELS) or len(r_cost) != len(RELIABILITY_LEVELS):
        raise ValueError("pilot reliability arrays must cover levels 0, 1, and 2")
    data = QFRData(
        items=items,
        scenarios=scenarios,
        budget=ratio * reference,
        tau=tau,
        q_unit_cost=q_cost,
        storage_cost=storage,
        retention=retention,
        flexible_capacity=fbar,
        reservation_cost={
            item: float(payload["reservation_cost_ratio"]) * q_cost[item]
            for item in items
        },
        reliability_cost={
            item: {level: r_cost[level] * q_cost[item] for level in RELIABILITY_LEVELS}
            for item in items
        },
        reliability_mitigation={
            item: {level: eta[level] for level in RELIABILITY_LEVELS}
            for item in items
        },
        exercise_cost={
            item: float(payload["exercise_cost_ratio"]) * q_cost[item]
            for item in items
        },
        shortage_cost={
            item: float(payload["shortage_cost_ratio"]) * q_cost[item]
            for item in items
        },
        demand=demand,
        q_availability=q_availability,
        disruption=disruption,
        schema_version=3,
    )
    return QFRPilotBaseline(data=data, budget_ratio=ratio, reference_budget=reference)
