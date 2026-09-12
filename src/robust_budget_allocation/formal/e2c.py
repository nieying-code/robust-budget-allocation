"""Solver-free Formal E2-C reliability boundary analysis."""

from __future__ import annotations

from collections import Counter
import csv
import math
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

from robust_budget_allocation.algorithms.qfr_final_a1 import (
    FINAL_A1_IDENTITY,
    FINAL_A1_IMPLEMENTATION_REVISION,
)
from robust_budget_allocation.formal.e2a import (
    BUDGET,
    OUTPUT_ITEMS,
    POLICY_TOLERANCE,
    SAMPLE_SHA256,
    load_base_fixture,
    load_baseline,
    load_samples,
)
from robust_budget_allocation.formal.e2b import frozen_hashes as frozen_e1_e2a_hashes
from robust_budget_allocation.io.hashing import canonical_json_sha256, sha256_file


LEVELS = ("NONE", "R0", "R1", "R2")
PAID_LEVELS = ("R1", "R2")
OUTPUT = Path("formal_results/e2_final/e2c")
E2B_HASHES = Path("formal_results/e2_final/e2b/HASHES.sha256")
METRICS = (
    "A_R1", "A_R2", "eta_1", "eta_2", "c_R1_ratio", "c_R2_ratio",
    "incremental_reliability_gain", "incremental_reliability_cost_ratio",
    "phi", "psi", "rho_F_severity_score", "F_quantity", "F_exposure", "budget_usage",
)


def frozen_hashes(root: Path) -> dict[str, str]:
    return {**frozen_e1_e2a_hashes(root), "e2b_HASHES": sha256_file(root / E2B_HASHES)}


def validate_preflight(root: Path) -> dict[str, Any]:
    samples = load_samples(root)
    results = load_baseline(root)
    payload, _ = load_base_fixture(root)
    if len(samples) != 1000 or len(results) != 1000:
        raise ValueError("Final E1 population is not exactly 1000 rows")
    if any(row["algorithm_identity"] != FINAL_A1_IDENTITY for row in results):
        raise ValueError("Final E1 algorithm identity drift")
    if FINAL_A1_IMPLEMENTATION_REVISION != "A1_FINAL_NO_MEMORY_V1_R1_WITNESS_GATED_INFEASIBLE_RETRY":
        raise ValueError("Final A1 implementation revision drift")
    if float(payload["budget"]) != BUDGET:
        raise ValueError("Final E1 budget drift")
    return {
        "status": "PASS", "scope": "FORMAL_E2C_PREFLIGHT_V1",
        "sample_rows": 1000, "sample_sha256": SAMPLE_SHA256,
        "result_rows": 1000,
        "e1_results_sha256": sha256_file(root / "formal_results/e1_final/e1_scientific_results.csv"),
        "algorithm_identity": FINAL_A1_IDENTITY,
        "implementation_revision": FINAL_A1_IMPLEMENTATION_REVISION,
        "policy_tolerance": POLICY_TOLERANCE,
        "F_active_rule": "sum_i(F_i)>policy_tolerance",
        "rho_F_severity_score": "mean_k(1-rho_Fk)",
        "F_exposure": "F_quantity*rho_F_severity_score",
        "budget": BUDGET,
        "frozen_hashes": frozen_hashes(root),
        "E2_C_new_scientific_optimization_runs": 0,
        "E2_D_runs": 0,
    }


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if str(value) in {"True", "1"}:
        return True
    if str(value) in {"False", "0"}:
        return False
    raise ValueError(f"invalid boolean {value!r}")


def observations(root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    samples = load_samples(root)
    results = load_baseline(root)
    payload, _ = load_base_fixture(root)
    result: list[dict[str, Any]] = []
    aggregate_counts = Counter()
    aggregate_f_active = 0
    for sample, scientific in zip(samples, results, strict=True):
        if sample["simulation_id"] != scientific["simulation_id"] or sample["input_sha256"] != scientific["input_sha256"]:
            raise ValueError("Final E1 parameter/result traceability mismatch")
        severity = sum(1.0 - float(sample[f"rho_F{k}"]) for k in range(1, 6)) / 5.0
        ar1 = float(sample["eta_1"]) / float(sample["c_R1_ratio"])
        gain2 = float(sample["eta_2"]) - float(sample["eta_1"])
        cost2 = float(sample["c_R2_ratio"]) - float(sample["c_R1_ratio"])
        ar2 = gain2 / cost2
        row_levels: list[str] = []
        total_f = sum(float(scientific[f"F_{label}"]) for label in OUTPUT_ITEMS.values())
        f_active_row = total_f > POLICY_TOLERANCE
        aggregate_f_active += int(f_active_row)
        for item, label in OUTPUT_ITEMS.items():
            f_quantity = float(scientific[f"F_{label}"])
            f_active = f_quantity > POLICY_TOLERANCE
            reliability = str(scientific[f"R_{label}"])
            if reliability not in LEVELS:
                raise ValueError(f"invalid reliability class: {scientific['simulation_id']} {item}")
            if f_active != (reliability != "NONE"):
                raise ValueError(f"R/F linking violation: {scientific['simulation_id']} {item}")
            if reliability in PAID_LEVELS and not f_active:
                raise ValueError(f"paid R without protected F: {scientific['simulation_id']} {item}")
            row_levels.append(reliability)
            c_q = float(payload["q_unit_cost"][item])
            row = {
                "simulation_id": sample["simulation_id"], "sample_index": sample["sample_index"],
                "input_sha256": sample["input_sha256"], "scientific_first_stage_sha256": scientific["first_stage_sha256"],
                "commodity": label, "c_Q": c_q, "F_active_row": f_active_row,
                "F_active_item": f_active, "reliability_level": reliability,
                "eta_1": sample["eta_1"], "eta_2": sample["eta_2"],
                "c_R1_ratio": sample["c_R1_ratio"], "c_R2_ratio": sample["c_R2_ratio"],
                "c_R1": float(sample["c_R1_ratio"]) * c_q,
                "c_R2": float(sample["c_R2_ratio"]) * c_q,
                "incremental_reliability_gain": gain2,
                "incremental_reliability_cost_ratio": cost2,
                "A_R1": ar1, "A_R2": ar2,
                "phi": sample["phi"], "psi": sample["psi"],
                "rho_F_severity_score": severity,
                "F_quantity": f_quantity, "F_exposure": f_quantity * severity,
                "Q_quantity": float(scientific[f"Q_{label}"]),
                "budget_usage": float(scientific["budget_usage"]),
                "policy_label": scientific["policy_label"],
            }
            row["observation_sha256"] = canonical_json_sha256(row)
            result.append(row)
        if not f_active_row:
            aggregate_level = "NONE"
        elif "R2" in row_levels:
            aggregate_level = "R2"
        elif "R1" in row_levels:
            aggregate_level = "R1"
        else:
            aggregate_level = "R0"
        aggregate_counts[aggregate_level] += 1
    if aggregate_f_active != 792:
        raise ValueError(f"Final E1 F-active population mismatch: {aggregate_f_active}")
    return result, {
        "total_E1_rows": 1000,
        "F_active_rows": aggregate_f_active,
        "F_inactive_rows": 1000 - aggregate_f_active,
        "aggregate_reliability_counts": {level: aggregate_counts[level] for level in LEVELS},
    }


def quantile(values: Sequence[float], probability: float) -> float:
    return float(np.quantile(np.asarray(values, dtype=float), probability, method="linear"))


def extended_summary(values: Sequence[float]) -> dict[str, float | int]:
    numeric = [float(value) for value in values]
    if not numeric:
        return {"N": 0}
    return {
        "N": len(numeric), "mean": float(np.mean(numeric)), "median": quantile(numeric, .5),
        "Q10": quantile(numeric, .1), "Q25": quantile(numeric, .25), "Q50": quantile(numeric, .5),
        "Q75": quantile(numeric, .75), "Q90": quantile(numeric, .9),
        "min": min(numeric), "max": max(numeric),
    }


def class_summary(active: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for scope, subset in [("ALL", active), *[(label, [row for row in active if row["commodity"] == label]) for label in OUTPUT_ITEMS.values()]]:
        for level in ("R0", "R1", "R2"):
            selected = [row for row in subset if row["reliability_level"] == level]
            for metric in METRICS:
                result.append({"scope": scope, "reliability_level": level, "metric": metric, **extended_summary([float(row[metric]) for row in selected])})
    return result


def quintile_edges(rows: Sequence[Mapping[str, Any]], field: str) -> list[float]:
    values = [float(row[field]) for row in rows]
    return [quantile(values, probability) for probability in (0.0, .2, .4, .6, .8, 1.0)]


def assign_bin(value: float, edges: Sequence[float]) -> int:
    return min(4, int(np.searchsorted(np.asarray(edges[1:-1]), float(value), side="right"))) + 1


def bin_summary(active: Sequence[Mapping[str, Any]], field: str) -> tuple[list[dict[str, Any]], list[float]]:
    edges = quintile_edges(active, field)
    result: list[dict[str, Any]] = []
    for bin_index in range(1, 6):
        selected = [row for row in active if assign_bin(float(row[field]), edges) == bin_index]
        counts = Counter(str(row["reliability_level"]) for row in selected)
        result.append({
            "metric": field, "quintile": bin_index, "lower_edge": edges[bin_index - 1], "upper_edge": edges[bin_index],
            "N": len(selected), **{f"{level}_count": counts[level] for level in ("R0", "R1", "R2")},
            **{f"{level}_share": counts[level] / len(selected) if selected else 0.0 for level in ("R0", "R1", "R2")},
            "mean_F_exposure": float(np.mean([float(row["F_exposure"]) for row in selected])),
            "median_F_exposure": quantile([float(row["F_exposure"]) for row in selected], .5),
        })
    return result, edges


def interaction_map(active: Sequence[Mapping[str, Any]], field: str) -> list[dict[str, Any]]:
    x_edges = quintile_edges(active, field)
    exposure_edges = quintile_edges(active, "F_exposure")
    result: list[dict[str, Any]] = []
    for x_bin in range(1, 6):
        for exposure_bin in range(1, 6):
            selected = [row for row in active if assign_bin(float(row[field]), x_edges) == x_bin and assign_bin(float(row["F_exposure"]), exposure_edges) == exposure_bin]
            counts = Counter(str(row["reliability_level"]) for row in selected)
            result.append({
                "metric": field, "metric_quintile": x_bin, "F_exposure_quintile": exposure_bin,
                "N": len(selected), **{f"{level}_count": counts[level] for level in ("R0", "R1", "R2")},
                **{f"{level}_share": counts[level] / len(selected) if selected else 0.0 for level in ("R0", "R1", "R2")},
            })
    return result


def average_ranks(values: Sequence[float]) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    order = np.argsort(array, kind="mergesort")
    ranks = np.empty(len(array), dtype=float)
    start = 0
    while start < len(array):
        end = start + 1
        while end < len(array) and array[order[end]] == array[order[start]]:
            end += 1
        ranks[order[start:end]] = (start + 1 + end) / 2.0
        start = end
    return ranks


def spearman(x: Sequence[float], y: Sequence[float]) -> float:
    rx, ry = average_ranks(x), average_ranks(y)
    return float(np.corrcoef(rx, ry)[0, 1])


def auc_rank_biserial(lower: Sequence[float], upper: Sequence[float]) -> dict[str, float | int]:
    left, right = np.asarray(lower, dtype=float), np.asarray(upper, dtype=float)
    comparisons = (right[:, None] > left[None, :]).sum() + 0.5 * (right[:, None] == left[None, :]).sum()
    auc = float(comparisons / (len(left) * len(right)))
    return {"N_lower": len(left), "N_upper": len(right), "AUC_upper_gt_lower": auc, "rank_biserial": 2.0 * auc - 1.0, "ordering_violation_fraction": 1.0 - auc}


def statistical_support(active: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    ordinal = {"R0": 0.0, "R1": 1.0, "R2": 2.0}
    result: list[dict[str, Any]] = []
    scopes = [("ALL_ACTIVE_ITEM_OBSERVATIONS", active)] + [
        (commodity, [row for row in active if row["commodity"] == commodity])
        for commodity in OUTPUT_ITEMS.values()
    ]
    comparisons = (("R0", ("R1", "R2"), "R0_vs_R1plus", "A_R1"), ("R1", ("R2",), "R1_vs_R2", "A_R2"))
    for scope, subset in scopes:
        for field in ("A_R1", "A_R2", "F_quantity", "F_exposure", "rho_F_severity_score", "phi", "psi"):
            result.append({"analysis": "spearman_with_R_ordinal", "metric": field, "scope": scope, "N": len(subset), "effect_size": spearman([float(row[field]) for row in subset], [ordinal[str(row["reliability_level"])] for row in subset])})
        for lower, upper_levels, name, primary in comparisons:
            for field in (primary, "F_exposure", "F_quantity"):
                lower_values = [float(row[field]) for row in subset if row["reliability_level"] == lower]
                upper_values = [float(row[field]) for row in subset if row["reliability_level"] in upper_levels]
                result.append({"analysis": "rank_biserial", "comparison": name, "metric": field, "scope": scope, **auc_rank_biserial(lower_values, upper_values)})
    return result


def boundary_rows(active: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for metric, low, high in (("A_R1", "R0", ("R1", "R2")), ("A_R2", "R1", ("R2",))):
        lower = [float(row[metric]) for row in active if row["reliability_level"] == low]
        upper = [float(row[metric]) for row in active if row["reliability_level"] in high]
        effect = auc_rank_biserial(lower, upper)
        result.append({
            "comparison": f"{low}_vs_{'+'.join(high)}", "metric": metric,
            "lower_median": quantile(lower, .5), "upper_median": quantile(upper, .5),
            "lower_Q25": quantile(lower, .25), "lower_Q75": quantile(lower, .75),
            "upper_Q25": quantile(upper, .25), "upper_Q75": quantile(upper, .75),
            "quartile_overlap": max(0.0, min(quantile(lower,.75), quantile(upper,.75)) - max(quantile(lower,.25), quantile(upper,.25))),
            **effect, "interpretation": "EMPIRICAL_DECISION_BOUNDARY_NOT_STRUCTURAL_THEOREM",
        })
    return result


def commodity_summary(active: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for commodity in OUTPUT_ITEMS.values():
        subset = [row for row in active if row["commodity"] == commodity]
        counts = Counter(str(row["reliability_level"]) for row in subset)
        rows.append({
            "commodity": commodity, "F_active": len(subset), "NONE": 1000 - len(subset),
            **{level: counts[level] for level in ("R0", "R1", "R2")},
            "mean_A_R1": float(np.mean([float(row["A_R1"]) for row in subset])),
            "median_A_R1": quantile([float(row["A_R1"]) for row in subset], .5),
            "mean_A_R2": float(np.mean([float(row["A_R2"]) for row in subset])),
            "median_A_R2": quantile([float(row["A_R2"]) for row in subset], .5),
            "mean_F_quantity": float(np.mean([float(row["F_quantity"]) for row in subset])),
            "median_F_quantity": quantile([float(row["F_quantity"]) for row in subset], .5),
            "mean_F_exposure": float(np.mean([float(row["F_exposure"]) for row in subset])),
            "median_F_exposure": quantile([float(row["F_exposure"]) for row in subset], .5),
        })
    return rows
