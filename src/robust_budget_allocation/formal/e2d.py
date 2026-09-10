"""Formal E2-D shortage-valuation and commodity-priority sensitivity support."""

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
from robust_budget_allocation.algorithms.qfr_numerical_validation import family_feasibility_threshold
from robust_budget_allocation.algorithms.qfr_state import QFRFirstStage
from robust_budget_allocation.data.qfr_data import QFRData
from robust_budget_allocation.formal.e2a import (
    BUDGET, ITEMS, OUTPUT_ITEMS, POLICIES, POLICY_TOLERANCE, SAMPLE_SHA256,
    baseline_identity_preflight, load_base_fixture, load_baseline, load_samples,
)
from robust_budget_allocation.formal.e2b import (
    _bool, frozen_hashes as _frozen_e1_e2a,
    quartile_distribution, serialize_result as _serialize_base, summarize_level,
)
from robust_budget_allocation.io.hashing import canonical_json_sha256, sha256_file


CASES: dict[str, dict[str, Any]] = {
    "E2D_BETA2": {"part": "D1", "beta": 2.0, "lambda": (1.0, 1.0, 1.0)},
    "E2D_BETA6": {"part": "D1", "beta": 6.0, "lambda": (1.0, 1.0, 1.0)},
    "E2D_LAMBDA_WATER": {"part": "D2", "beta": 4.0, "lambda": (1.5, 1.0, 1.0)},
    "E2D_LAMBDA_VACCINE": {"part": "D2", "beta": 4.0, "lambda": (1.0, 1.5, 1.0)},
    "E2D_LAMBDA_CRACKERS": {"part": "D2", "beta": 4.0, "lambda": (1.0, 1.0, 1.5)},
}
BASELINE_CASE = "E2D_BASELINE"
LEVEL_NAMES = {
    "E2D_BETA2": "BETA2", "E2D_BETA6": "BETA6",
    "E2D_LAMBDA_WATER": "LAMBDA_WATER",
    "E2D_LAMBDA_VACCINE": "LAMBDA_VACCINE",
    "E2D_LAMBDA_CRACKERS": "LAMBDA_CRACKERS",
}
LEVELS = ("NONE", "R0", "R1", "R2")
E2B_HASHES = Path("formal_results/e2_final/e2b/HASHES.sha256")
E2C_HASHES = Path("formal_results/e2_final/e2c/HASHES.sha256")


def frozen_hashes(root: Path) -> dict[str, str]:
    return {
        **_frozen_e1_e2a(root),
        "e2b_HASHES": sha256_file(root / E2B_HASHES),
        "e2c_HASHES": sha256_file(root / E2C_HASHES),
    }


def validate_e2d_design(root: Path) -> dict[str, Any]:
    report = baseline_identity_preflight(root)
    import json
    design = json.loads((root / "configs/final_formal_scientific_design_v1.json").read_text(encoding="utf-8"))
    d1 = design["E2"]["D1"]
    d2 = design["E2"]["D2"]
    if [float(v) for v in d1["beta"]] != [2.0, 4.0, 6.0]:
        raise ValueError("frozen E2-D1 beta design changed")
    expected = [[1.5, 1.0, 1.0], [1.0, 1.5, 1.0], [1.0, 1.0, 1.5]]
    if d2["cases"] != expected:
        raise ValueError("frozen E2-D2 lambda design changed")
    if int(d1["new_optimizations"]) + int(d2["new_optimizations"]) != 5000:
        raise ValueError("frozen E2-D run count changed")
    if FINAL_A1_IMPLEMENTATION_REVISION != "A1_FINAL_NO_MEMORY_V1_R1_WITNESS_GATED_INFEASIBLE_RETRY":
        raise ValueError("Final A1 implementation revision drift")
    return {
        **report, "scope": "FORMAL_E2D_PREFLIGHT_V1", "planned_new_runs": 5000,
        "baseline_reused_rows": 1000, "baseline_rerun": False, "budget": BUDGET,
        "cases": CASES, "frozen_hashes": frozen_hashes(root),
        "algorithm_identity": FINAL_A1_IDENTITY,
        "implementation_revision": FINAL_A1_IMPLEMENTATION_REVISION,
        "E3_runs": 0,
    }


def data_for_case_sample(
    base_payload: Mapping[str, Any], metadata: Mapping[str, Mapping[str, Any]],
    case_id: str, sample: Mapping[str, Any],
) -> QFRData:
    if case_id not in CASES:
        raise ValueError(f"unknown E2-D case: {case_id}")
    payload = deepcopy(dict(base_payload))
    payload["budget"] = BUDGET
    payload["reservation_cost"] = {
        item: float(sample["phi"]) * float(payload["q_unit_cost"][item]) for item in ITEMS
    }
    payload["exercise_cost"] = {
        item: float(sample["psi"]) * float(payload["q_unit_cost"][item]) for item in ITEMS
    }
    payload["reliability_cost"] = {
        item: {"0": 0.0,
               "1": float(sample["c_R1_ratio"]) * float(payload["q_unit_cost"][item]),
               "2": float(sample["c_R2_ratio"]) * float(payload["q_unit_cost"][item])}
        for item in ITEMS
    }
    payload["reliability_mitigation"] = {
        item: {"0": 0.0, "1": float(sample["eta_1"]), "2": float(sample["eta_2"])} for item in ITEMS
    }
    for scenario in payload["scenarios"]:
        category = int(metadata[scenario]["category"])
        payload["q_availability"][scenario] = dict.fromkeys(ITEMS, float(sample[f"rho_Q{category}"]))
        payload["disruption"][scenario] = dict.fromkeys(ITEMS, 1.0 - float(sample[f"rho_F{category}"]))
    treatment = CASES[case_id]
    lambdas = dict(zip(ITEMS, treatment["lambda"], strict=True))
    payload["shortage_cost"] = {
        item: float(treatment["beta"]) * float(payload["q_unit_cost"][item]) * float(lambdas[item])
        for item in ITEMS
    }
    result = QFRData.from_dict(payload)
    if not math.isclose(result.storage_cost["Seasonal Influenza Vaccine"] * result.tau, .5, abs_tol=1e-12):
        raise ValueError("E2-D Vaccine baseline drift")
    if not math.isclose(result.retention["Crackers"], .9, abs_tol=1e-12):
        raise ValueError("E2-D Crackers baseline drift")
    return result


def serialize_result(
    case_id: str, sample: Mapping[str, Any], data: QFRData,
    metadata: Mapping[str, Mapping[str, Any]], result: Mapping[str, Any],
) -> dict[str, Any]:
    row = _serialize_base("E2B_B075", sample, data, metadata, result)
    treatment = CASES[case_id]
    row.update(
        experiment_part=treatment["part"], case_id=case_id, budget_ratio=1.0,
        budget=BUDGET, beta=treatment["beta"],
        lambda_Water=treatment["lambda"][0],
        lambda_Vaccine=treatment["lambda"][1],
        lambda_Crackers=treatment["lambda"][2],
    )
    if row.get("certificate_status") == "PASS":
        first_stage = result["incumbent"]["first_stage"]
        decision = QFRFirstStage.from_dict(first_stage)
        worst_id = result["incumbent"]["oracle"]["worst_scenario"]
        worst = next(v for v in result["incumbent"]["oracle"]["results"] if v["scenario_id"] == worst_id)
        row["normalized_shortage_value"] = float(row["worst_shortage_penalty"]) / float(treatment["beta"])
        for item, label in OUTPUT_ITEMS.items():
            row[f"C_Q_{label}"] = (data.q_unit_cost[item] + data.storage_cost[item] * data.tau) * decision.q[item]
            row[f"C_F_{label}"] = sum(data.reservation_cost[item] * decision.f[item][r] for r in decision.reliability_levels)
            row[f"C_R_{label}"] = sum(data.reliability_cost[item][r] * decision.f[item][r] for r in decision.reliability_levels)
            row[f"weighted_shortage_loss_{label}"] = data.shortage_cost[item] * float(worst["shortage"][item])
            row[f"worst_exercise_{label}"] = float(worst["exercise"][item])
    row["row_sha256"] = canonical_json_sha256({k: v for k, v in row.items() if k != "row_sha256"})
    return row


def solve_one(root: Path, case_id: str, sample: Mapping[str, Any]) -> dict[str, Any]:
    payload, metadata = load_base_fixture(root)
    data = data_for_case_sample(payload, metadata, case_id, sample)
    return serialize_result(case_id, sample, data, metadata, solve_qfr_final_a1(data, "M2"))


def baseline_rows(root: Path) -> list[dict[str, Any]]:
    payload, _ = load_base_fixture(root)
    rows: list[dict[str, Any]] = []
    samples = load_samples(root)
    for source, sample in zip(load_baseline(root), samples, strict=True):
        row = dict(source)
        row.update(case_id=BASELINE_CASE, experiment_part="BASELINE", beta=4.0,
                   lambda_Water=1.0, lambda_Vaccine=1.0, lambda_Crackers=1.0,
                   budget=BUDGET, budget_ratio=1.0)
        row["mixed_aggregate_QF"] = row["policy_label"] in {"P2", "P3a", "P3b"}
        row["budget_spend"] = float(row["budget_usage"]) * BUDGET
        row["budget_residual"] = BUDGET - row["budget_spend"]
        row["Q_budget_share"] = float(row["C_Q"]) / BUDGET
        row["F_reservation_budget_share"] = float(row["C_F"]) / BUDGET
        row["R_budget_share"] = float(row["C_R"]) / BUDGET
        row["emergency_budget_share"] = float(row["worst_exercise_cost"]) / BUDGET
        row["normalized_shortage_value"] = float(row["worst_shortage_penalty"]) / 4.0
        for item, label in OUTPUT_ITEMS.items():
            row[f"weighted_shortage_loss_{label}"] = float(payload["shortage_cost"][item]) * float(row[f"worst_shortage_{label}"])
            q_cost = float(payload["q_unit_cost"][item]) + float(payload["storage_cost"][item]) * float(payload["tau"])
            row[f"C_Q_{label}"] = q_cost * float(row[f"Q_{label}"])
            row[f"C_F_{label}"] = float(sample["phi"]) * float(payload["q_unit_cost"][item]) * float(row[f"F_{label}"])
            r_level = str(row[f"R_{label}"])
            r_ratio = 0.0 if r_level in {"NONE", "R0"} else float(sample[f"c_{r_level}_ratio"])
            row[f"C_R_{label}"] = r_ratio * float(payload["q_unit_cost"][item]) * float(row[f"F_{label}"])
        rows.append(row)
    return rows


def _direction(before: float, after: float, family: str = "quantity_flow") -> str:
    scale = max(abs(before), abs(after), 1.0)
    tol = 1e-7 + (1e-9 if family == "objective" else 1e-12) * scale
    delta = after - before
    return "unchanged" if abs(delta) <= tol else ("improved" if delta < 0 else "worsened")


def paired_rows(case_rows: Mapping[str, Sequence[Mapping[str, Any]]], baseline: Sequence[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    base = {str(r["simulation_id"]): r for r in baseline}
    indexed = {case: {str(r["simulation_id"]): r for r in rows} for case, rows in case_rows.items()}
    beta_rows: list[dict[str, Any]] = []
    priority_rows: list[dict[str, Any]] = []
    for index in range(1, 1001):
        sid = f"LA-{index:04d}"
        b = base[sid]
        low, high = indexed["E2D_BETA2"][sid], indexed["E2D_BETA6"][sid]
        if len({b["input_sha256"], low["input_sha256"], high["input_sha256"]}) != 1:
            raise ValueError(f"beta paired identity mismatch: {sid}")
        out: dict[str, Any] = {"simulation_id": sid, "sample_index": index, "input_sha256": b["input_sha256"]}
        for name, row in (("BETA2", low), ("BETA4", b), ("BETA6", high)):
            for field in ("policy_label", "T_COST", "worst_total_shortage", "worst_shortage_penalty",
                          "normalized_shortage_value", "budget_usage", "worst_scenario", "C_Q", "C_F", "C_R"):
                out[f"{name}_{field}"] = row[field]
            for label in OUTPUT_ITEMS.values():
                for field in ("Q", "F", "R", "worst_shortage", "weighted_shortage_loss"):
                    out[f"{name}_{field}_{label}"] = row[f"{field}_{label}"]
        for before, after in (("BETA2", "BETA4"), ("BETA4", "BETA6")):
            out[f"policy_transition_{before}_{after}"] = f"{out[f'{before}_policy_label']}->{out[f'{after}_policy_label']}"
            for field in ("T_COST", "worst_total_shortage", "worst_shortage_penalty", "normalized_shortage_value"):
                out[f"delta_{field}_{before}_{after}"] = float(out[f"{after}_{field}"]) - float(out[f"{before}_{field}"])
            for label in OUTPUT_ITEMS.values():
                out[f"R_transition_{label}_{before}_{after}"] = f"{out[f'{before}_R_{label}']}->{out[f'{after}_R_{label}']}"
        out["row_sha256"] = canonical_json_sha256(out)
        beta_rows.append(out)

        for case in ("E2D_LAMBDA_WATER", "E2D_LAMBDA_VACCINE", "E2D_LAMBDA_CRACKERS"):
            c = indexed[case][sid]
            if c["input_sha256"] != b["input_sha256"]:
                raise ValueError(f"priority paired identity mismatch: {case} {sid}")
            pr: dict[str, Any] = {"case_id": case, "simulation_id": sid, "sample_index": index, "input_sha256": b["input_sha256"]}
            pr["policy_transition"] = f"{b['policy_label']}->{c['policy_label']}"
            for field in ("T_COST", "worst_total_shortage", "worst_shortage_penalty", "normalized_shortage_value", "budget_usage"):
                pr[f"baseline_{field}"] = b[field]; pr[f"case_{field}"] = c[field]
                pr[f"delta_{field}"] = float(c[field]) - float(b[field])
            for label in OUTPUT_ITEMS.values():
                for field in ("Q", "F", "R", "worst_shortage", "weighted_shortage_loss"):
                    pr[f"baseline_{field}_{label}"] = b[f"{field}_{label}"]
                    pr[f"case_{field}_{label}"] = c[f"{field}_{label}"]
                    if field != "R": pr[f"delta_{field}_{label}"] = float(c[f"{field}_{label}"]) - float(b[f"{field}_{label}"])
                for cost in ("C_Q", "C_F", "C_R"):
                    pr[f"baseline_{cost}_{label}"] = b[f"{cost}_{label}"]
                    pr[f"case_{cost}_{label}"] = c[f"{cost}_{label}"]
                    pr[f"delta_{cost}_{label}"] = float(c[f"{cost}_{label}"]) - float(b[f"{cost}_{label}"])
            pr["row_sha256"] = canonical_json_sha256(pr)
            priority_rows.append(pr)
    return beta_rows, priority_rows


def summarize_all(case_rows: Mapping[str, Sequence[Mapping[str, Any]]], baseline: Sequence[Mapping[str, Any]], beta_pairs: Sequence[Mapping[str, Any]], priority_pairs: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    levels = {"BETA4_BASELINE": baseline, **{LEVEL_NAMES[k]: v for k, v in case_rows.items()}}
    summaries = {name: summarize_level(rows) for name, rows in levels.items()}
    for name, rows in levels.items():
        summaries[name]["weighted_shortage_loss"] = quartile_distribution([float(r["worst_shortage_penalty"]) for r in rows])
        summaries[name]["normalized_shortage_value"] = quartile_distribution([float(r["normalized_shortage_value"]) for r in rows])
    beta_transitions = {
        comparison: dict(Counter(str(r[f"policy_transition_{comparison}"]) for r in beta_pairs))
        for comparison in ("BETA2_BETA4", "BETA4_BETA6")
    }
    beta_paired = {}
    for comparison in ("BETA2_BETA4", "BETA4_BETA6"):
        before, after = comparison.split("_")
        beta_paired[comparison] = {}
        for field, family in (("T_COST", "objective"), ("worst_total_shortage", "quantity_flow"),
                              ("worst_shortage_penalty", "objective"), ("normalized_shortage_value", "objective")):
            deltas = [float(r[f"delta_{field}_{comparison}"]) for r in beta_pairs]
            dirs = [_direction(float(r[f"{before}_{field}"]), float(r[f"{after}_{field}"]), family) for r in beta_pairs]
            beta_paired[comparison][field] = {"delta": quartile_distribution(deltas), "direction": dict(Counter(dirs))}
    priority_analysis: dict[str, Any] = {}
    tradeoff: list[dict[str, Any]] = []
    for case in ("E2D_LAMBDA_WATER", "E2D_LAMBDA_VACCINE", "E2D_LAMBDA_CRACKERS"):
        rows = [r for r in priority_pairs if r["case_id"] == case]
        priority_analysis[case] = {
            "policy_transitions": dict(Counter(str(r["policy_transition"]) for r in rows)),
            "T_COST_delta": quartile_distribution([float(r["delta_T_COST"]) for r in rows]),
            "shortage_delta": quartile_distribution([float(r["delta_worst_total_shortage"]) for r in rows]),
        }
        for label in OUTPUT_ITEMS.values():
            rec = {"priority_case": case, "outcome_commodity": label}
            for field in ("Q", "F", "worst_shortage", "weighted_shortage_loss"):
                vals = [float(r[f"delta_{field}_{label}"]) for r in rows]
                rec[f"mean_delta_{field}"] = sum(vals) / len(vals)
                rec[f"median_delta_{field}"] = quartile_distribution(vals)["median"]
                directions = [_direction(float(r[f"baseline_{field}_{label}"]), float(r[f"case_{field}_{label}"])) for r in rows]
                if field in {"Q", "F"}:
                    rec[f"increased_{field}"] = directions.count("worsened")
                    rec[f"unchanged_{field}"] = directions.count("unchanged")
                    rec[f"decreased_{field}"] = directions.count("improved")
                else:
                    rec[f"improved_{field}"] = directions.count("improved")
                    rec[f"unchanged_{field}"] = directions.count("unchanged")
                    rec[f"worsened_{field}"] = directions.count("worsened")
            for cost in ("C_Q", "C_F", "C_R"):
                values = [float(r[f"delta_{cost}_{label}"]) for r in rows]
                rec[f"mean_delta_{cost}"] = sum(values) / len(values)
                rec[f"median_delta_{cost}"] = quartile_distribution(values)["median"]
            tradeoff.append(rec)
    return {"levels": summaries, "beta_policy_transitions": beta_transitions, "beta_paired": beta_paired,
            "priority": priority_analysis, "commodity_priority_tradeoff": tradeoff}
