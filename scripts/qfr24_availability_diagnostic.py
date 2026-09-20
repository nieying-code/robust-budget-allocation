"""Run the single authorized 9-case Rawls24 availability diagnostic."""

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

from robust_budget_allocation.algorithms.qfr_builders import build_qfr_extensive_form  # noqa: E402
from robust_budget_allocation.algorithms.qfr_exact_oracle import build_exact_recourse  # noqa: E402
from robust_budget_allocation.algorithms.qfr_protocol import SOLVER_OPTIONS, solve_exact  # noqa: E402
from robust_budget_allocation.algorithms.qfr_state import (  # noqa: E402
    extract_first_stage,
    first_stage_cost,
)
from robust_budget_allocation.diagnostics.qfr24_availability import (  # noqa: E402
    BUDGET_RATIOS,
    ITEMS,
    MODELS,
    build_diagnostic_authority,
    case_data,
)
from robust_budget_allocation.io.hashing import canonical_json_sha256, sha256_bytes  # noqa: E402
from robust_budget_allocation.models.qfr_support import validate_qfr_solution  # noqa: E402
from robust_budget_allocation.runtime.environment import ensure_preflight_once  # noqa: E402


OUTPUT_DIR = ROOT / "diagnostics/qfr24_availability"


def _selected_level(first: dict, item: str, tolerance: float = 1e-7) -> str:
    levels = first["reliability_levels"]
    active = [int(level) for level in levels if float(first["f"][item][str(level)]) > tolerance]
    return "NONE" if not active else f"R{active[0]}"


def _exact_recourse_diagnostics(data, decision) -> list[dict]:
    """Evaluate existing exact-recourse LPs with a scale-focused Gurobi setting."""

    rows = []
    pre = first_stage_cost(data, decision)
    for scenario in data.scenarios:
        model = build_exact_recourse(data, decision, scenario)
        solver = pyo.SolverFactory("gurobi_direct")
        for name, value in SOLVER_OPTIONS.items():
            solver.options[name] = value
        # h09 has an O(1e9) RHS; this prevents a false infeasible presolve at
        # FeasibilityTol=1e-9 without changing the LP or any scientific input.
        solver.options["NumericFocus"] = 3
        outcome = solver.solve(model, tee=False, load_solutions=False)
        if str(outcome.solver.status) != "ok" or str(outcome.solver.termination_condition) != "optimal":
            raise RuntimeError(f"exact recourse failed for {scenario}: {outcome.solver}")
        model.solutions.load_from(outcome)
        exercise = {
            item: 0.0 if decision.model_kind == "M0" else float(pyo.value(model.x[item]))
            for item in ITEMS
        }
        shortage = {item: float(pyo.value(model.u[item])) for item in ITEMS}
        exercise_cost = sum(data.exercise_cost[item] * exercise[item] for item in ITEMS)
        shortage_penalty = sum(data.shortage_cost[item] * shortage[item] for item in ITEMS)
        rows.append({
            "scenario_id": scenario,
            "exercise": exercise,
            "shortage": shortage,
            "exercise_cost": exercise_cost,
            "shortage_penalty": shortage_penalty,
            "loss": exercise_cost + shortage_penalty,
            "unused_cash": data.budget - pre - exercise_cost,
        })
    return rows


def _solve_diagnostic_case(data, model_kind: str) -> dict:
    """Solve the full EF and inspect its loaded all-scenario solution.

    This is not a Formal certification run. The EF formulation and frozen solve
    policy remain unchanged; exact-recourse diagnostics are evaluated separately
    with the documented scale-focused numerical setting.
    """

    model = build_qfr_extensive_form(data, model_kind)
    outcome = solve_exact(model)
    if outcome.status != "optimal":
        return {"status": "failed", "solver": outcome.to_dict()}
    accounting = validate_qfr_solution(data, model, tolerance=1e-6)
    first = extract_first_stage(data, model)
    recourse = _exact_recourse_diagnostics(data, first)
    worst_loss = max(row["loss"] for row in recourse)
    co_worst = sorted(
        row["scenario_id"] for row in recourse
        if math.isclose(row["loss"], worst_loss, rel_tol=1e-9, abs_tol=1e-6)
    )
    worst_id = co_worst[0]
    solver_identity = outcome.to_dict()
    solver_identity.pop("runtime_seconds")
    result = {
        "status": "optimal",
        "solver": outcome.to_dict(),
        "objective": float(outcome.objective),
        "first_stage": first.to_dict(),
        "accounting": accounting.to_dict(),
        "exact_recourse_diagnostics": recourse,
        "worst_scenario": worst_id,
        "co_worst_scenarios": co_worst,
        "validation": "FULL_EF_LOADED_SOLUTION_ACCOUNTING_NOT_FORMAL_ORACLE_CERTIFICATION",
    }
    result["scientific_result_sha256"] = canonical_json_sha256({
        "model_kind": model_kind,
        "data_sha256": data.data_sha256,
        "solver": solver_identity,
        "objective": result["objective"],
        "first_stage": result["first_stage"],
        "accounting": result["accounting"],
        "exact_recourse_diagnostics": recourse,
        "worst_scenario": worst_id,
        "co_worst_scenarios": co_worst,
        "validation": result["validation"],
    })
    return result


def _summarize_case(authority: dict, model: str, ratio: float, result: dict) -> dict:
    if result["status"] != "optimal":
        raise RuntimeError(f"{model}/{ratio} failed: {result['solver']}")
    data = case_data(authority, ratio)
    first = result["first_stage"]
    accounting = result["accounting"]
    worst_id = result["worst_scenario"]
    worst = next(
        row for row in result["exact_recourse_diagnostics"] if row["scenario_id"] == worst_id
    )
    q = {item: float(first["q"][item]) for item in ITEMS}
    f = {
        item: sum(float(value) for value in first["f"][item].values()) for item in ITEMS
    }
    levels = {item: _selected_level(first, item) for item in ITEMS}
    c_q, c_f, c_r = (float(accounting[key]) for key in ("C_Q", "C_F", "C_R"))
    row = {
        "case_id": f"{model}_B{ratio:.2f}",
        "model_kind": model,
        "budget_ratio": ratio,
        "budget": data.budget,
        "T_COST": float(result["objective"]),
        "Q": q,
        "F": f,
        "R_level": levels,
        "expenditure": {"Q": c_q, "F": c_f, "R": c_r, "first_stage": float(accounting["C_pre"])},
        "budget_share": {"Q": c_q / data.budget, "F": c_f / data.budget, "R": c_r / data.budget},
        "worst_scenario": {
            "scenario_id": worst_id,
            **authority["metadata"][worst_id],
            "shortage": {item: float(worst["shortage"][item]) for item in ITEMS},
            "shortage_penalty": float(worst["shortage_penalty"]),
            "exercise": {item: float(worst["exercise"][item]) for item in ITEMS},
            "exercise_expenditure": float(worst["exercise_cost"]),
            "recourse_loss": float(worst["loss"]),
            "co_worst_scenario_ids": list(result["co_worst_scenarios"]),
        },
        "F_activated": any(value > 1e-7 for value in f.values()),
        "R1_activated": "R1" in levels.values(),
        "R2_activated": "R2" in levels.values(),
        "solver_status": result["solver"]["status"],
        "termination": result["solver"]["termination"],
        "validation": result["validation"],
        "data_sha256": data.data_sha256,
        "result_sha256": result["scientific_result_sha256"],
    }
    row["case_sha256"] = canonical_json_sha256(row)
    return row


def _summary_csv(cases: list[dict]) -> bytes:
    fields = [
        "case_id", "model_kind", "budget_ratio", "budget", "T_COST", "C_Q", "C_F", "C_R",
        "Q_Water", "Q_Vaccine", "Q_Crackers", "F_Water", "F_Vaccine", "F_Crackers",
        "R_Water", "R_Vaccine", "R_Crackers", "F_activated", "R1_activated", "R2_activated",
        "worst_scenario", "worst_hurricane", "worst_category", "shortage_Water",
        "shortage_Vaccine", "shortage_Crackers", "shortage_penalty",
    ]
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for case in cases:
        worst = case["worst_scenario"]
        writer.writerow({
            "case_id": case["case_id"], "model_kind": case["model_kind"],
            "budget_ratio": case["budget_ratio"], "budget": case["budget"], "T_COST": case["T_COST"],
            "C_Q": case["expenditure"]["Q"], "C_F": case["expenditure"]["F"], "C_R": case["expenditure"]["R"],
            "Q_Water": case["Q"]["Water"], "Q_Vaccine": case["Q"]["Seasonal Influenza Vaccine"],
            "Q_Crackers": case["Q"]["Crackers"], "F_Water": case["F"]["Water"],
            "F_Vaccine": case["F"]["Seasonal Influenza Vaccine"], "F_Crackers": case["F"]["Crackers"],
            "R_Water": case["R_level"]["Water"], "R_Vaccine": case["R_level"]["Seasonal Influenza Vaccine"],
            "R_Crackers": case["R_level"]["Crackers"], "F_activated": case["F_activated"],
            "R1_activated": case["R1_activated"], "R2_activated": case["R2_activated"],
            "worst_scenario": worst["scenario_id"], "worst_hurricane": worst["hurricane_name"],
            "worst_category": worst["category"], "shortage_Water": worst["shortage"]["Water"],
            "shortage_Vaccine": worst["shortage"]["Seasonal Influenza Vaccine"],
            "shortage_Crackers": worst["shortage"]["Crackers"], "shortage_penalty": worst["shortage_penalty"],
        })
    return stream.getvalue().encode("utf-8")


def main() -> int:
    authority = build_diagnostic_authority(ROOT)
    environment = ensure_preflight_once().to_dict()
    cases = []
    for ratio in BUDGET_RATIOS:
        for model in MODELS:
            print(f"solving {model} at {ratio:.2f} B_ref", flush=True)
            result = _solve_diagnostic_case(case_data(authority, ratio), model)
            cases.append(_summarize_case(authority, model, ratio, result))
    payload = {
        "scope": authority["scope"],
        "scientific_status": authority["scientific_status"],
        "authority": {key: value for key, value in authority.items() if key != "base_qfr_data"},
        "environment": environment,
        "case_count": len(cases),
        "cases": cases,
        "no_second_round_tuning": True,
    }
    payload["diagnostic_sha256"] = canonical_json_sha256(payload)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    result_bytes = (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    csv_bytes = _summary_csv(cases)
    (OUTPUT_DIR / "results.json").write_bytes(result_bytes)
    (OUTPUT_DIR / "summary.csv").write_bytes(csv_bytes)
    hashes = {
        "README.md": sha256_bytes((OUTPUT_DIR / "README.md").read_bytes()),
        "results.json": sha256_bytes(result_bytes),
        "summary.csv": sha256_bytes(csv_bytes),
    }
    (OUTPUT_DIR / "HASHES.sha256").write_text(
        "\n".join(f"{digest}  {name}" for name, digest in sorted(hashes.items())) + "\n",
        encoding="utf-8", newline="\n",
    )
    print(json.dumps({"status": "PASS", "B_ref": authority["B_ref"], "cases": len(cases), "hashes": hashes}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
