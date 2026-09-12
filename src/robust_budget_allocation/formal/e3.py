"""Frozen Formal E3 targeted-interaction experiment support."""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

from robust_budget_allocation.algorithms.qfr_final_a1 import (
    FINAL_A1_IDENTITY, FINAL_A1_IMPLEMENTATION_REVISION, solve_qfr_final_a1,
)
from robust_budget_allocation.data.qfr_data import QFRData
from robust_budget_allocation.formal.e2a import (
    BUDGET, ITEMS, OUTPUT_ITEMS, POLICIES, POLICY_TOLERANCE, SAMPLE_SHA256,
    csv_bytes, load_base_fixture, load_samples, read_csv,
)
from robust_budget_allocation.formal.e2b import serialize_result as _serialize_base
from robust_budget_allocation.formal.e2d_audit import verify_hash_inventory
from robust_budget_allocation.formal.final_design import (
    canonical_sha256, select_f_supply_risk, select_reliability_economics,
    select_space_filling, selection_identity,
)
from robust_budget_allocation.io.hashing import canonical_json_sha256, sha256_file


DESIGN = Path("configs/final_formal_scientific_design_v1.json")
MACHINE = Path("docs/evidence/FINAL_FORMAL_MACHINE_IDENTITIES_v1.json")
E1_RESULTS = Path("formal_results/e1_final/e1_scientific_results.csv")
E2D_AUDIT_HASHES = Path("formal_results/e2_final/e2d_audit/HASHES.sha256")
EXPECTED_S200 = "2b7d7a92c9a0301203a6b73a349a32903b83434038dc88a52fe1cc734ffad32d"
EXPECTED_S100 = "1ad7dcbf17a2339a41723bea60ad0e7e8fce70017d54c5c1f80ba7412accd0ee"
EXPECTED_REVISION = "A1_FINAL_NO_MEMORY_V1_R1_WITNESS_GATED_INFEASIBLE_RETRY"
E3A_H = (0.0, 0.5, 1.0)
E3A_MF = (0.8, 1.0, 1.2)
F_PAIR = {0.8: (0.16, 0.68), 1.0: (0.20, 0.85), 1.2: (0.24, 1.02)}
RISK_LEVELS = ("Low", "Medium", "High")
RELIABILITY_LEVELS = ("Unfavorable", "Reference", "Favorable")


def e3a_case(h: float, mf: float) -> str:
    return f"E3A_H{int(round(h * 100)):03d}_MF{int(round(mf * 100)):03d}"


def e3b_case(risk: str, reliability: str) -> str:
    return f"E3B_{risk.upper()}_{reliability.upper()}"


E3A_CASES = {e3a_case(h, mf): {"h_V_tau": h, "m_F": mf, "phi": F_PAIR[mf][0], "psi": F_PAIR[mf][1]} for h in E3A_H for mf in E3A_MF}
E3B_CASES = {e3b_case(risk, rel): {"F_risk": risk, "reliability_economics": rel} for risk in RISK_LEVELS for rel in RELIABILITY_LEVELS}


def _load(root: Path, path: Path) -> dict[str, Any]:
    return json.loads((root / path).read_text(encoding="utf-8"))


def _frozen_hashes(root: Path) -> dict[str, str]:
    directories = (
        "formal_results/e1_final", "formal_results/e2_final/e2a",
        "formal_results/e2_final/e2b", "formal_results/e2_final/e2c",
        "formal_results/e2_final/e2d", "formal_results/e2_final/e2d_audit",
    )
    result = {}
    for relative in directories:
        directory = root / relative
        verify_hash_inventory(directory)
        result[relative] = sha256_file(directory / "HASHES.sha256")
    return result


def preflight(root: Path) -> dict[str, Any]:
    design, machine = _load(root, DESIGN), _load(root, MACHINE)
    common, e1, e3 = design["common"], design["E1"], design["E3"]
    if common["dataset"] != "rawls_24_real_single_hurricane_data_recalibration_v1" or common["scenario_order"] != [f"h{i:02d}" for i in range(1, 25)]:
        raise ValueError("Rawls24 identity mismatch")
    if common["commodities"] != list(ITEMS) or common["model"] != "M2":
        raise ValueError("E3 model/commodity identity mismatch")
    if float(common["B_ref_E1"]) != BUDGET or float(common["beta"]) != 4.0 or common["lambda"] != [1.0, 1.0, 1.0] or float(common["gamma_D"]) != 1.0:
        raise ValueError("E3 frozen baseline mismatch")
    if e1["sample_table_sha256"] != SAMPLE_SHA256 or int(e1["seed"]) != 20260903:
        raise ValueError("E1 sample identity mismatch")
    if design["algorithm"]["identity"] != FINAL_A1_IDENTITY or FINAL_A1_IMPLEMENTATION_REVISION != EXPECTED_REVISION:
        raise ValueError("Final A1 identity/revision mismatch")
    if e3["A"]["h_V_tau"] != [0.0, 0.5, 1.0] or e3["A"]["m_F"] != [0.8, 1.0, 1.2] or e3["A"]["phi_psi"] != [[0.16, 0.68], [0.2, 0.85], [0.24, 1.02]]:
        raise ValueError("E3-A treatment grid mismatch")
    samples = load_samples(root)
    rebuilt_s200 = select_space_filling(samples, e1["bounds"], 200)
    s200 = selection_identity(rebuilt_s200, SAMPLE_SHA256, "E3_E4A_SHARED_S200")
    by_id = {int(row["sample_index"]): row for row in samples}
    rebuilt_s100 = select_space_filling([by_id[index] for index in rebuilt_s200], e1["bounds"], 100)
    s100 = selection_identity(rebuilt_s100, SAMPLE_SHA256, "E4B_NESTED_WITHIN_S200", s200["selection_sha256"])
    if s200 != machine["S_200"] or s200["selection_sha256"] != EXPECTED_S200:
        raise ValueError("S200 identity mismatch")
    if s100 != machine["S_100"] or s100["selection_sha256"] != EXPECTED_S100:
        raise ValueError("S100 identity mismatch")
    results = read_csv(root / E1_RESULTS)
    f_rows = [{"sample_index": row["sample_index"], **{f"F_{item}": row[f"F_{label}"] for item, label in OUTPUT_ITEMS.items()}} for row in results]
    supply = select_f_supply_risk(samples)
    reliability = select_reliability_economics(samples, f_rows, POLICY_TOLERANCE)
    for actual, expected, name in ((supply, machine["E3B_F_supply_risk"], "F-risk"), (reliability, machine["E3B_reliability_economics"], "reliability")):
        body = {k: v for k, v in expected.items() if k not in {"identity_sha256", "selected_full_rho_F_curves", "selected_actual_reliability_tuples"}}
        frozen_identity_body = {k: v for k, v in expected.items() if k != "identity_sha256"}
        if actual != body or canonical_sha256(frozen_identity_body) != expected["identity_sha256"]:
            raise ValueError(f"E3-B {name} representative mismatch")
    return {
        "status": "PASS", "scope": "FORMAL_E3_PREFLIGHT_V1", "frozen_hashes": _frozen_hashes(root),
        "sample_sha256": SAMPLE_SHA256, "S200_sha256": EXPECTED_S200, "S100_sha256": EXPECTED_S100,
        "S200_ids": rebuilt_s200, "S100_ids": rebuilt_s100,
        "algorithm_identity": FINAL_A1_IDENTITY, "implementation_revision": FINAL_A1_IMPLEMENTATION_REVISION,
        "E3A_cells": E3A_CASES, "E3B_cells": E3B_CASES,
        "E3B_F_risk": machine["E3B_F_supply_risk"], "E3B_reliability": machine["E3B_reliability_economics"],
        "E3B_design_recovery": {
            "status": "PASS", "background": "E3_E4A_SHARED_S200", "S100_used": False,
            "per_cell_sample_size": 200, "total_optimizations": 1800,
            "risk_donor_fields": [f"rho_F{k}" for k in range(1, 6)],
            "reliability_donor_fields": ["eta_1", "eta_2", "c_R1_ratio", "c_R2_ratio"],
            "background_fields": [f"rho_Q{k}" for k in range(1, 6)] + ["phi", "psi"],
            "fixed": {"B": BUDGET, "beta": 4.0, "lambda": [1.0, 1.0, 1.0], "gamma_D": 1.0, "h_V_tau": 0.5, "a_C": 0.9},
            "scenario_data": "Rawls24 h01-h24", "reliability_cost_mapping": "donor ratios multiplied by each commodity cQ",
        },
        "planned_E3A": 1800, "planned_E3B": 1800, "E4_runs": 0,
    }


def s200_samples(root: Path, report: Mapping[str, Any]) -> list[dict[str, Any]]:
    by_id = {int(row["sample_index"]): row for row in load_samples(root)}
    return [deepcopy(by_id[index]) for index in report["S200_ids"]]


def treatment_sample(part: str, case_id: str, background: Mapping[str, Any], report: Mapping[str, Any], all_samples: Mapping[int, Mapping[str, Any]]) -> dict[str, Any]:
    sample = deepcopy(dict(background))
    if part == "E3A":
        treatment = E3A_CASES[case_id]
        sample["phi"], sample["psi"] = treatment["phi"], treatment["psi"]
    else:
        treatment = E3B_CASES[case_id]
        risk_id = int(report["E3B_F_risk"]["levels"][treatment["F_risk"]])
        rel_id = int(report["E3B_reliability"]["levels"][treatment["reliability_economics"]])
        for k in range(1, 6): sample[f"rho_F{k}"] = float(all_samples[risk_id][f"rho_F{k}"])
        for field in ("eta_1", "eta_2", "c_R1_ratio", "c_R2_ratio"): sample[field] = float(all_samples[rel_id][field])
        sample["F_risk_donor_id"], sample["reliability_donor_id"] = f"LA-{risk_id:04d}", f"LA-{rel_id:04d}"
    return sample


def data_for_sample(base: Mapping[str, Any], metadata: Mapping[str, Mapping[str, Any]], part: str, case_id: str, sample: Mapping[str, Any]) -> QFRData:
    payload = deepcopy(dict(base))
    if part == "E3A":
        h = E3A_CASES[case_id]["h_V_tau"]
        if h != 0.5: payload["storage_cost"]["Seasonal Influenza Vaccine"] = h / float(payload["tau"])
    payload["budget"] = BUDGET
    payload["reservation_cost"] = {item: float(sample["phi"]) * float(payload["q_unit_cost"][item]) for item in ITEMS}
    payload["exercise_cost"] = {item: float(sample["psi"]) * float(payload["q_unit_cost"][item]) for item in ITEMS}
    payload["reliability_cost"] = {item: {"0": 0.0, "1": float(sample["c_R1_ratio"]) * float(payload["q_unit_cost"][item]), "2": float(sample["c_R2_ratio"]) * float(payload["q_unit_cost"][item])} for item in ITEMS}
    payload["reliability_mitigation"] = {item: {"0": 0.0, "1": float(sample["eta_1"]), "2": float(sample["eta_2"])} for item in ITEMS}
    for scenario in payload["scenarios"]:
        category = int(metadata[scenario]["category"])
        payload["q_availability"][scenario] = dict.fromkeys(ITEMS, float(sample[f"rho_Q{category}"]))
        payload["disruption"][scenario] = dict.fromkeys(ITEMS, 1.0 - float(sample[f"rho_F{category}"]))
    return QFRData.from_dict(payload)


def serialize(part: str, case_id: str, background: Mapping[str, Any], treated: Mapping[str, Any], data: QFRData, metadata: Mapping[str, Mapping[str, Any]], result: Mapping[str, Any]) -> dict[str, Any]:
    row = _serialize_base("E2B_B075", background, data, metadata, result)
    row.update(experiment_part=part, case_id=case_id, background_simulation_id=background["simulation_id"], background_sample_index=background["sample_index"], budget_ratio=1.0, budget=BUDGET, beta=4.0, lambda_Water=1.0, lambda_Vaccine=1.0, lambda_Crackers=1.0, gamma_D=1.0, h_V_tau=(E3A_CASES[case_id]["h_V_tau"] if part == "E3A" else 0.5), a_C=0.9, phi=float(treated["phi"]), psi=float(treated["psi"]), eta_1=float(treated["eta_1"]), eta_2=float(treated["eta_2"]), c_R1_ratio=float(treated["c_R1_ratio"]), c_R2_ratio=float(treated["c_R2_ratio"]))
    if part == "E3A": row["m_F"] = E3A_CASES[case_id]["m_F"]
    else:
        row.update(F_risk=E3B_CASES[case_id]["F_risk"], reliability_economics=E3B_CASES[case_id]["reliability_economics"], F_risk_donor_id=treated["F_risk_donor_id"], reliability_donor_id=treated["reliability_donor_id"])
    if row.get("certificate_status") == "PASS":
        for item, label in OUTPUT_ITEMS.items():
            row[f"shortage_loss_{label}"] = float(data.shortage_cost[item]) * float(row[f"worst_shortage_{label}"])
        row["paid_R_Vaccine"] = row["R_Vaccine"] in {"R1", "R2"}
        row["R_level_numeric_Vaccine"] = {"NONE": 0, "R0": 0, "R1": 1, "R2": 2}[row["R_Vaccine"]]
        row["F_total"] = sum(float(row[f"F_{label}"]) for label in OUTPUT_ITEMS.values())
        row["paid_R_any"] = any(row[f"R_{label}"] in {"R1", "R2"} for label in OUTPUT_ITEMS.values())
        row["R1_item_count"] = sum(row[f"R_{label}"] == "R1" for label in OUTPUT_ITEMS.values())
        row["R2_item_count"] = sum(row[f"R_{label}"] == "R2" for label in OUTPUT_ITEMS.values())
    row["row_sha256"] = canonical_json_sha256({k: v for k, v in row.items() if k != "row_sha256"})
    return row


def solve_one(root: Path, part: str, case_id: str, background: Mapping[str, Any], report: Mapping[str, Any]) -> dict[str, Any]:
    base, metadata = load_base_fixture(root)
    all_samples = {int(row["sample_index"]): row for row in load_samples(root)}
    treated = treatment_sample(part, case_id, background, report, all_samples)
    data = data_for_sample(base, metadata, part, case_id, treated)
    return serialize(part, case_id, background, treated, data, metadata, solve_qfr_final_a1(data, "M2"))


def distribution(values: Sequence[float]) -> dict[str, float]:
    ordered = sorted(map(float, values))
    def q(p: float) -> float:
        at = (len(ordered) - 1) * p; lo, hi = math.floor(at), math.ceil(at)
        return ordered[lo] if lo == hi else ordered[lo] + (at - lo) * (ordered[hi] - ordered[lo])
    return {"min": ordered[0], "Q25": q(.25), "median": q(.5), "mean": sum(ordered)/len(ordered), "Q75": q(.75), "max": ordered[-1]}


def summarize_cell(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {"N": len(rows), "policy_counts": dict(Counter(str(r["policy_label"]) for r in rows)), "worst_scenarios": dict(Counter(str(r["worst_scenario"]) for r in rows))}
    out["policy_counts"] = {p: out["policy_counts"].get(p, 0) for p in POLICIES}
    out["mixed_aggregate_QF"] = sum(str(r["mixed_aggregate_QF"]).lower() == "true" for r in rows)
    out["same_item_QF_coexistence"] = sum(str(r["same_item_QF_coexistence"]).lower() == "true" for r in rows)
    out["cross_item_specialization"] = sum(str(r["cross_item_specialization"]).lower() == "true" for r in rows)
    out["paid_R_cases"] = sum(str(r["paid_R_any"]).lower() == "true" for r in rows)
    out["R1_item_selections"] = sum(int(r["R1_item_count"]) for r in rows)
    out["R2_item_selections"] = sum(int(r["R2_item_count"]) for r in rows)
    out["outcomes"] = {field: distribution([float(r[field]) for r in rows]) for field in ("T_COST", "C_Q", "C_F", "C_R", "first_stage_cost", "worst_exercise_cost", "worst_shortage_penalty", "budget_usage")}
    out["outcomes"]["F_total"] = distribution([float(r["F_total"]) for r in rows])
    out["certification_diagnostics"] = {
        "iterations": distribution([float(r["iterations"]) for r in rows]),
        "full_exact_certification_calls": distribution([float(r["full_exact_certification_calls"]) for r in rows]),
        "witness_gated_retry_count": "unavailable_in_result_schema",
    }
    out["commodities"] = {}
    for label in OUTPUT_ITEMS.values():
        out["commodities"][label] = {"Q_active": sum(float(r[f"Q_{label}"]) > POLICY_TOLERANCE for r in rows), "F_active": sum(float(r[f"F_{label}"]) > POLICY_TOLERANCE for r in rows), "R": dict(Counter(str(r[f"R_{label}"]) for r in rows)), "Q": distribution([float(r[f"Q_{label}"]) for r in rows]), "F": distribution([float(r[f"F_{label}"]) for r in rows]), "shortage": distribution([float(r[f"worst_shortage_{label}"]) for r in rows]), "shortage_loss": distribution([float(r[f"shortage_loss_{label}"]) for r in rows])}
    return out


def _direction(value: float, scale: float) -> str:
    tol = 1e-7 + 1e-12 * max(abs(scale), 1.0)
    return "unchanged" if abs(value) <= tol else ("increased" if value > 0 else "decreased")


def _numeric(value: Any) -> float:
    """Convert a serialized scientific scalar or indicator deterministically."""
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, str) and value.lower() in {"true", "false"}:
        return 1.0 if value.lower() == "true" else 0.0
    return float(value)


def paired_panel(part: str, case_rows: Mapping[str, Sequence[Mapping[str, Any]]]) -> list[dict[str, Any]]:
    cases = E3A_CASES if part == "E3A" else E3B_CASES
    indexed = {case: {r["simulation_id"]: r for r in rows} for case, rows in case_rows.items()}
    panel = []
    sample_ids = [row["simulation_id"] for row in next(iter(case_rows.values()))]
    for position, sid in enumerate(sample_ids):
        row: dict[str, Any] = {"panel_index": position + 1, "simulation_id": sid}
        for case in cases:
            source = indexed[case][sid]
            for field in ("policy_label", "T_COST", "C_Q", "C_F", "C_R", "first_stage_cost", "worst_exercise_cost", "worst_shortage_penalty", "budget_usage", "worst_scenario", "Q_Vaccine", "F_Vaccine", "R_Vaccine", "paid_R_Vaccine", "R_level_numeric_Vaccine", "worst_shortage_Vaccine", "shortage_loss_Vaccine", "F_total", "paid_R_any", "R1_item_count", "R2_item_count"):
                row[f"{case}_{field}"] = source[field]
        row["row_sha256"] = canonical_json_sha256(row); panel.append(row)
    return panel


def contrasts(part: str, case_rows: Mapping[str, Sequence[Mapping[str, Any]]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    indexed = {case: {r["simulation_id"]: r for r in rows} for case, rows in case_rows.items()}
    ids = list(next(iter(indexed.values())))
    outcomes = ("Q_Vaccine", "F_Vaccine", "paid_R_Vaccine", "R_level_numeric_Vaccine", "worst_shortage_Vaccine", "shortage_loss_Vaccine", "T_COST", "C_Q", "C_F", "C_R") if part == "E3A" else ("F_total", "F_Water", "F_Vaccine", "F_Crackers", "paid_R_any", "R1_item_count", "R2_item_count", "worst_shortage_Water", "worst_shortage_Vaccine", "worst_shortage_Crackers", "worst_shortage_penalty", "T_COST", "budget_usage")
    main, interactions = [], []
    if part == "E3A":
        comparisons = []
        for mf in E3A_MF:
            for a,b in ((0.0,.5),(.5,1.0),(0.0,1.0)): comparisons.append((f"h:{a}->{b}|mF:{mf}", e3a_case(a,mf), e3a_case(b,mf)))
        for h in E3A_H:
            for a,b in ((.8,1.0),(1.0,1.2),(.8,1.2)): comparisons.append((f"mF:{a}->{b}|h:{h}", e3a_case(h,a), e3a_case(h,b)))
        rectangles = [("EXTREME",0.0,1.0,.8,1.2),("H0_050_M080_100",0.0,.5,.8,1.0),("H0_050_M100_120",0.0,.5,1.0,1.2),("H050_100_M080_100",.5,1.0,.8,1.0),("H050_100_M100_120",.5,1.0,1.0,1.2)]
        case_of=lambda h,m:e3a_case(h,m)
    else:
        comparisons=[]
        for rel in RELIABILITY_LEVELS:
            for a,b in (("Low","Medium"),("Medium","High"),("Low","High")): comparisons.append((f"risk:{a}->{b}|rel:{rel}",e3b_case(a,rel),e3b_case(b,rel)))
        for risk in RISK_LEVELS:
            for a,b in (("Unfavorable","Reference"),("Reference","Favorable"),("Unfavorable","Favorable")): comparisons.append((f"rel:{a}->{b}|risk:{risk}",e3b_case(risk,a),e3b_case(risk,b)))
        rectangles=[("EXTREME","Low","High","Unfavorable","Favorable"),("LOW_MED_UNF_REF","Low","Medium","Unfavorable","Reference"),("LOW_MED_REF_FAV","Low","Medium","Reference","Favorable"),("MED_HIGH_UNF_REF","Medium","High","Unfavorable","Reference"),("MED_HIGH_REF_FAV","Medium","High","Reference","Favorable")]
        case_of=lambda r,e:e3b_case(r,e)
    for name,before,after in comparisons:
        for outcome in outcomes:
            values=[_numeric(indexed[after][sid][outcome])-_numeric(indexed[before][sid][outcome]) for sid in ids]
            scale=max(abs(_numeric(indexed[before][sid][outcome])) for sid in ids) or 1.0
            dirs=Counter(_direction(v,scale) for v in values)
            main.append({"comparison":name,"outcome":outcome,**distribution(values),**dirs})
    for name,a0,a1,b0,b1 in rectangles:
        for outcome in outcomes:
            values=[]
            for sid in ids:
                v=(_numeric(indexed[case_of(a1,b1)][sid][outcome])-_numeric(indexed[case_of(a0,b1)][sid][outcome]))-(_numeric(indexed[case_of(a1,b0)][sid][outcome])-_numeric(indexed[case_of(a0,b0)][sid][outcome]))
                values.append(v)
            stats=distribution(values); scale=max(abs(v) for v in values) or 1.0; dirs=Counter(_direction(v,scale) for v in values)
            interactions.append({"contrast":name,"outcome":outcome,**stats,**dirs})
    return main, interactions
