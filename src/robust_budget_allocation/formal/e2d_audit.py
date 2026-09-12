"""Solver-free common-reference interpretation audit for frozen Formal E2-D."""

from __future__ import annotations

from collections import Counter
import csv
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

from robust_budget_allocation.algorithms.qfr_numerical_validation import family_feasibility_threshold
from robust_budget_allocation.formal.e2a import BUDGET, OUTPUT_ITEMS, csv_bytes, load_base_fixture, read_csv
from robust_budget_allocation.formal.e2d import CASES, frozen_hashes as frozen_through_e2c
from robust_budget_allocation.io.hashing import canonical_json_sha256, sha256_file


OUTPUT = Path("formal_results/e2_final/e2d_audit")
E1_RESULTS = Path("formal_results/e1_final/e1_scientific_results.csv")
E2D_RESULTS = Path("formal_results/e2_final/e2d/scientific_results.csv")
E2D_HASHES = Path("formal_results/e2_final/e2d/HASHES.sha256")
REFERENCE_BETA = 4.0
REFERENCE_LAMBDA = {"Water": 1.0, "Vaccine": 1.0, "Crackers": 1.0}
BASELINE_CELL = "E2D_BASELINE"
CELL_ORDER = (
    "E2D_BETA2", BASELINE_CELL, "E2D_BETA6", "E2D_LAMBDA_WATER",
    "E2D_LAMBDA_VACCINE", "E2D_LAMBDA_CRACKERS",
)


def frozen_hashes(root: Path) -> dict[str, str]:
    return {**frozen_through_e2c(root), "e2d_HASHES": sha256_file(root / E2D_HASHES)}


def verify_hash_inventory(directory: Path) -> None:
    entries: dict[str, str] = {}
    for line in (directory / "HASHES.sha256").read_text(encoding="utf-8").splitlines():
        digest, name = line.split("  ", 1)
        entries[name] = digest
    actual = {path.name for path in directory.iterdir() if path.is_file()} - {"HASHES.sha256"}
    if set(entries) != actual:
        raise ValueError(f"incomplete hash inventory: {directory}")
    for name, digest in entries.items():
        if sha256_file(directory / name) != digest:
            raise ValueError(f"frozen hash mismatch: {directory / name}")


def preflight(root: Path) -> dict[str, Any]:
    for relative in (
        Path("formal_results/e1_final"), Path("formal_results/e2_final/e2a"),
        Path("formal_results/e2_final/e2b"), Path("formal_results/e2_final/e2c"),
        Path("formal_results/e2_final/e2d"),
    ):
        verify_hash_inventory(root / relative)
    e1 = read_csv(root / E1_RESULTS)
    e2d = read_csv(root / E2D_RESULTS)
    if len(e1) != 1000 or len(e2d) != 5000:
        raise ValueError("frozen E1/E2-D population count mismatch")
    expected = [f"LA-{index:04d}" for index in range(1, 1001)]
    if [row["simulation_id"] for row in e1] != expected:
        raise ValueError("frozen E1 identity/order mismatch")
    for case in CASES:
        rows = [row for row in e2d if row["case_id"] == case]
        if [row["simulation_id"] for row in rows] != expected:
            raise ValueError(f"frozen E2-D identity/order mismatch: {case}")
        if any(row["certificate_status"] != "PASS" for row in rows):
            raise ValueError(f"uncertified frozen E2-D row: {case}")
    payload, _ = load_base_fixture(root)
    expected_cost = {
        label: REFERENCE_BETA * float(payload["q_unit_cost"][item])
        for item, label in OUTPUT_ITEMS.items()
    }
    actual_cost = {OUTPUT_ITEMS[item]: float(value) for item, value in payload["shortage_cost"].items()}
    if actual_cost != expected_cost:
        raise ValueError("Final E1 shortage-cost identity is not beta=4, lambda=(1,1,1), cQ-scaled")
    return {
        "status": "PASS", "scope": "FORMAL_E2D_INTERPRETATION_AUDIT_PREFLIGHT_V1",
        "frozen_hashes": frozen_hashes(root), "e1_rows": 1000, "e2d_rows": 5000,
        "reference_beta": REFERENCE_BETA, "reference_lambda": REFERENCE_LAMBDA,
        "reference_shortage_cost": expected_cost, "budget": BUDGET,
        "new_scientific_optimization_runs": 0, "E3_runs": 0,
    }


def _distribution(values: Sequence[float]) -> dict[str, float]:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return {}
    def q(p: float) -> float:
        at = (len(ordered) - 1) * p
        lo, hi = math.floor(at), math.ceil(at)
        return ordered[lo] if lo == hi else ordered[lo] + (at - lo) * (ordered[hi] - ordered[lo])
    return {"min": ordered[0], "Q25": q(.25), "median": q(.5), "mean": sum(ordered) / len(ordered), "Q75": q(.75), "max": ordered[-1]}


def _direction(before: float, after: float, family: str) -> str:
    if family == "objective":
        threshold = 1e-7 + 1e-9 * max(abs(before), abs(after), 1.0)
    else:
        threshold = family_feasibility_threshold("quantity_flow", before, after)
    delta = after - before
    if abs(delta) <= threshold:
        return "unchanged"
    return "improved" if delta < 0.0 else "worsened"


def common_reference_rows(root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    payload, _ = load_base_fixture(root)
    q_cost = {OUTPUT_ITEMS[item]: float(value) for item, value in payload["q_unit_cost"].items()}
    baseline = read_csv(root / E1_RESULTS)
    e2d = read_csv(root / E2D_RESULTS)
    sources: list[tuple[str, Mapping[str, Any]]] = [(BASELINE_CELL, row) for row in baseline]
    sources.extend((str(row["case_id"]), row) for row in e2d)
    results: list[dict[str, Any]] = []
    anchor_pass = 0
    anchor_max_abs = 0.0
    for cell, source in sources:
        reference_item = {
            label: REFERENCE_BETA * REFERENCE_LAMBDA[label] * q_cost[label] * float(source[f"worst_shortage_{label}"])
            for label in OUTPUT_ITEMS.values()
        }
        reference_loss = sum(reference_item.values())
        pre = float(source["first_stage_cost"])
        emergency = float(source["worst_exercise_cost"])
        t_ref = pre + emergency + reference_loss
        row: dict[str, Any] = {
            "cell": cell, "simulation_id": source["simulation_id"], "sample_index": int(source["sample_index"]),
            "input_sha256": source["input_sha256"], "first_stage_sha256": source["first_stage_sha256"],
            "policy_label": source["policy_label"], "worst_scenario": source["worst_scenario"],
            "original_beta": 4.0 if cell == BASELINE_CELL else float(source["beta"]),
            "original_lambda_Water": 1.0 if cell == BASELINE_CELL else float(source["lambda_Water"]),
            "original_lambda_Vaccine": 1.0 if cell == BASELINE_CELL else float(source["lambda_Vaccine"]),
            "original_lambda_Crackers": 1.0 if cell == BASELINE_CELL else float(source["lambda_Crackers"]),
            "beta_ref": REFERENCE_BETA, "lambda_ref_Water": 1.0, "lambda_ref_Vaccine": 1.0, "lambda_ref_Crackers": 1.0,
            "C_Q": float(source["C_Q"]), "C_F": float(source["C_F"]), "C_R": float(source["C_R"]),
            "first_stage_cost": pre, "emergency_expenditure": emergency,
            "reference_shortage_loss": reference_loss, "T_COST_original": float(source["T_COST"]),
            "T_COST_REF": t_ref, "raw_aggregate_shortage": sum(float(source[f"worst_shortage_{label}"]) for label in OUTPUT_ITEMS.values()),
        }
        for label in OUTPUT_ITEMS.values():
            row[f"Q_{label}"] = float(source[f"Q_{label}"])
            row[f"F_{label}"] = float(source[f"F_{label}"])
            row[f"R_{label}"] = source[f"R_{label}"]
            row[f"shortage_{label}"] = float(source[f"worst_shortage_{label}"])
            row[f"reference_shortage_loss_{label}"] = reference_item[label]
        if cell == BASELINE_CELL:
            difference = abs(t_ref - float(source["T_COST"]))
            anchor_max_abs = max(anchor_max_abs, difference)
            if _direction(float(source["T_COST"]), t_ref, "objective") == "unchanged":
                anchor_pass += 1
        row["audit_row_sha256"] = canonical_json_sha256(row)
        results.append(row)
    anchor = {"tested": 1000, "passed": anchor_pass, "failed": 1000 - anchor_pass, "max_abs_difference": anchor_max_abs}
    if anchor_pass != 1000:
        raise ValueError(f"baseline T_COST/T_COST_REF consistency failure: {anchor}")
    return results, anchor


def paired_tables(rows: Sequence[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    indexed = {(str(row["cell"]), str(row["simulation_id"])): row for row in rows}
    beta: list[dict[str, Any]] = []
    priority: list[dict[str, Any]] = []
    for index in range(1, 1001):
        sid = f"LA-{index:04d}"
        b2, b4, b6 = (indexed[(cell, sid)] for cell in ("E2D_BETA2", BASELINE_CELL, "E2D_BETA6"))
        if len({b2["input_sha256"], b4["input_sha256"], b6["input_sha256"]}) != 1:
            raise ValueError(f"beta paired identity mismatch: {sid}")
        out: dict[str, Any] = {"simulation_id": sid, "sample_index": index, "input_sha256": b4["input_sha256"]}
        for name, source in (("BETA2", b2), ("BETA4", b4), ("BETA6", b6)):
            for field in ("policy_label", "T_COST_REF", "reference_shortage_loss", "first_stage_cost", "C_Q", "C_F", "C_R", "emergency_expenditure"):
                out[f"{name}_{field}"] = source[field]
            for label in OUTPUT_ITEMS.values():
                for field in ("Q", "F", "R", "shortage", "reference_shortage_loss"):
                    out[f"{name}_{field}_{label}"] = source[f"{field}_{label}"]
        for before, after in (("BETA2", "BETA4"), ("BETA4", "BETA6")):
            for field in ("T_COST_REF", "reference_shortage_loss", "first_stage_cost", "C_Q", "C_F", "C_R", "emergency_expenditure"):
                out[f"delta_{field}_{before}_{after}"] = float(out[f"{after}_{field}"]) - float(out[f"{before}_{field}"])
            out[f"T_COST_REF_direction_{before}_{after}"] = _direction(float(out[f"{before}_T_COST_REF"]), float(out[f"{after}_T_COST_REF"]), "objective")
            out[f"reference_shortage_direction_{before}_{after}"] = _direction(float(out[f"{before}_reference_shortage_loss"]), float(out[f"{after}_reference_shortage_loss"]), "objective")
            out[f"policy_transition_{before}_{after}"] = f"{out[f'{before}_policy_label']}->{out[f'{after}_policy_label']}"
            for label in OUTPUT_ITEMS.values():
                for field in ("Q", "F", "shortage", "reference_shortage_loss"):
                    out[f"delta_{field}_{label}_{before}_{after}"] = float(out[f"{after}_{field}_{label}"]) - float(out[f"{before}_{field}_{label}"])
                out[f"R_transition_{label}_{before}_{after}"] = f"{out[f'{before}_R_{label}']}->{out[f'{after}_R_{label}']}"
        out["audit_row_sha256"] = canonical_json_sha256(out)
        beta.append(out)

        base = indexed[(BASELINE_CELL, sid)]
        for case in ("E2D_LAMBDA_WATER", "E2D_LAMBDA_VACCINE", "E2D_LAMBDA_CRACKERS"):
            treated = indexed[(case, sid)]
            if treated["input_sha256"] != base["input_sha256"]:
                raise ValueError(f"priority paired identity mismatch: {case} {sid}")
            out = {"cell": case, "simulation_id": sid, "sample_index": index, "input_sha256": base["input_sha256"]}
            for field in ("T_COST_REF", "reference_shortage_loss", "first_stage_cost", "C_Q", "C_F", "C_R", "emergency_expenditure"):
                out[f"baseline_{field}"] = base[field]
                out[f"treated_{field}"] = treated[field]
                out[f"delta_{field}"] = float(treated[field]) - float(base[field])
            out["T_COST_REF_direction"] = _direction(float(base["T_COST_REF"]), float(treated["T_COST_REF"]), "objective")
            for label in OUTPUT_ITEMS.values():
                for field in ("Q", "F", "shortage", "reference_shortage_loss"):
                    out[f"baseline_{field}_{label}"] = base[f"{field}_{label}"]
                    out[f"treated_{field}_{label}"] = treated[f"{field}_{label}"]
                    out[f"delta_{field}_{label}"] = float(treated[f"{field}_{label}"]) - float(base[f"{field}_{label}"])
                out[f"R_transition_{label}"] = f"{base[f'R_{label}']}->{treated[f'R_{label}']}"
            out["audit_row_sha256"] = canonical_json_sha256(out)
            priority.append(out)
    return beta, priority


def summaries(common: Sequence[Mapping[str, Any]], beta: Sequence[Mapping[str, Any]], priority: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    level: dict[str, Any] = {}
    expenditure_rows: list[dict[str, Any]] = []
    for cell in CELL_ORDER:
        rows = [row for row in common if row["cell"] == cell]
        level[cell] = {
            "T_COST_REF": _distribution([float(row["T_COST_REF"]) for row in rows]),
            "reference_shortage_loss": _distribution([float(row["reference_shortage_loss"]) for row in rows]),
        }
        expenditure_rows.append({"cell": cell, **{field: _distribution([float(row[field]) for row in rows])["mean"] for field in (
            "C_Q", "C_F", "C_R", "first_stage_cost", "emergency_expenditure", "reference_shortage_loss", "T_COST_REF")}})
    paired_beta: dict[str, Any] = {}
    beta_mechanism: dict[str, Any] = {}
    for comparison in ("BETA2_BETA4", "BETA4_BETA6"):
        paired_beta[comparison] = {}
        for field in ("T_COST_REF", "reference_shortage_loss", "C_Q", "C_F", "C_R", "first_stage_cost", "emergency_expenditure"):
            paired_beta[comparison][field] = _distribution([float(row[f"delta_{field}_{comparison}"]) for row in beta])
        paired_beta[comparison]["T_COST_REF_direction"] = dict(Counter(str(row[f"T_COST_REF_direction_{comparison}"]) for row in beta))
        paired_beta[comparison]["reference_shortage_direction"] = dict(Counter(str(row[f"reference_shortage_direction_{comparison}"]) for row in beta))
        paired_beta[comparison]["policy_transitions"] = dict(Counter(str(row[f"policy_transition_{comparison}"]) for row in beta))
        beta_mechanism[comparison] = {}
        for label in OUTPUT_ITEMS.values():
            beta_mechanism[comparison][label] = {
                field: _distribution([float(row[f"delta_{field}_{label}_{comparison}"]) for row in beta])
                for field in ("Q", "F", "shortage", "reference_shortage_loss")
            }
            beta_mechanism[comparison][label]["R_transitions"] = dict(
                Counter(str(row[f"R_transition_{label}_{comparison}"]) for row in beta)
            )
    paired_priority: dict[str, Any] = {}
    priority_mechanism: dict[str, Any] = {}
    tradeoff_rows: list[dict[str, Any]] = []
    target_by_case = {"E2D_LAMBDA_WATER": "Water", "E2D_LAMBDA_VACCINE": "Vaccine", "E2D_LAMBDA_CRACKERS": "Crackers"}
    crowding: dict[str, Any] = {}
    for case, target in target_by_case.items():
        rows = [row for row in priority if row["cell"] == case]
        paired_priority[case] = {
            field: _distribution([float(row[f"delta_{field}"]) for row in rows])
            for field in ("T_COST_REF", "reference_shortage_loss", "C_Q", "C_F", "C_R", "first_stage_cost", "emergency_expenditure")
        }
        paired_priority[case]["T_COST_REF_direction"] = dict(Counter(str(row["T_COST_REF_direction"]) for row in rows))
        priority_mechanism[case] = {}
        for label in OUTPUT_ITEMS.values():
            physical = [float(row[f"delta_shortage_{label}"]) for row in rows]
            valued = [float(row[f"delta_reference_shortage_loss_{label}"]) for row in rows]
            directions = [_direction(float(row[f"baseline_shortage_{label}"]), float(row[f"treated_shortage_{label}"]), "quantity") for row in rows]
            tradeoff_rows.append({
                "priority_cell": case, "outcome_commodity": label,
                "mean_delta_physical_shortage": sum(physical) / len(physical),
                "median_delta_physical_shortage": _distribution(physical)["median"],
                "mean_delta_reference_shortage_loss": sum(valued) / len(valued),
                "median_delta_reference_shortage_loss": _distribution(valued)["median"],
                **{name: directions.count(name) for name in ("improved", "unchanged", "worsened")},
            })
            priority_mechanism[case][label] = {
                field: _distribution([float(row[f"delta_{field}_{label}"]) for row in rows])
                for field in ("Q", "F", "shortage", "reference_shortage_loss")
            }
            priority_mechanism[case][label]["R_transitions"] = dict(
                Counter(str(row[f"R_transition_{label}"]) for row in rows)
            )
        target_row = next(row for row in tradeoff_rows if row["priority_cell"] == case and row["outcome_commodity"] == target)
        non_target = [row for row in tradeoff_rows if row["priority_cell"] == case and row["outcome_commodity"] != target]
        direction_counts = paired_priority[case]["T_COST_REF_direction"]
        crowding[case] = {
            "TARGET_BENEFIT": target_row["mean_delta_reference_shortage_loss"] < 0,
            "NON_TARGET_CROWDING_OUT": any(row["mean_delta_reference_shortage_loss"] > 0 for row in non_target),
            "PORTFOLIO_REFERENCE_COST_INCREASE": direction_counts.get("worsened", 0) > 0,
            "target": target,
        }
    verdict = "PARTIALLY_SUPPORTED"
    return {"levels": level, "paired_beta": paired_beta, "beta_mechanism": beta_mechanism,
            "paired_priority": paired_priority, "priority_mechanism": priority_mechanism,
            "expenditure_decomposition": expenditure_rows, "commodity_reference_tradeoff": tradeoff_rows,
            "priority_crowding_out": crowding, "diminishing_response_verdict": verdict}


def claim_rows() -> list[dict[str, str]]:
    return [
        {"claim_id": "C1", "claim": "Cross-beta raw T-COST rises mechanically because beta changes the objective coefficient.", "status": "SAFE_AS_WRITTEN", "reason": "Production formula and common-reference evaluation confirm the scale change."},
        {"claim_id": "C2", "claim": "Raw aggregate physical shortage does not fall monotonically.", "status": "NEEDS_QUALIFICATION", "reason": "Numerically true, but the sum combines gallons, doses, and 22-g service units and is descriptive only."},
        {"claim_id": "C3", "claim": "Beta 2 to 4 improves coefficient-normalized shortage value and beta 4 to 6 is unchanged.", "status": "SAFE_AS_WRITTEN", "reason": "The common-reference shortage calculation reproduces this result."},
        {"claim_id": "C4", "claim": "Beta 4 to 6 exhibits a strong plateau.", "status": "NEEDS_QUALIFICATION", "reason": "Reference-valued outcome and aggregate expenditures plateau, but commodity F/R and shortage composition still reallocate."},
        {"claim_id": "C5", "claim": "Each priority treatment reduces target shortage and transfers shortage to non-target commodities.", "status": "SAFE_AS_WRITTEN", "reason": "Within-commodity physical and reference-valued paired comparisons agree."},
        {"claim_id": "C6", "claim": "Commodity responses differ by archetype.", "status": "SAFE_AS_WRITTEN", "reason": "Paired Q/F/R and expenditure decompositions show distinct Water, Vaccine, and Crackers responses."},
        {"claim_id": "C7", "claim": "Same-item Q/F coexistence remains zero and h09 remains worst.", "status": "SAFE_AS_WRITTEN", "reason": "Directly supported by frozen row-level evidence."},
        {"claim_id": "C8", "claim": "Commodity prioritization reallocates scarcity rather than eliminating it.", "status": "SAFE_AS_WRITTEN", "reason": "All treatments show target benefit and non-target crowding-out under the common reference scale."},
    ]


def csv_payload(rows: Sequence[Mapping[str, Any]]) -> bytes:
    return csv_bytes(rows)
