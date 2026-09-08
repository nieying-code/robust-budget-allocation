"""Deterministic, solver-free helpers for the Final Formal design.

This module selects frozen parameter rows and generates synthetic *inputs* only.
It deliberately has no model or optimizer imports.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np


PARAMETERS = (
    "rho_Q1", "rho_Q2", "rho_Q3", "rho_Q4", "rho_Q5",
    "rho_F1", "rho_F2", "rho_F3", "rho_F4", "rho_F5",
    "eta_1", "eta_2", "phi", "psi", "c_R1_ratio", "c_R2_ratio",
)
FORBIDDEN_OUTCOME_FIELDS = frozenset({
    "objective", "objective_T_COST", "policy_label", "shortage", "runtime",
    "worst_scenario", "candidate_hits", "R_activation", "R_level",
})
TIE_POLICY = "IEEE754_8ULP_THEN_MIN_SAMPLE_INDEX_V1"
QUANTILE_POLICY = "NUMPY_LINEAR_EMPIRICAL_QUANTILE_V1"
RNG_IDENTITY = "NUMPY_GENERATOR_PCG64_V1"
E4_GENERATOR_IDENTITY = "RAWLS24_SCIENTIFIC_OOS_GENERATOR_V1"
E5B_GENERATOR_IDENTITY = "RAWLS24_E5B_COMPUTATIONAL_BENCHMARK_GENERATOR_V1"
E5C_GENERATOR_IDENTITY = "RAWLS24_E5C_COMMODITY_BENCHMARK_GENERATOR_V1"


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _is_tie(left: float, right: float) -> bool:
    scale = max(math.ulp(float(left)), math.ulp(float(right)))
    return abs(float(left) - float(right)) <= 8.0 * scale


def _row_id(row: Mapping[str, Any]) -> int:
    return int(row["sample_index"])


def _validate_parameter_rows(rows: Sequence[Mapping[str, Any]]) -> None:
    if not rows:
        raise ValueError("parameter rows must not be empty")
    for row in rows:
        contaminated = FORBIDDEN_OUTCOME_FIELDS.intersection(row)
        if contaminated:
            raise ValueError(f"outcome fields are forbidden: {sorted(contaminated)}")
        missing = set(PARAMETERS).difference(row)
        if missing:
            raise ValueError(f"missing parameter fields: {sorted(missing)}")


def _normalized(rows: Sequence[Mapping[str, Any]], bounds: Mapping[str, Sequence[float]]) -> np.ndarray:
    _validate_parameter_rows(rows)
    matrix = np.empty((len(rows), len(PARAMETERS)), dtype=np.float64)
    for column, name in enumerate(PARAMETERS):
        low, high = map(float, bounds[name])
        if not high > low:
            raise ValueError(f"invalid theoretical bounds for {name}")
        matrix[:, column] = [(float(row[name]) - low) / (high - low) for row in rows]
    return matrix


def _argmin_tied(values: np.ndarray, row_ids: Sequence[int], available: Sequence[int]) -> int:
    best = int(available[0])
    for index in available[1:]:
        index = int(index)
        if values[index] < values[best] and not _is_tie(values[index], values[best]):
            best = index
        elif _is_tie(values[index], values[best]) and row_ids[index] < row_ids[best]:
            best = index
    return best


def _argmax_tied(values: np.ndarray, row_ids: Sequence[int], available: Sequence[int]) -> int:
    best = int(available[0])
    for index in available[1:]:
        index = int(index)
        if values[index] > values[best] and not _is_tie(values[index], values[best]):
            best = index
        elif _is_tie(values[index], values[best]) and row_ids[index] < row_ids[best]:
            best = index
    return best


def select_space_filling(
    rows: Sequence[Mapping[str, Any]], bounds: Mapping[str, Sequence[float]], size: int
) -> list[int]:
    """Center-initialized normalized-Euclidean greedy maximin row IDs."""
    if not 0 < size <= len(rows):
        raise ValueError("selection size must be in 1..len(rows)")
    z = _normalized(rows, bounds)
    row_ids = [_row_id(row) for row in rows]
    if len(set(row_ids)) != len(row_ids):
        raise ValueError("sample_index values must be unique")
    center_distance = np.linalg.norm(z - 0.5, axis=1)
    available = list(range(len(rows)))
    first = _argmin_tied(center_distance, row_ids, available)
    selected = [first]
    available.remove(first)
    min_distance = np.linalg.norm(z - z[first], axis=1)
    while len(selected) < size:
        chosen = _argmax_tied(min_distance, row_ids, available)
        selected.append(chosen)
        available.remove(chosen)
        min_distance = np.minimum(min_distance, np.linalg.norm(z - z[chosen], axis=1))
    return [row_ids[index] for index in selected]


def selection_identity(
    row_ids: Sequence[int], source_sha256: str, kind: str, parent_selection_sha256: str | None = None
) -> dict[str, Any]:
    body = {
        "kind": kind,
        "source_sample_sha256": source_sha256,
        "row_ids_in_selection_order": [int(value) for value in row_ids],
        "normalization": "THEORETICAL_FINAL_E1_MARGINAL_BOUNDS_V1",
        "distance": "NORMALIZED_EUCLIDEAN_V1",
        "initialization": "NEAREST_TO_GEOMETRIC_CENTER_0_5_V1",
        "tie_policy": TIE_POLICY,
    }
    if parent_selection_sha256 is not None:
        body["parent_selection_sha256"] = parent_selection_sha256
    return {**body, "selection_sha256": canonical_sha256(body)}


def _distinct_nearest(values: np.ndarray, row_ids: Sequence[int], quantiles: Sequence[float]) -> list[int]:
    targets = np.quantile(values, quantiles, method="linear")
    unused = list(range(len(values)))
    selected: list[int] = []
    for target in targets:
        distances = np.abs(values - float(target))
        chosen = _argmin_tied(distances, row_ids, unused)
        selected.append(row_ids[chosen])
        unused.remove(chosen)
    return selected


def select_f_supply_risk(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    _validate_parameter_rows(rows)
    row_ids = [_row_id(row) for row in rows]
    values = np.asarray([
        np.mean([1.0 - float(row[f"rho_F{k}"]) for k in range(1, 6)]) for row in rows
    ])
    quantiles = np.quantile(values, [0.25, 0.50, 0.75], method="linear")
    selected = _distinct_nearest(values, row_ids, [0.25, 0.50, 0.75])
    return {
        "levels": dict(zip(("Low", "Medium", "High"), selected, strict=True)),
        "quantiles": dict(zip(("Q25", "Q50", "Q75"), map(float, quantiles), strict=True)),
        "quantile_policy": QUANTILE_POLICY,
        "tie_policy": TIE_POLICY,
    }


def select_reliability_economics(
    parameter_rows: Sequence[Mapping[str, Any]],
    f_rows: Sequence[Mapping[str, Any]],
    activation_tolerance: float,
) -> dict[str, Any]:
    _validate_parameter_rows(parameter_rows)
    f_by_id = {int(row["sample_index"]): row for row in f_rows}
    active: list[Mapping[str, Any]] = []
    for row in parameter_rows:
        result = f_by_id.get(_row_id(row))
        if result is None:
            raise ValueError(f"missing F quantities for sample {_row_id(row)}")
        f_values = [float(result[f"F_{name}"]) for name in ("Water", "Seasonal Influenza Vaccine", "Crackers")]
        if any(value < 0 for value in f_values):
            raise ValueError("F quantities must be nonnegative")
        if any(value > activation_tolerance for value in f_values):
            active.append(row)
    if len(active) < 3:
        raise ValueError("fewer than three F-active rows")
    a1 = np.asarray([float(row["eta_1"]) / float(row["c_R1_ratio"]) for row in active])
    a2 = np.asarray([
        (float(row["eta_2"]) - float(row["eta_1"]))
        / (float(row["c_R2_ratio"]) - float(row["c_R1_ratio"])) for row in active
    ])
    sd1, sd2 = float(np.std(a1, ddof=0)), float(np.std(a2, ddof=0))
    if sd1 == 0.0 or sd2 == 0.0:
        raise RuntimeError("E3B_RELIABILITY_SCORE_DEGENERATE")
    score = 0.5 * ((a1 - np.mean(a1)) / sd1 + (a2 - np.mean(a2)) / sd2)
    row_ids = [_row_id(row) for row in active]
    selected = _distinct_nearest(score, row_ids, [0.25, 0.50, 0.75])
    quantiles = np.quantile(score, [0.25, 0.50, 0.75], method="linear")
    return {
        "active_row_count": len(active),
        "levels": dict(zip(("Unfavorable", "Reference", "Favorable"), selected, strict=True)),
        "quantiles": dict(zip(("Q25", "Q50", "Q75"), map(float, quantiles), strict=True)),
        "population": "ALL_F_ACTIVE_ROWS",
        "standard_deviation_ddof": 0,
        "activation_tolerance": float(activation_tolerance),
        "quantile_policy": QUANTILE_POLICY,
        "tie_policy": TIE_POLICY,
    }


def generate_e4b(seed: int, templates: Sequence[Mapping[str, Any]], count: int = 2000) -> list[dict[str, Any]]:
    rng = np.random.Generator(np.random.PCG64(seed))
    scenarios = []
    for index in range(1, count + 1):
        template = templates[int(rng.integers(0, len(templates)))]
        common = float(rng.uniform(0.85, 1.15))
        item = [float(rng.uniform(0.95, 1.05)) for _ in range(3)]
        base = template["demand"]
        scenarios.append({
            "scenario_id": f"OOS-{seed}-{index:04d}",
            "template_id": template["scenario_id"],
            "category": int(template["category"]),
            "m_common": common,
            "m_item": dict(zip(("Water", "Seasonal Influenza Vaccine", "Crackers"), item, strict=True)),
            "demand": {
                name: float(base[name]) * common * multiplier
                for name, multiplier in zip(("Water", "Seasonal Influenza Vaccine", "Crackers"), item, strict=True)
            },
        })
    return scenarios


def generate_e5b(seed: int, templates: Sequence[Mapping[str, Any]], row_count: int = 1000) -> dict[str, Any]:
    rng = np.random.Generator(np.random.PCG64(seed))
    parameter_row_id = int(rng.integers(1, row_count + 1))
    scenarios = []
    for index in range(1, 501):
        template = templates[int(rng.integers(0, len(templates)))]
        common = float(rng.uniform(0.85, 1.15))
        item = [float(rng.uniform(0.95, 1.05)) for _ in range(3)]
        scenarios.append({
            "scenario_id": f"E5B-{seed}-{index:03d}",
            "template_id": template["scenario_id"],
            "category": int(template["category"]),
            "demand": {
                name: float(template["demand"][name]) * common * multiplier
                for name, multiplier in zip(("Water", "Seasonal Influenza Vaccine", "Crackers"), item, strict=True)
            },
        })
    return {"seed": seed, "parameter_row_id": parameter_row_id, "master_500": scenarios}


def benchmark_budget(
    scenarios: Sequence[Mapping[str, Any]], static: Mapping[str, Mapping[str, float]]
) -> float:
    names = ("Water", "Seasonal Influenza Vaccine", "Crackers")
    means = {name: float(np.mean([row["demand"][name] for row in scenarios])) for name in names}
    return float(sum(
        (float(static[name]["c_Q"]) + float(static[name]["h_times_tau"]))
        * means[name] / float(static[name]["a"]) for name in names
    ))


def generate_e5c_items(seed: int, row_count: int = 1000) -> dict[str, Any]:
    rng = np.random.Generator(np.random.PCG64(seed))
    parameter_row_id = int(rng.integers(1, row_count + 1))
    items = []
    for suffix in range(1, 4):
        for archetype in ("Standard", "Preservation", "StorageLoss"):
            item = {
                "item_id": f"{archetype}_{suffix}", "archetype": archetype,
                "m_c": float(rng.uniform(0.8, 1.2)), "m_d": float(rng.uniform(0.8, 1.2)),
            }
            if archetype == "Standard":
                item.update({"h_times_tau": 0.0, "a": 1.0})
            elif archetype == "Preservation":
                multiplier = float(rng.uniform(0.5, 1.5))
                item.update({"m_h": multiplier, "h_times_tau": 0.5 * multiplier, "a": 1.0})
            else:
                item.update({"h_times_tau": 0.0, "a": float(rng.uniform(0.8, 1.0))})
            items.append(item)
    return {"seed": seed, "parameter_row_id": parameter_row_id, "master_9": items}
