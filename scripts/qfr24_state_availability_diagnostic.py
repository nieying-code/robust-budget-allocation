"""Run the one authorized 9-case Rawls24 state-availability diagnostic."""

from __future__ import annotations

import csv
import io
import json
import math
from pathlib import Path
import sys

import pyomo.environ as pyo


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from robust_budget_allocation.algorithms.qfr_exact_oracle import build_exact_recourse  # noqa: E402
from robust_budget_allocation.algorithms.qfr_protocol import SOLVER_OPTIONS  # noqa: E402
from robust_budget_allocation.algorithms.qfr_state import extract_first_stage, first_stage_cost  # noqa: E402
from robust_budget_allocation.diagnostics.qfr24_state_availability import (  # noqa: E402
    BUDGET_RATIOS, ITEMS, MODELS, build_authority, build_diagnostic_ef, case_data,
)
from robust_budget_allocation.io.hashing import canonical_json_sha256, sha256_bytes  # noqa: E402
from robust_budget_allocation.runtime.environment import ensure_preflight_once  # noqa: E402


OUTPUT_DIR = ROOT / "diagnostics/qfr24_state_availability"


def _solve(model) -> dict:
    solver = pyo.SolverFactory("gurobi_direct")
    for name, value in SOLVER_OPTIONS.items():
        solver.options[name] = value
    # Scale stabilization for Rawls24's O(1e9) RHS; no scientific input changes.
    solver.options["NumericFocus"] = 3
    result = solver.solve(model, tee=False, load_solutions=False)
    status, termination = str(result.solver.status), str(result.solver.termination_condition)
    if status != "ok" or termination not in {"optimal", "globallyOptimal"}:
        raise RuntimeError(f"solver failed: {status}/{termination}")
    model.solutions.load_from(result)
    return {
        "status": status,
        "termination": termination,
        "interface": "gurobi_direct",
        "options": {**SOLVER_OPTIONS, "NumericFocus": 3},
    }


def _recourse(data, decision, scenario: str, direct_f: dict) -> dict:
    model = build_exact_recourse(data, decision, scenario)
    if decision.model_kind != "M0":
        model.del_component(model.exercise_limit)
        model.exercise_limit = pyo.Constraint(
            model.I,
            rule=lambda m, item: m.x[item] <= sum(
                float(direct_f[scenario][str(level)]) * decision.f[item][level]
                for level in decision.reliability_levels
            ),
        )
    _solve(model)
    exercise = {
        item: 0.0 if decision.model_kind == "M0" else float(pyo.value(model.x[item]))
        for item in ITEMS
    }
    shortage = {item: float(pyo.value(model.u[item])) for item in ITEMS}
    exercise_cost = sum(data.exercise_cost[item] * exercise[item] for item in ITEMS)
    shortage_cost = sum(data.shortage_cost[item] * shortage[item] for item in ITEMS)
    return {
        "scenario_id": scenario, "exercise": exercise, "shortage": shortage,
        "exercise_cost": exercise_cost, "shortage_cost": shortage_cost,
        "loss": exercise_cost + shortage_cost,
        "unused_cash": data.budget - first_stage_cost(data, decision) - exercise_cost,
    }


def _case(authority: dict, ratio: float, model_kind: str) -> dict:
    data = case_data(authority, ratio)
    model = build_diagnostic_ef(data, model_kind, authority["direct_f_availability"])
    solver = _solve(model)
    decision = extract_first_stage(data, model)
    recourse = [_recourse(data, decision, scenario, authority["direct_f_availability"]) for scenario in data.scenarios]
    worst_loss = max(row["loss"] for row in recourse)
    worst_ids = sorted(row["scenario_id"] for row in recourse if math.isclose(row["loss"], worst_loss, rel_tol=1e-9, abs_tol=1e-6))
    worst_id = worst_ids[0]
    worst_recourse = next(row for row in recourse if row["scenario_id"] == worst_id)
    objective = float(pyo.value(model.total_cost))
    expected = first_stage_cost(data, decision) + worst_loss
    if not math.isclose(objective, expected, rel_tol=1e-9, abs_tol=1e-6):
        raise RuntimeError(f"EF/exact-recourse mismatch: {objective!r} != {expected!r}")
    q = dict(decision.q)
    f = {item: sum(decision.f[item].values()) for item in ITEMS}
    selected = {
        item: next((f"R{level}" for level in decision.reliability_levels if decision.f[item][level] > 1e-7), "NONE")
        for item in ITEMS
    }
    c_q = float(pyo.value(model.C_Q))
    c_f = float(pyo.value(model.C_F))
    c_r = float(pyo.value(model.C_R))
    row = {
        "case_id": f"{model_kind}_B{ratio:.2f}", "model_kind": model_kind,
        "budget_ratio": ratio, "budget": data.budget, "T_COST": objective,
        "Q": q, "F": f, "R_level": selected,
        "expenditure": {"Q": c_q, "F": c_f, "R": c_r, "first_stage": c_q + c_f + c_r},
        "budget_share": {"Q": c_q / data.budget, "F": c_f / data.budget, "R": c_r / data.budget},
        "F_activated": any(value > 1e-7 for value in f.values()),
        "R1_activated": "R1" in selected.values(), "R2_activated": "R2" in selected.values(),
        "worst_scenario": {"scenario_id": worst_id, **authority["metadata"][worst_id], "co_worst_ids": worst_ids},
        "worst_recourse": worst_recourse,
        "scenario_losses": {row["scenario_id"]: row["loss"] for row in recourse},
        "solver": solver,
    }
    row["case_sha256"] = canonical_json_sha256(row)
    return row


def _csv(cases: list[dict]) -> bytes:
    fields = [
        "case_id", "budget", "T_COST", "Q_Water", "Q_Vaccine", "Q_Crackers",
        "F_Water", "F_Vaccine", "F_Crackers", "R_Water", "R_Vaccine", "R_Crackers",
        "C_Q", "C_F", "C_R", "F_activated", "R1_activated", "R2_activated",
        "worst_scenario", "worst_hurricane", "worst_category", "worst_state",
    ]
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for case in cases:
        writer.writerow({
            "case_id": case["case_id"], "budget": case["budget"], "T_COST": case["T_COST"],
            "Q_Water": case["Q"]["Water"], "Q_Vaccine": case["Q"]["Seasonal Influenza Vaccine"], "Q_Crackers": case["Q"]["Crackers"],
            "F_Water": case["F"]["Water"], "F_Vaccine": case["F"]["Seasonal Influenza Vaccine"], "F_Crackers": case["F"]["Crackers"],
            "R_Water": case["R_level"]["Water"], "R_Vaccine": case["R_level"]["Seasonal Influenza Vaccine"], "R_Crackers": case["R_level"]["Crackers"],
            "C_Q": case["expenditure"]["Q"], "C_F": case["expenditure"]["F"], "C_R": case["expenditure"]["R"],
            "F_activated": case["F_activated"], "R1_activated": case["R1_activated"], "R2_activated": case["R2_activated"],
            "worst_scenario": case["worst_scenario"]["scenario_id"], "worst_hurricane": case["worst_scenario"]["hurricane_name"],
            "worst_category": case["worst_scenario"]["category"], "worst_state": case["worst_scenario"]["state"],
        })
    return stream.getvalue().encode("utf-8")


def main() -> int:
    authority = build_authority(ROOT)
    environment = ensure_preflight_once().to_dict()
    cases = []
    for ratio in BUDGET_RATIOS:
        for model_kind in MODELS:
            print(f"solving {model_kind} at {ratio:.2f} B_ref", flush=True)
            cases.append(_case(authority, ratio, model_kind))
    comparisons = []
    for ratio in BUDGET_RATIOS:
        indexed = {case["model_kind"]: case for case in cases if case["budget_ratio"] == ratio}
        comparisons.append({
            "budget_ratio": ratio,
            "M1_minus_M0": indexed["M1"]["T_COST"] - indexed["M0"]["T_COST"],
            "M2_minus_M1": indexed["M2"]["T_COST"] - indexed["M1"]["T_COST"],
            "M1_M2_objective_equal": math.isclose(indexed["M1"]["T_COST"], indexed["M2"]["T_COST"], rel_tol=1e-9, abs_tol=1e-6),
            "M1_M2_decisions_differ": indexed["M1"]["Q"] != indexed["M2"]["Q"] or indexed["M1"]["F"] != indexed["M2"]["F"] or indexed["M1"]["R_level"] != indexed["M2"]["R_level"],
        })
    payload = {
        "scope": authority["scope"], "scientific_status": authority["scientific_status"],
        "authority": {key: value for key, value in authority.items() if key != "base_qfr_data"},
        "environment": environment, "case_count": len(cases), "cases": cases,
        "comparisons": comparisons, "no_automatic_tuning": True, "formal_E1_runs": 0,
    }
    payload["diagnostic_sha256"] = canonical_json_sha256(payload)
    result_bytes = (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    csv_bytes = _csv(cases)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "results.json").write_bytes(result_bytes)
    (OUTPUT_DIR / "summary.csv").write_bytes(csv_bytes)
    hashes = {"results.json": sha256_bytes(result_bytes), "summary.csv": sha256_bytes(csv_bytes)}
    (OUTPUT_DIR / "HASHES.sha256").write_text(
        "\n".join(f"{digest}  {name}" for name, digest in sorted(hashes.items())) + "\n",
        encoding="utf-8", newline="\n",
    )
    print(json.dumps({"status": "PASS", "D_ref": authority["D_ref"], "B_ref": authority["B_ref"], "hashes": hashes}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
