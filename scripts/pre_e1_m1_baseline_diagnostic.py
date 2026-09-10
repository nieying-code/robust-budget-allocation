"""Run the three-case PRE-E1 M1 baseline mechanism diagnostic only."""

from __future__ import annotations

from copy import deepcopy
import json
import math
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from robust_budget_allocation.algorithms.qfr_extensive_form import solve_qfr_extensive_form  # noqa: E402
from robust_budget_allocation.algorithms.qfr_protocol import solver_configuration_identity, tolerance  # noqa: E402
from robust_budget_allocation.data.qfr_data import QFRData  # noqa: E402
from robust_budget_allocation.io.atomic import atomic_write_json, atomic_write_text  # noqa: E402
from robust_budget_allocation.io.hashing import canonical_json_sha256, sha256_file  # noqa: E402
from robust_budget_allocation.runtime.environment import ensure_preflight_once  # noqa: E402


INPUT = ROOT / "configs/r6c_formal_ready_data_v2.json"
OUTPUT = ROOT / "experiments/pre_e1_m1_baseline_diagnostic/result.json"
SUMMARY = ROOT / "experiments/pre_e1_m1_baseline_diagnostic/SUMMARY.md"
EXPECTED_DATA_SHA256 = "59f4b89d8706f9af06aef46455292335b8b8b095f4a2a0ce0f700e5d219ed16f"
EXPECTED_SCENARIO_SHA256 = "3bfea4bad74d39422eb4e004f4c5ffe883cffc7d65244ab14b2d87864531fede"
BUDGET_RATIOS = (0.9, 1.0, 1.1)
ITEMS = ("Water", "Seasonal Influenza Vaccine", "Crackers")


def _load_ready() -> dict[str, Any]:
    ready = json.loads(INPUT.read_text(encoding="utf-8"))
    bare = dict(ready)
    embedded = bare.pop("data_sha256", None)
    if embedded != EXPECTED_DATA_SHA256 or canonical_json_sha256(bare) != embedded:
        raise ValueError("R6-C Formal-ready data identity mismatch")
    if ready.get("scenario_sha256") != EXPECTED_SCENARIO_SHA256:
        raise ValueError("R6-C scenario identity mismatch")
    parameters = ready["parameters"]
    if (
        tuple(parameters["reliability_mitigation"]) != (0.2, 0.5, 0.8)
        or tuple(parameters["f_disruption_cat1_to_cat5"]) != (0.1, 0.3, 0.6, 0.8, 1.0)
        or tuple(parameters["q_survivability_cat1_to_cat5"]) != (0.9, 0.85, 0.8, 0.75, 0.7)
        or parameters["shortage_beta"] != 4.0
        or parameters["shortage_priority_lambda"] != dict.fromkeys(ITEMS, 1.0)
    ):
        raise ValueError("R6-C baseline parameter mismatch")
    for item in ITEMS:
        q_cost = float(parameters["q_unit_cost"][item])
        if not math.isclose(parameters["reservation_cost"][item] / q_cost, 0.2, abs_tol=1e-12):
            raise ValueError("R6-C phi mismatch")
        if not math.isclose(parameters["exercise_cost"][item] / q_cost, 0.85, abs_tol=1e-12):
            raise ValueError("R6-C psi mismatch")
    return ready


def _case_data(ready: dict[str, Any], ratio: float) -> QFRData:
    payload = deepcopy(ready["qfr_data"])
    payload["budget"] = float(ready["reference_budget"]) * ratio
    data = QFRData.from_dict(payload)
    if tuple(data.items) != ITEMS:
        raise ValueError("R6-C commodity identity mismatch")
    for item in ITEMS:
        if data.reliability_mitigation[item] != {0: 0.2, 1: 0.5, 2: 0.8}:
            raise ValueError("R6-C eta mismatch")
        if data.reliability_cost[item][0] != 0.0:
            raise ValueError("M1 R0 premium must remain zero")
    return data


def _category_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {f"Cat{category}": sum(int(row["category"]) == category for row in rows) for category in (3, 4, 5)}


def _classification(near_active: list[dict[str, Any]], f_positive: bool) -> str:
    categories = [int(row["category"]) for row in near_active]
    has_mid = any(value in (3, 4) for value in categories)
    has_cat5 = 5 in categories
    if has_mid and has_cat5:
        return "MULTI-SEVERITY_ACTIVE_STRUCTURE"
    cat5_share = 0.0 if not categories else sum(value == 5 for value in categories) / len(categories)
    if not f_positive and cat5_share >= 0.8:
        return "CAT5_DOMINATED_AND_F_INACTIVE"
    if has_mid and not f_positive:
        return "MULTI-SEVERITY_BUT_F_INACTIVE"
    return "OUTSIDE_A_B_C"


def _run_case(ready: dict[str, Any], ratio: float) -> dict[str, Any]:
    data = _case_data(ready, ratio)
    solved = solve_qfr_extensive_form(data, "M1")
    if solved["status"] != "optimal" or solved["oracle"]["status"] != "complete":
        raise RuntimeError(f"M1 diagnostic solve failed at budget ratio {ratio}")
    first = solved["first_stage"]
    if first["reliability_levels"] != [0]:
        raise RuntimeError("M1 diagnostic did not remain restricted to R0")
    q = {item: float(first["q"][item]) for item in ITEMS}
    f = {item: float(first["f"][item]["0"]) for item in ITEMS}
    f_positive = any(value > tolerance(value, 0.0) for value in f.values())
    categories = {row["scenario_id"]: int(row["category"]) for row in ready["scenarios"]}
    recourse = {str(row["scenario_id"]): float(row["loss"]) for row in solved["oracle"]["results"]}
    ordered = sorted(recourse, key=lambda scenario: (-recourse[scenario], scenario))
    worst_scenario = str(solved["oracle"]["worst_scenario"])
    worst_cost = float(solved["oracle"]["worst_loss"])

    def diagnostic_row(scenario: str) -> dict[str, Any]:
        cost = recourse[scenario]
        gap = 0.0 if worst_cost == 0.0 else 100.0 * (worst_cost - cost) / worst_cost
        return {"scenario_id": scenario, "category": categories[scenario],
                "recourse_cost": cost, "gap_to_worst_percent": gap}

    top10 = [diagnostic_row(scenario) for scenario in ordered[:10]]
    near_active = [diagnostic_row(scenario) for scenario in ordered
                   if (0.0 if worst_cost == 0.0 else 100.0 * (worst_cost - recourse[scenario]) / worst_cost) <= 1.0 + 1e-12]
    return {
        "budget_ratio": ratio,
        "budget": data.budget,
        "status": "SUCCESS",
        "objective": float(solved["objective"]),
        "Q": q,
        "F": f,
        "M1_F_positive": f_positive,
        "reported_worst_scenario": worst_scenario,
        "scenario_recourse_costs": recourse,
        "top10": top10,
        "near_active_within_1_percent": near_active,
        "top10_category_counts": _category_counts(top10),
        "near_active_category_counts": _category_counts(near_active),
        "classification": _classification(near_active, f_positive),
    }


def _summary(result: dict[str, Any]) -> str:
    lines = [
        "# PRE-E1 M1 baseline diagnostic",
        "",
        "Status: **PRE-E1 DIAGNOSTIC ONLY**",
        "",
        "Scientific purpose: mechanism diagnosis only. This is not Formal E1 and does not authorize parameter changes or later experiments.",
        "",
        "| Budget | Success | M1 F>0 | Reported worst | <=1% near-active categories | Classification |",
        "| ---: | --- | --- | --- | --- | --- |",
    ]
    for case in result["cases"]:
        counts = case["near_active_category_counts"]
        composition = ", ".join(f"{key}={value}" for key, value in counts.items())
        lines.append(
            f"| {case['budget_ratio']:.2f} B_ref | {case['status']} | {case['M1_F_positive']} | "
            f"{case['reported_worst_scenario']} | {composition} | {case['classification']} |"
        )
    lines.extend([
        "", f"Overall classification: **{result['overall_classification']}**.", "",
        "No R6-C parameter was modified. M0/M2 and Formal E1–E5 were not run.", "",
    ])
    return "\n".join(lines)


def main() -> int:
    if OUTPUT.exists() or SUMMARY.exists():
        raise FileExistsError("diagnostic output already exists; refusing to overwrite")
    ready = _load_ready()
    environment = ensure_preflight_once().to_dict()
    cases = [_run_case(ready, ratio) for ratio in BUDGET_RATIOS]
    classes = {case["classification"] for case in cases}
    overall = next(iter(classes)) if len(classes) == 1 else "MIXED_" + "__".join(sorted(classes))
    result = {
        "schema_version": 1,
        "scope": "PRE_E1_M1_BASELINE_DIAGNOSTIC_ONLY",
        "scientific_purpose": "MECHANISM_DIAGNOSIS_ONLY",
        "formal_E1": False,
        "models_run": ["M1"],
        "formal_E1_E5_runs": 0,
        "input_path": INPUT.relative_to(ROOT).as_posix(),
        "input_file_sha256": sha256_file(INPUT),
        "input_data_sha256": ready["data_sha256"],
        "input_scenario_sha256": ready["scenario_sha256"],
        "reference_budget": ready["reference_budget"],
        "budget_ratios": list(BUDGET_RATIOS),
        "solver_configuration": solver_configuration_identity(),
        "environment": environment,
        "classification_rule": {
            "A": "Cat3/Cat4 and Cat5 both occur in <=1% near-active set",
            "B": "Cat5 share >=80% in <=1% near-active set and M1 F is inactive",
            "C": "Cat3/Cat4 occurs in <=1% near-active set and M1 F is inactive, unless A applies",
        },
        "cases": cases,
        "overall_classification": overall,
        "parameter_changes": [],
    }
    result["result_sha256"] = canonical_json_sha256(result)
    atomic_write_json(OUTPUT, result)
    atomic_write_text(SUMMARY, _summary(result))
    print(json.dumps({"status": "SUCCESS", "cases": len(cases), "overall_classification": overall,
                      "result_sha256": result["result_sha256"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
