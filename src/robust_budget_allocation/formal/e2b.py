"""Formal E2-B budget-sensitivity support over the frozen Final E1 population."""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

from robust_budget_allocation.algorithms.qfr_final_a1 import (
    FINAL_A1_IDENTITY,
    FINAL_A1_IMPLEMENTATION_REVISION,
    solve_qfr_final_a1,
)
from robust_budget_allocation.algorithms.qfr_numerical_validation import (
    family_feasibility_threshold,
)
from robust_budget_allocation.algorithms.qfr_state import QFRFirstStage, first_stage_cost
from robust_budget_allocation.data.qfr_data import QFRData
from robust_budget_allocation.formal.e2a import (
    BASELINE_RELATIVE,
    BUDGET as B_REF,
    ITEMS,
    OUTPUT_ITEMS,
    POLICIES,
    POLICY_TOLERANCE,
    SAMPLE_SHA256,
    SAMPLES_RELATIVE,
    baseline_identity_preflight,
    classify_policy,
    csv_bytes,
    distribution,
    load_base_fixture,
    load_baseline,
    load_samples,
    read_csv,
)
from robust_budget_allocation.io.hashing import canonical_json_sha256, sha256_file


CASES: dict[str, dict[str, float]] = {
    "E2B_B075": {"budget_ratio": 0.75, "budget": 0.75 * B_REF},
    "E2B_B125": {"budget_ratio": 1.25, "budget": 1.25 * B_REF},
}
BASELINE_CASE = "E2B_B100"
LEVELS = ("NONE", "R0", "R1", "R2")


def validate_e2b_design(root: Path) -> dict[str, Any]:
    report = baseline_identity_preflight(root)
    design = __import__("json").loads(
        (root / "configs/final_formal_scientific_design_v1.json").read_text(encoding="utf-8")
    )
    e2b = design["E2"]["B"]
    if [float(value) for value in e2b["budget_ratios"]] != [0.75, 1.0, 1.25]:
        raise ValueError("frozen E2-B budget ratios changed")
    if not e2b["baseline_reused"] or int(e2b["new_optimizations"]) != 2000:
        raise ValueError("frozen E2-B execution design changed")
    if FINAL_A1_IMPLEMENTATION_REVISION != (
        "A1_FINAL_NO_MEMORY_V1_R1_WITNESS_GATED_INFEASIBLE_RETRY"
    ):
        raise ValueError("Final A1 implementation revision changed")
    return {
        **report,
        "scope": "FORMAL_E2B_PREFLIGHT_V1",
        "planned_new_runs": 2000,
        "budget_reference": B_REF,
        "budgets": {case: values["budget"] for case, values in CASES.items()},
        "baseline_case": BASELINE_CASE,
        "baseline_budget": B_REF,
        "implementation_revision": FINAL_A1_IMPLEMENTATION_REVISION,
        "E2_A_frozen": True,
        "E2_A_rerun": False,
        "E2_C_runs": 0,
        "E2_D_runs": 0,
    }


def data_for_case_sample(
    base_payload: Mapping[str, Any],
    metadata: Mapping[str, Mapping[str, Any]],
    case_id: str,
    sample: Mapping[str, Any],
) -> QFRData:
    if case_id not in CASES:
        raise ValueError(f"unknown E2-B case: {case_id}")
    payload = deepcopy(dict(base_payload))
    payload["budget"] = CASES[case_id]["budget"]
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
        payload["q_availability"][scenario] = dict.fromkeys(
            ITEMS, float(sample[f"rho_Q{category}"])
        )
        payload["disruption"][scenario] = dict.fromkeys(
            ITEMS, 1.0 - float(sample[f"rho_F{category}"])
        )
    data = QFRData.from_dict(payload)
    # Fail closed on the OFAT identity: the base fixture already contains h*tau=.5 and a=.9.
    if not math.isclose(
        data.storage_cost["Seasonal Influenza Vaccine"] * data.tau,
        0.5,
        rel_tol=0.0,
        abs_tol=1e-12,
    ) or data.retention["Crackers"] != 0.9:
        raise ValueError("E2-B heterogeneous commodity baseline drift")
    return data


def _reliability_label(first_stage: Mapping[str, Any], item: str) -> str:
    if sum(float(value) for value in first_stage["f"][item].values()) <= POLICY_TOLERANCE:
        return "NONE"
    selected = [int(level) for level, value in first_stage["z"][item].items() if int(value) == 1]
    if len(selected) != 1:
        raise ValueError(f"active F for {item} lacks one reliability selection")
    return f"R{selected[0]}"


def _portfolio(first_stage: Mapping[str, Any]) -> tuple[bool, bool, str]:
    q_items = [OUTPUT_ITEMS[item] for item in ITEMS if float(first_stage["q"][item]) > POLICY_TOLERANCE]
    f_items = [
        OUTPUT_ITEMS[item]
        for item in ITEMS
        if sum(float(value) for value in first_stage["f"][item].values()) > POLICY_TOLERANCE
    ]
    same = any(item in q_items and item in f_items for item in OUTPUT_ITEMS.values())
    return bool(q_items and f_items), same, f"Q[{'+'.join(q_items) or 'NONE'}]|F[{'+'.join(f_items) or 'NONE'}]"


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
        "implementation_revision": FINAL_A1_IMPLEMENTATION_REVISION,
        "status": result["status"],
        "certificate_status": "PASS" if result["status"] == "certified" else "FAIL",
        "failure_type": "" if result["status"] == "certified" else result["status"],
        "failure_message": "" if result["status"] == "certified" else (result.get("diagnostic") or ""),
        "data_sha256": data.data_sha256,
        "scenario_sha256": data.scenario_sha256,
        "budget_ratio": CASES[case_id]["budget_ratio"],
        "budget": data.budget,
        "beta": 4.0,
        "lambda_Water": 1.0,
        "lambda_Vaccine": 1.0,
        "lambda_Crackers": 1.0,
        "gamma_D": 1.0,
        "h_V_tau": 0.5,
        "a_C": 0.9,
        "result_sha256": result["result_sha256"],
        "iterations": result["iterations"],
        "full_exact_certification_calls": result["full_exact_certification_calls"],
        "complete_full_exact_certification_calls": result["complete_full_exact_certification_calls"],
    }
    if result["status"] != "certified":
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
    c_f = sum(
        data.reservation_cost[item] * decision.f[item][level]
        for item in ITEMS for level in decision.reliability_levels
    )
    c_r = sum(
        data.reliability_cost[item][level] * decision.f[item][level]
        for item in ITEMS for level in decision.reliability_levels
    )
    pre = first_stage_cost(data, decision)
    exercise_cost = float(worst["exercise_cost"])
    budget_spend = pre + exercise_cost
    mixed, same, portfolio = _portfolio(first_stage)
    row.update(
        first_stage_sha256=incumbent["first_stage_sha256"],
        policy_label=classify_policy(first_stage),
        mixed_aggregate_QF=mixed,
        same_item_QF_coexistence=same,
        cross_item_specialization=mixed and not same,
        portfolio_pattern=portfolio,
        T_COST=float(result["objective"]),
        certified_objective=float(result["objective"]),
        C_Q=float(c_q), C_F=float(c_f), C_R=float(c_r),
        first_stage_cost=float(pre),
        worst_scenario=worst_id,
        worst_category=int(metadata[worst_id]["category"]),
        worst_hurricane=metadata[worst_id]["hurricane_name"],
        exact_worst_case_loss=float(oracle["worst_loss"]),
        worst_exercise_cost=exercise_cost,
        worst_shortage_penalty=float(worst["shortage_loss"]),
        worst_total_shortage=sum(float(value) for value in worst["shortage"].values()),
        worst_total_F_exercise=sum(float(value) for value in worst["exercise"].values()),
        budget_spend=float(budget_spend),
        budget_residual=float(data.budget - budget_spend),
        budget_usage=float(budget_spend / data.budget),
        Q_budget_share=float(c_q / data.budget),
        F_reservation_budget_share=float(c_f / data.budget),
        R_budget_share=float(c_r / data.budget),
        emergency_budget_share=float(exercise_cost / data.budget),
    )
    for item, label in OUTPUT_ITEMS.items():
        q = float(first_stage["q"][item])
        f = sum(float(value) for value in first_stage["f"][item].values())
        reliability = _reliability_label(first_stage, item)
        row[f"Q_{label}"] = q
        row[f"F_{label}"] = f
        row[f"R_{label}"] = reliability
        for level in range(3):
            row[f"z_R{level}_{label}"] = int(first_stage["z"][item][str(level)])
        row[f"Q_active_{label}"] = q > POLICY_TOLERANCE
        row[f"F_active_{label}"] = f > POLICY_TOLERANCE
        row[f"same_item_QF_{label}"] = q > POLICY_TOLERANCE and f > POLICY_TOLERANCE
        row[f"worst_exercise_{label}"] = float(worst["exercise"][item])
        row[f"worst_shortage_{label}"] = float(worst["shortage"][item])
    row["row_sha256"] = canonical_json_sha256(row)
    return row


def solve_one(root: Path, case_id: str, sample: Mapping[str, Any]) -> dict[str, Any]:
    payload, metadata = load_base_fixture(root)
    data = data_for_case_sample(payload, metadata, case_id, sample)
    result = solve_qfr_final_a1(data, "M2")
    return serialize_result(case_id, sample, data, metadata, result)


def _bool(value: Any) -> bool:
    return value is True or str(value) in {"True", "1"}


def quartile_distribution(values: Sequence[float]) -> dict[str, float]:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return {}
    def q(p: float) -> float:
        at = (len(ordered) - 1) * p
        lo, hi = math.floor(at), math.ceil(at)
        return ordered[lo] if lo == hi else ordered[lo] + (at - lo) * (ordered[hi] - ordered[lo])
    return {"mean": sum(ordered) / len(ordered), "median": q(.5), "Q25": q(.25), "Q75": q(.75)}


def outcome_comparison(before: float, after: float, family: str) -> str:
    scale = max(abs(float(before)), abs(float(after)), 1.0)
    threshold = (
        1e-7 + 1e-9 * scale
        if family == "objective"
        else family_feasibility_threshold("quantity_flow", before, after)
    )
    delta = float(after) - float(before)
    if abs(delta) <= threshold:
        return "unchanged"
    return "improved" if delta < 0.0 else "worsened"


def summarize_level(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if len(rows) != 1000 or any(row["certificate_status"] != "PASS" for row in rows):
        raise ValueError("level summary requires exactly 1000 certified rows")
    commodity: dict[str, Any] = {}
    for label in OUTPUT_ITEMS.values():
        commodity[label] = {
            "Q_active": sum(_bool(row[f"Q_active_{label}"]) for row in rows),
            "F_active": sum(_bool(row[f"F_active_{label}"]) for row in rows),
            "reliability": {level: sum(row[f"R_{label}"] == level for row in rows) for level in LEVELS},
            "Q_quantity": quartile_distribution([float(row[f"Q_{label}"]) for row in rows]),
            "F_quantity": quartile_distribution([float(row[f"F_{label}"]) for row in rows]),
            "shortage": {
                **quartile_distribution([float(row[f"worst_shortage_{label}"]) for row in rows]),
                "zero_frequency": sum(float(row[f"worst_shortage_{label}"]) <= POLICY_TOLERANCE for row in rows),
                "positive_frequency": sum(float(row[f"worst_shortage_{label}"]) > POLICY_TOLERANCE for row in rows),
            },
        }
    near_binding = []
    for row in rows:
        threshold = family_feasibility_threshold("budget", float(row["budget"]), float(row["budget_spend"]))
        near_binding.append(abs(float(row["budget_residual"])) <= threshold)
    return {
        "rows": 1000,
        "policy_counts": {policy: sum(row["policy_label"] == policy for row in rows) for policy in POLICIES},
        "commodity": commodity,
        "aggregate_reliability": {
            level: sum(row[f"R_{label}"] == level for row in rows for label in OUTPUT_ITEMS.values())
            for level in LEVELS
        },
        "mixed_aggregate_QF": sum(_bool(row["mixed_aggregate_QF"]) for row in rows),
        "same_item_QF_coexistence": sum(_bool(row["same_item_QF_coexistence"]) for row in rows),
        "cross_item_specialization": dict(Counter(str(row["portfolio_pattern"]) for row in rows if _bool(row["cross_item_specialization"]))),
        "T_COST": quartile_distribution([float(row["T_COST"]) for row in rows]),
        "aggregate_shortage": quartile_distribution([float(row["worst_total_shortage"]) for row in rows]),
        "budget_utilization": {
            **quartile_distribution([float(row["budget_usage"]) for row in rows]),
            "near_binding": sum(near_binding),
            "slack": len(rows) - sum(near_binding),
        },
        "mechanism_expenditure": {
            field: quartile_distribution([float(row[field]) for row in rows])
            for field in ("C_Q", "C_F", "C_R", "worst_exercise_cost")
        },
        "mechanism_budget_share": {
            field: quartile_distribution([float(row[field]) for row in rows])
            for field in ("Q_budget_share", "F_reservation_budget_share", "R_budget_share", "emergency_budget_share")
        },
        "worst_scenario_counts": dict(Counter(str(row["worst_scenario"]) for row in rows)),
    }


def baseline_rows(root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source in load_baseline(root):
        row: dict[str, Any] = dict(source)
        row.update(case_id=BASELINE_CASE, budget_ratio=1.0, budget=B_REF)
        row["mixed_aggregate_QF"] = source["policy_label"] in {"P2", "P3a", "P3b"}
        row["budget_spend"] = float(source["budget_usage"]) * B_REF
        row["budget_residual"] = B_REF - float(row["budget_spend"])
        row["Q_budget_share"] = float(source["C_Q"]) / B_REF
        row["F_reservation_budget_share"] = float(source["C_F"]) / B_REF
        row["R_budget_share"] = float(source["C_R"]) / B_REF
        row["emergency_budget_share"] = float(source["worst_exercise_cost"]) / B_REF
        rows.append(row)
    return rows


def paired_rows(levels: Mapping[str, Sequence[Mapping[str, Any]]]) -> list[dict[str, Any]]:
    indexed = {level: {str(row["simulation_id"]): row for row in rows} for level, rows in levels.items()}
    result: list[dict[str, Any]] = []
    for index in range(1, 1001):
        simulation_id = f"LA-{index:04d}"
        low, base, high = (indexed[level][simulation_id] for level in ("B075", "B100", "B125"))
        row: dict[str, Any] = {
            "simulation_id": simulation_id,
            "sample_index": index,
            "input_sha256": low["input_sha256"],
        }
        if len({low["input_sha256"], base["input_sha256"], high["input_sha256"]}) != 1:
            raise ValueError(f"paired parameter identity mismatch: {simulation_id}")
        for name, value in (("B075", low), ("B100", base), ("B125", high)):
            for field in (
                "policy_label", "T_COST", "worst_total_shortage", "budget_usage", "portfolio_pattern",
                "C_Q", "C_F", "C_R", "worst_exercise_cost",
            ):
                row[f"{name}_{field}"] = value[field]
            for label in OUTPUT_ITEMS.values():
                for field in ("Q", "F", "R", "worst_shortage"):
                    row[f"{name}_{field}_{label}"] = value[f"{field}_{label}"]
        for before, after in (("B075", "B100"), ("B100", "B125"), ("B075", "B125")):
            row[f"policy_transition_{before}_{after}"] = f"{row[f'{before}_policy_label']}->{row[f'{after}_policy_label']}"
            for field in ("T_COST", "worst_total_shortage"):
                row[f"delta_{field}_{before}_{after}"] = float(row[f"{after}_{field}"]) - float(row[f"{before}_{field}"])
            for label in OUTPUT_ITEMS.values():
                row[f"R_transition_{label}_{before}_{after}"] = f"{row[f'{before}_R_{label}']}->{row[f'{after}_R_{label}']}"
        row["row_sha256"] = canonical_json_sha256(row)
        result.append(row)
    return result


def summarize_pairs(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for before, after in (("B075", "B100"), ("B100", "B125"), ("B075", "B125")):
        key = f"{before}_to_{after}"
        shortage_status = [
            outcome_comparison(float(row[f"{before}_worst_total_shortage"]), float(row[f"{after}_worst_total_shortage"]), "quantity")
            for row in rows
        ]
        objective_status = [
            outcome_comparison(float(row[f"{before}_T_COST"]), float(row[f"{after}_T_COST"]), "objective")
            for row in rows
        ]
        summary[key] = {
            "policy_transitions": dict(Counter(str(row[f"policy_transition_{before}_{after}"]) for row in rows)),
            "T_COST_delta": quartile_distribution([float(row[f"delta_T_COST_{before}_{after}"]) for row in rows]),
            "T_COST_direction": dict(Counter(objective_status)),
            "shortage_delta": quartile_distribution([float(row[f"delta_worst_total_shortage_{before}_{after}"]) for row in rows]),
            "shortage_direction": dict(Counter(shortage_status)),
            "reliability_transitions": {
                label: dict(Counter(str(row[f"R_transition_{label}_{before}_{after}"]) for row in rows))
                for label in OUTPUT_ITEMS.values()
            },
        }
    return summary


def frozen_hashes(root: Path) -> dict[str, str]:
    paths = {
        "e1_HASHES": root / "formal_results/e1_final/HASHES.sha256",
        "e2a_HASHES": root / "formal_results/e2_final/e2a/HASHES.sha256",
        "e2a_diagnostics_HASHES": root / "formal_results/e2_final/e2a/diagnostics/HASHES.sha256",
        "e2a_recertification_HASHES": root / "formal_results/e2_final/e2a/recertification/HASHES.sha256",
    }
    return {name: sha256_file(path) for name, path in paths.items()}
