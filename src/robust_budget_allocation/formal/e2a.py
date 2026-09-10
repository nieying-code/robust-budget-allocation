"""Formal E2-A commodity-heterogeneity experiment support.

This module is deliberately a thin adapter around the frozen Rawls24 inputs and
the production Final A1 solver.  It does not define a new mathematical model.
"""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
import csv
import io
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

from robust_budget_allocation.algorithms.qfr_final_a1 import (
    FINAL_A1_IDENTITY,
    solve_qfr_final_a1,
)
from robust_budget_allocation.algorithms.qfr_state import QFRFirstStage, first_stage_cost
from robust_budget_allocation.data.qfr_data import QFRData
from robust_budget_allocation.io.hashing import canonical_json_sha256, sha256_file


ITEMS = ("Water", "Seasonal Influenza Vaccine", "Crackers")
OUTPUT_ITEMS = {"Water": "Water", "Seasonal Influenza Vaccine": "Vaccine", "Crackers": "Crackers"}
POLICIES = ("P1", "P2", "P3a", "P3b", "P4", "P5")
PARAMETERS = (
    "rho_Q1", "rho_Q2", "rho_Q3", "rho_Q4", "rho_Q5",
    "rho_F1", "rho_F2", "rho_F3", "rho_F4", "rho_F5",
    "eta_1", "eta_2", "phi", "psi", "c_R1_ratio", "c_R2_ratio",
)
POLICY_TOLERANCE = 1e-7
SAMPLE_SHA256 = "ac617befc8fbb7510e1b64b617c7e0339ea948ca519d0d18131f3b8048c131e0"
BUDGET = 19137905.85543848
DESIGN_RELATIVE = Path("configs/final_formal_scientific_design_v1.json")
SAMPLES_RELATIVE = Path("formal_results/e1_final/e1_samples.csv")
BASELINE_RELATIVE = Path("formal_results/e1_final/e1_scientific_results.csv")
INPUT_RELATIVE = Path("data/r6_rawls24/unified_hurricane_input.csv")
DEMAND_RELATIVE = Path("data/r6_rawls24/unified_rawls_demand.csv")
TEMPLATE_RELATIVE = Path("configs/r6c_formal_ready_data_v2.json")

CASES: dict[str, dict[str, float]] = {
    "E2A_VACCINE_H0": {"h_V_tau": 0.0, "a_C": 0.9},
    "E2A_VACCINE_H1": {"h_V_tau": 1.0, "a_C": 0.9},
    "E2A_CRACKERS_A100": {"h_V_tau": 0.5, "a_C": 1.0},
    "E2A_CRACKERS_A080": {"h_V_tau": 0.5, "a_C": 0.8},
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def csv_bytes(rows: Sequence[Mapping[str, Any]], columns: Sequence[str] | None = None) -> bytes:
    if not rows:
        raise ValueError("cannot serialize an empty E2-A table")
    fields = list(columns or dict.fromkeys(key for row in rows for key in row))
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def load_design(root: Path) -> dict[str, Any]:
    return json.loads((root / DESIGN_RELATIVE).read_text(encoding="utf-8"))


def _assert_close(actual: float, expected: float, label: str, tolerance: float = 1e-12) -> None:
    if not math.isclose(float(actual), float(expected), rel_tol=tolerance, abs_tol=tolerance):
        raise ValueError(f"{label} mismatch: {actual!r} != {expected!r}")


def validate_design(design: Mapping[str, Any]) -> None:
    common, e1, e2a = design["common"], design["E1"], design["E2"]["A"]
    if common["dataset"] != "rawls_24_real_single_hurricane_data_recalibration_v1":
        raise ValueError("E2-A requires the frozen Rawls24 dataset")
    if common["scenario_order"] != [f"h{index:02d}" for index in range(1, 25)]:
        raise ValueError("E2-A scenario identity/order is not h01..h24")
    if common["commodities"] != list(ITEMS) or common["model"] != "M2":
        raise ValueError("E2-A model/commodity identity mismatch")
    if design["algorithm"]["identity"] != FINAL_A1_IDENTITY or design["algorithm"]["memory_enabled"]:
        raise ValueError("E2-A requires Final no-memory A1")
    if int(e1["sample_size"]) != 1000 or int(e1["seed"]) != 20260903:
        raise ValueError("E2-A frozen E1 sample identity mismatch")
    if e1["sample_table_sha256"] != SAMPLE_SHA256:
        raise ValueError("E2-A frozen sample SHA mismatch")
    _assert_close(common["B_ref_E1"], BUDGET, "absolute E1 budget")
    _assert_close(common["beta"], 4.0, "beta")
    if common["lambda"] != [1.0, 1.0, 1.0] or float(common["gamma_D"]) != 1.0:
        raise ValueError("E2-A lambda/gamma_D mismatch")
    if e2a["design"] != "OFAT" or int(e2a["new_optimizations"]) != 4000:
        raise ValueError("E2-A frozen matrix mismatch")
    expected_cells = {(value["h_V_tau"], value["a_C"]) for value in CASES.values()}
    actual_cells = {(float(value["h_V_tau"]), float(value["a_C"])) for value in e2a["new_cells"]}
    if actual_cells != expected_cells:
        raise ValueError("E2-A case cells differ from the frozen design")
    _assert_close(e2a["budget"], BUDGET, "E2-A budget")


def load_samples(root: Path) -> list[dict[str, Any]]:
    path = root / SAMPLES_RELATIVE
    if sha256_file(path) != SAMPLE_SHA256:
        raise ValueError("frozen E1 sample file SHA mismatch")
    raw = read_csv(path)
    if len(raw) != 1000:
        raise ValueError("frozen E1 sample table is not 1000 rows")
    expected_ids = [f"LA-{index:04d}" for index in range(1, 1001)]
    if [row["simulation_id"] for row in raw] != expected_ids:
        raise ValueError("frozen E1 sample IDs are missing, duplicated, or reordered")
    rows: list[dict[str, Any]] = []
    for index, row in enumerate(raw, 1):
        converted: dict[str, Any] = {
            "simulation_id": row["simulation_id"],
            "sample_index": int(row["sample_index"]),
            "simulation_seed": int(row["simulation_seed"]),
            "input_sha256": row["input_sha256"],
        }
        converted.update({name: float(row[name]) for name in PARAMETERS})
        if converted["sample_index"] != index or converted["simulation_seed"] != 20260903:
            raise ValueError("frozen E1 sample index/seed mismatch")
        rows.append(converted)
    return rows


def load_baseline(root: Path) -> list[dict[str, str]]:
    rows = read_csv(root / BASELINE_RELATIVE)
    if len(rows) != 1000 or [row["simulation_id"] for row in rows] != [
        f"LA-{index:04d}" for index in range(1, 1001)
    ]:
        raise ValueError("Final E1 baseline is incomplete or reordered")
    if any(row["algorithm_identity"] != FINAL_A1_IDENTITY for row in rows):
        raise ValueError("Final E1 baseline algorithm identity mismatch")
    if any(row["certificate_status"] != "PASS" for row in rows):
        raise ValueError("Final E1 baseline contains an uncertified row")
    return rows


def load_base_fixture(root: Path) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    design = load_design(root)
    source = design["common"]["data_sources"]
    for key, relative in (("unified_input", INPUT_RELATIVE), ("unified_demand", DEMAND_RELATIVE), ("economic_template", TEMPLATE_RELATIVE)):
        if source[key]["path"] != relative.as_posix() or sha256_file(root / relative) != source[key]["sha256"]:
            raise ValueError(f"frozen {key} source identity mismatch")
    inputs, demands = read_csv(root / INPUT_RELATIVE), read_csv(root / DEMAND_RELATIVE)
    scenario_ids = [f"h{index:02d}" for index in range(1, 25)]
    if [row["scenario_id"] for row in inputs] != scenario_ids or [row["scenario_id"] for row in demands] != scenario_ids:
        raise ValueError("Rawls24 input/demand ordering mismatch")
    if any(row["scenario_type"] != "single_hurricane" for row in inputs):
        raise ValueError("Rawls24 contains a non-single-hurricane scenario")
    template = json.loads((root / TEMPLATE_RELATIVE).read_text(encoding="utf-8"))
    payload = deepcopy(template["qfr_data"])
    normalization = template["demand_normalization"]
    demand_by_id = {row["scenario_id"]: row for row in demands}
    mapped = {
        scenario: {
            "Water": float(demand_by_id[scenario]["water_unified"]),
            "Seasonal Influenza Vaccine": float(demand_by_id[scenario]["medical_unified"]) * float(normalization["vaccine"]),
            "Crackers": float(demand_by_id[scenario]["food_unified"]) * 14.0,
        }
        for scenario in scenario_ids
    }
    payload.update(
        scenarios=scenario_ids,
        demand=mapped,
        q_availability={scenario: dict.fromkeys(ITEMS, 1.0) for scenario in scenario_ids},
        disruption={scenario: dict.fromkeys(ITEMS, 0.0) for scenario in scenario_ids},
        flexible_capacity={item: max(mapped[scenario][item] for scenario in scenario_ids) for item in ITEMS},
        storage_cost={"Water": 0.0, "Seasonal Influenza Vaccine": 0.0833333333333333, "Crackers": 0.0},
        retention={"Water": 1.0, "Seasonal Influenza Vaccine": 1.0, "Crackers": 0.9},
        budget=BUDGET,
    )
    metadata = {
        row["scenario_id"]: {"category": int(row["category"]), "hurricane_name": row["hurricane_name"]}
        for row in inputs
    }
    return payload, metadata


def data_for_case_sample(
    base_payload: Mapping[str, Any],
    metadata: Mapping[str, Mapping[str, Any]],
    case_id: str,
    sample: Mapping[str, Any],
) -> QFRData:
    if case_id not in CASES:
        raise ValueError(f"unknown E2-A case: {case_id}")
    payload = deepcopy(dict(base_payload))
    case = CASES[case_id]
    tau = float(payload["tau"])
    # Preserve the exact frozen baseline literal (0.0833333333333333/month)
    # for Crackers OFAT cells.  Recomputing 0.5/6 would create a different
    # binary float and therefore a false scientific-identity drift.
    if case["h_V_tau"] != 0.5:
        payload["storage_cost"]["Seasonal Influenza Vaccine"] = case["h_V_tau"] / tau
    payload["retention"]["Crackers"] = case["a_C"]
    payload["budget"] = BUDGET
    payload["reservation_cost"] = {
        item: float(sample["phi"]) * float(payload["q_unit_cost"][item]) for item in ITEMS
    }
    payload["exercise_cost"] = {
        item: float(sample["psi"]) * float(payload["q_unit_cost"][item]) for item in ITEMS
    }
    payload["reliability_cost"] = {
        item: {
            "0": 0.0,
            "1": float(sample["c_R1_ratio"]) * float(payload["q_unit_cost"][item]),
            "2": float(sample["c_R2_ratio"]) * float(payload["q_unit_cost"][item]),
        }
        for item in ITEMS
    }
    payload["reliability_mitigation"] = {
        item: {"0": 0.0, "1": float(sample["eta_1"]), "2": float(sample["eta_2"])}
        for item in ITEMS
    }
    for scenario in payload["scenarios"]:
        category = int(metadata[scenario]["category"])
        payload["q_availability"][scenario] = dict.fromkeys(ITEMS, float(sample[f"rho_Q{category}"]))
        payload["disruption"][scenario] = dict.fromkeys(ITEMS, 1.0 - float(sample[f"rho_F{category}"]))
    return QFRData.from_dict(payload)


def classify_policy(first_stage: Mapping[str, Any], tolerance: float = POLICY_TOLERANCE) -> str:
    q_active = any(float(value) > tolerance for value in first_stage["q"].values())
    active_levels = {
        int(level)
        for levels in first_stage["f"].values()
        for level, value in levels.items()
        if float(value) > tolerance
    }
    if q_active and not active_levels:
        return "P1"
    if active_levels and not q_active:
        return "P4"
    if q_active and active_levels:
        if 2 in active_levels:
            return "P3b"
        if 1 in active_levels:
            return "P3a"
        if active_levels == {0}:
            return "P2"
    return "P5"


def _reliability_label(first_stage: Mapping[str, Any], item: str) -> str:
    if sum(float(value) for value in first_stage["f"][item].values()) <= POLICY_TOLERANCE:
        return "NONE"
    selected = [int(level) for level, value in first_stage["z"][item].items() if int(value) == 1]
    if len(selected) != 1:
        raise ValueError(f"active F for {item} lacks one reliability selection")
    return f"R{selected[0]}"


def serialize_result(
    case_id: str,
    sample: Mapping[str, Any],
    data: QFRData,
    metadata: Mapping[str, Mapping[str, Any]],
    result: Mapping[str, Any],
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "case_id": case_id,
        "simulation_id": sample["simulation_id"],
        "sample_index": sample["sample_index"],
        "input_sha256": sample["input_sha256"],
        "model_kind": "M2",
        "algorithm_identity": FINAL_A1_IDENTITY,
        "status": result["status"],
        "certificate_status": "PASS" if result["status"] == "certified" else "FAIL",
        "failure_type": "" if result["status"] == "certified" else result["status"],
        "failure_message": "" if result["status"] == "certified" else (result.get("diagnostic") or ""),
        "data_sha256": data.data_sha256,
        "scenario_sha256": data.scenario_sha256,
        "h_V_tau": CASES[case_id]["h_V_tau"],
        "a_C": CASES[case_id]["a_C"],
        "budget": data.budget,
        "beta": 4.0,
        "lambda_Water": 1.0,
        "lambda_Vaccine": 1.0,
        "lambda_Crackers": 1.0,
        "gamma_D": 1.0,
        "result_sha256": result["result_sha256"],
        "iterations": result["iterations"],
        "full_exact_certification_calls": result["full_exact_certification_calls"],
        "complete_full_exact_certification_calls": result["complete_full_exact_certification_calls"],
    }
    if result["status"] != "certified":
        for field in (
            "first_stage_sha256", "policy_label", "T_COST", "certified_objective", "C_Q", "C_F", "C_R",
            "first_stage_cost", "worst_scenario", "worst_category", "worst_hurricane", "exact_worst_case_loss",
            "worst_exercise_cost", "worst_shortage_penalty", "worst_total_shortage", "worst_total_F_exercise", "budget_usage",
        ):
            row[field] = ""
        for item, label in OUTPUT_ITEMS.items():
            for prefix in ("Q", "F", "R", "Q_active", "F_active", "worst_exercise", "worst_shortage"):
                row[f"{prefix}_{label}"] = ""
        row["row_sha256"] = canonical_json_sha256(row)
        return row
    incumbent = result["incumbent"]
    first_stage = incumbent["first_stage"]
    decision = QFRFirstStage.from_dict(first_stage)
    oracle = incumbent["oracle"]
    worst_id = oracle["worst_scenario"]
    worst = next(value for value in oracle["results"] if value["scenario_id"] == worst_id)
    c_q = sum(
        (data.q_unit_cost[item] + data.storage_cost[item] * data.tau) * decision.q[item]
        for item in ITEMS
    )
    c_f = sum(data.reservation_cost[item] * decision.f[item][level] for item in ITEMS for level in decision.reliability_levels)
    c_r = sum(data.reliability_cost[item][level] * decision.f[item][level] for item in ITEMS for level in decision.reliability_levels)
    pre = first_stage_cost(data, decision)
    row.update(
        first_stage_sha256=incumbent["first_stage_sha256"],
        policy_label=classify_policy(first_stage),
        T_COST=float(result["objective"]),
        certified_objective=float(result["objective"]),
        C_Q=float(c_q), C_F=float(c_f), C_R=float(c_r), first_stage_cost=float(pre),
        worst_scenario=worst_id,
        worst_category=int(metadata[worst_id]["category"]),
        worst_hurricane=metadata[worst_id]["hurricane_name"],
        exact_worst_case_loss=float(oracle["worst_loss"]),
        worst_exercise_cost=float(worst["exercise_cost"]),
        worst_shortage_penalty=float(worst["shortage_loss"]),
        worst_total_shortage=sum(float(value) for value in worst["shortage"].values()),
        worst_total_F_exercise=sum(float(value) for value in worst["exercise"].values()),
        budget_usage=(pre + float(worst["exercise_cost"])) / data.budget,
    )
    for item, label in OUTPUT_ITEMS.items():
        q = float(first_stage["q"][item])
        f = sum(float(value) for value in first_stage["f"][item].values())
        row[f"Q_{label}"] = q
        row[f"F_{label}"] = f
        row[f"R_{label}"] = _reliability_label(first_stage, item)
        row[f"Q_active_{label}"] = q > POLICY_TOLERANCE
        row[f"F_active_{label}"] = f > POLICY_TOLERANCE
        row[f"worst_exercise_{label}"] = float(worst["exercise"][item])
        row[f"worst_shortage_{label}"] = float(worst["shortage"][item])
    row["row_sha256"] = canonical_json_sha256(row)
    return row


def solve_one(
    root: Path, case_id: str, sample: Mapping[str, Any]
) -> dict[str, Any]:
    payload, metadata = load_base_fixture(root)
    data = data_for_case_sample(payload, metadata, case_id, sample)
    result = solve_qfr_final_a1(data, "M2")
    return serialize_result(case_id, sample, data, metadata, result)


def distribution(values: Sequence[float]) -> dict[str, float]:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return {}
    def quantile(probability: float) -> float:
        position = (len(ordered) - 1) * probability
        lower, upper = math.floor(position), math.ceil(position)
        if lower == upper:
            return ordered[lower]
        return ordered[lower] + (position - lower) * (ordered[upper] - ordered[lower])
    return {
        "min": ordered[0], "median": quantile(0.5), "mean": sum(ordered) / len(ordered),
        "P90": quantile(0.9), "P95": quantile(0.95), "max": ordered[-1],
    }


def _boolean(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if str(value) in {"True", "1"}:
        return True
    if str(value) in {"False", "0"}:
        return False
    raise ValueError(f"invalid serialized boolean: {value!r}")


def summarize_case(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    successful = [row for row in rows if row["certificate_status"] == "PASS"]
    commodity: dict[str, Any] = {}
    for label in OUTPUT_ITEMS.values():
        commodity[label] = {
            "Q_active": sum(_boolean(row[f"Q_active_{label}"]) for row in successful),
            "F_active": sum(_boolean(row[f"F_active_{label}"]) for row in successful),
            "reliability": dict(Counter(str(row[f"R_{label}"]) for row in successful)),
            "Q_quantity": distribution([float(row[f"Q_{label}"]) for row in successful]),
            "F_quantity": distribution([float(row[f"F_{label}"]) for row in successful]),
        }
    mixed_q_f = sum(
        any(_boolean(row[f"Q_active_{label}"]) for label in OUTPUT_ITEMS.values())
        and any(_boolean(row[f"F_active_{label}"]) for label in OUTPUT_ITEMS.values())
        for row in successful
    )
    same_item_q_f_cases = sum(
        any(
            _boolean(row[f"Q_active_{label}"])
            and _boolean(row[f"F_active_{label}"])
            for label in OUTPUT_ITEMS.values()
        )
        for row in successful
    )
    same_item_q_f_item_draws = sum(
        _boolean(row[f"Q_active_{label}"])
        and _boolean(row[f"F_active_{label}"])
        for row in successful
        for label in OUTPUT_ITEMS.values()
    )
    return {
        "requested": len(rows),
        "certified": len(successful),
        "failed": len(rows) - len(successful),
        "failure_types": dict(Counter(str(row["failure_type"]) for row in rows if row["failure_type"])),
        "policy_counts": {policy: sum(row.get("policy_label") == policy for row in successful) for policy in POLICIES},
        "commodity": commodity,
        "mixed_QF_cases": mixed_q_f,
        "same_item_QF_coexistence_cases": same_item_q_f_cases,
        "same_item_QF_coexistence_item_draws": same_item_q_f_item_draws,
        "T_COST": distribution([float(row["T_COST"]) for row in successful]),
        "shortage": distribution([float(row["worst_total_shortage"]) for row in successful]),
        "budget_usage": distribution([float(row["budget_usage"]) for row in successful]),
        "worst_scenario_counts": dict(Counter(str(row["worst_scenario"]) for row in successful)),
    }


def paired_rows(case_rows: Sequence[Mapping[str, Any]], baseline: Sequence[Mapping[str, str]]) -> list[dict[str, Any]]:
    base = {row["simulation_id"]: row for row in baseline}
    result: list[dict[str, Any]] = []
    for row in case_rows:
        old = base[row["simulation_id"]]
        paired: dict[str, Any] = {
            "case_id": row["case_id"], "simulation_id": row["simulation_id"], "sample_index": row["sample_index"],
            "input_sha256": row["input_sha256"], "certificate_status": row["certificate_status"],
            "baseline_policy": old["policy_label"], "case_policy": row.get("policy_label", ""),
            "policy_transition": f"{old['policy_label']}->{row.get('policy_label', '')}" if row["certificate_status"] == "PASS" else "FAILED",
        }
        for field in ("T_COST", "budget_usage"):
            paired[f"baseline_{field}"] = float(old[field])
            paired[f"case_{field}"] = row.get(field, "")
            paired[f"delta_{field}"] = float(row[field]) - float(old[field]) if row["certificate_status"] == "PASS" else ""
        for label in OUTPUT_ITEMS.values():
            for prefix in ("Q", "F"):
                paired[f"baseline_{prefix}_{label}"] = float(old[f"{prefix}_{label}"])
                paired[f"case_{prefix}_{label}"] = row.get(f"{prefix}_{label}", "")
                paired[f"delta_{prefix}_{label}"] = (
                    float(row[f"{prefix}_{label}"]) - float(old[f"{prefix}_{label}"])
                    if row["certificate_status"] == "PASS" else ""
                )
            paired[f"baseline_R_{label}"] = old[f"R_{label}"]
            paired[f"case_R_{label}"] = row.get(f"R_{label}", "")
            paired[f"reliability_transition_{label}"] = (
                f"{old[f'R_{label}']}->{row[f'R_{label}']}" if row["certificate_status"] == "PASS" else "FAILED"
            )
        paired["row_sha256"] = canonical_json_sha256(paired)
        result.append(paired)
    return result


def summarize_paired(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    successful = [row for row in rows if row["certificate_status"] == "PASS"]
    summary: dict[str, Any] = {
        "paired_rows": len(rows), "certified_pairs": len(successful),
        "policy_transitions": dict(Counter(str(row["policy_transition"]) for row in successful)),
        "delta_T_COST": distribution([float(row["delta_T_COST"]) for row in successful]),
        "delta_budget_usage": distribution([float(row["delta_budget_usage"]) for row in successful]),
    }
    summary["commodity_changes"] = {
        label: {
            "delta_Q": distribution([float(row[f"delta_Q_{label}"]) for row in successful]),
            "delta_F": distribution([float(row[f"delta_F_{label}"]) for row in successful]),
            "reliability_transitions": dict(Counter(str(row[f"reliability_transition_{label}"]) for row in successful)),
        }
        for label in OUTPUT_ITEMS.values()
    }
    return summary


def baseline_identity_preflight(root: Path) -> dict[str, Any]:
    design = load_design(root)
    validate_design(design)
    samples = load_samples(root)
    baseline = load_baseline(root)
    payload, metadata = load_base_fixture(root)
    for sample, expected in zip(samples, baseline, strict=True):
        # The E1 baseline is h_V*tau=0.5 and a_C=0.9. Build it without invoking a solver.
        data = data_for_case_sample(payload, metadata, "E2A_CRACKERS_A100", sample)
        replacement = data.to_dict()
        replacement["retention"]["Crackers"] = 0.9
        data = QFRData.from_dict(replacement)
        if data.data_sha256 != expected["data_sha256"] or data.scenario_sha256 != expected["scenario_sha256"]:
            raise ValueError(f"baseline data identity mismatch for {sample['simulation_id']}")
    return {
        "status": "PASS",
        "sample_count": len(samples),
        "sample_sha256": sha256_file(root / SAMPLES_RELATIVE),
        "baseline_reused_count": len(baseline),
        "baseline_rerun": False,
        "algorithm_identity": FINAL_A1_IDENTITY,
        "dataset": design["common"]["dataset"],
        "scenario_count": 24,
        "budget": BUDGET,
        "beta": 4.0,
        "lambda": [1.0, 1.0, 1.0],
        "gamma_D": 1.0,
        "baseline_h_V_tau": 0.5,
        "baseline_a_C": 0.9,
        "planned_new_runs": 4000,
        "cases": CASES,
        "E2_B_runs": 0, "E2_C_runs": 0, "E2_D_runs": 0,
    }
