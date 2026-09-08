"""Replay and quantify the 121 pre-fix Rawls24 Layer A numerical failures."""

from __future__ import annotations

import csv
import gzip
import json
import math
from pathlib import Path
import sys
from typing import Any, Mapping

import numpy as np
import pyomo.environ as pyo


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import robust_budget_allocation.algorithms.qfr_exact_oracle as exact_module  # noqa: E402
import robust_budget_allocation.algorithms.qfr_improved_ccg as a1_module  # noqa: E402
import robust_budget_allocation.algorithms.qfr_standard_ccg as master_module  # noqa: E402
from robust_budget_allocation.algorithms.qfr_improved_ccg import solve_qfr_improved_ccg  # noqa: E402
from robust_budget_allocation.algorithms.qfr_protocol import scenario_identity  # noqa: E402
from robust_budget_allocation.algorithms.qfr_state import first_stage_cost  # noqa: E402
from robust_budget_allocation.io.hashing import canonical_json_sha256, sha256_file  # noqa: E402
from robust_budget_allocation.simulation.layer_a import (  # noqa: E402
    data_for_sample,
    load_config,
    load_rawls24_neutral_fixture,
)
from qfr_mechanism_layer_a import _read_samples  # noqa: E402


CONFIG = ROOT / "configs/qfr_mechanism_layer_a_rawls24_v1.json"
SOURCE = ROOT / "simulation_results/qfr_mechanism_layer_a_rawls24_n1000"
OUTPUT = ROOT / "simulation_results/qfr_mechanism_layer_a_rawls24_numerical_audit_pre_fix"
FAMILIES = (
    "objective_epigraph",
    "budget",
    "quantity_nonnegative",
    "fulfillment_capacity",
    "demand_flow",
    "other_model_constraint",
)


def _value(component: Any) -> float:
    return float(pyo.value(component))


def _constraint_residual(constraint: pyo.ConstraintData) -> float:
    body = _value(constraint.body)
    residual = 0.0
    if constraint.lower is not None:
        residual = max(residual, _value(constraint.lower) - body)
    if constraint.upper is not None:
        residual = max(residual, body - _value(constraint.upper))
    return max(0.0, residual)


def _entry(family: str, label: str, absolute: float, scale: float) -> dict[str, Any]:
    reference = max(1.0, abs(float(scale)))
    violation = max(0.0, float(absolute))
    return {
        "family": family,
        "label": label,
        "reference_magnitude": reference,
        "absolute_violation": violation,
        "relative_violation": violation / reference,
    }


def _master_constraint_audit(data, model) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    for constraint in model.component_data_objects(pyo.Constraint, active=True):
        name = constraint.parent_component().local_name
        index = constraint.index()
        residual = _constraint_residual(constraint)
        if name == "worst_loss":
            scenario = str(index)
            entries.append(_entry(
                "objective_epigraph", f"worst_loss[{scenario}]", residual,
                max(abs(_value(model.theta)), abs(_value(model.scenario_loss[scenario]))),
            ))
        elif name == "scenario_budget":
            scenario = str(index)
            entries.append(_entry(
                "budget", f"scenario_budget[{scenario}]", residual,
                max(abs(data.budget), abs(_value(model.C_pre)), abs(_value(model.exercise_cost[scenario]))),
            ))
        elif name == "demand_balance":
            item, scenario = index
            parts = [_value(model.effective_Q[item, scenario]), _value(model.u[item, scenario])]
            if hasattr(model, "x"):
                parts.append(_value(model.x[item, scenario]))
            entries.append(_entry(
                "demand_flow", f"demand_balance[{item},{scenario}]", residual,
                max(abs(data.demand[scenario][item]), *(abs(value) for value in parts)),
            ))
        elif name == "exercise_limit":
            item, scenario = index
            entries.append(_entry(
                "fulfillment_capacity", f"exercise_limit[{item},{scenario}]", residual,
                max(abs(_value(model.x[item, scenario])), abs(_value(model.fulfillable_F[item, scenario]))),
            ))
        elif name == "capacity_link":
            item, level = index
            entries.append(_entry(
                "fulfillment_capacity", f"capacity_link[{item},{level}]", residual,
                max(abs(_value(model.F[item, level])), abs(data.flexible_capacity[item] * _value(model.z[item, level]))),
            ))
        else:
            entries.append(_entry("other_model_constraint", f"{name}[{index}]", residual, abs(_value(constraint.body))))
    for var in model.component_data_objects(pyo.Var, active=True):
        value = _value(var)
        if var.lb is not None:
            entries.append(_entry("quantity_nonnegative", f"{var.name} lower", float(var.lb) - value, max(abs(value), abs(float(var.lb)))))
    maxima = {
        family: max((row for row in entries if row["family"] == family), key=lambda row: row["absolute_violation"], default=_entry(family, "unavailable", 0, 1))
        for family in FAMILIES
    }
    return {"kind": "restricted_master", "maxima": maxima}


def _recourse_audit(data, decision, scenario: str, result: Mapping[str, Any] | None) -> dict[str, Any]:
    pre = first_stage_cost(data, decision)
    entries: list[dict[str, Any]] = []
    if result is None or result.get("exercise") is None:
        exercise = dict.fromkeys(data.items, 0.0)
        shortage = {
            item: max(0.0, data.demand[scenario][item] - exact_module._available_q(data, decision, item, scenario))
            for item in data.items
        }
        result_availability = "ANALYTIC_FEASIBLE_WITNESS_FOR_NONOPTIMAL_SOLVER_OUTCOME"
    else:
        exercise = {item: float(result["exercise"][item]) for item in data.items}
        shortage = {item: float(result["shortage"][item]) for item in data.items}
        result_availability = "LOADED_OPTIMAL_SOLUTION"
    for item in data.items:
        available = exact_module._available_q(data, decision, item, scenario)
        fulfillable = exact_module._fulfillable(data, decision, item, scenario)
        entries.append(_entry("quantity_nonnegative", f"exercise[{item}] nonnegative", -exercise[item], abs(exercise[item])))
        entries.append(_entry("quantity_nonnegative", f"shortage[{item}] nonnegative", -shortage[item], abs(shortage[item])))
        entries.append(_entry("fulfillment_capacity", f"exercise_limit[{item}]", exercise[item] - fulfillable, max(abs(exercise[item]), abs(fulfillable))))
        coverage = available + exercise[item] + shortage[item]
        entries.append(_entry("demand_flow", f"demand_balance[{item}]", data.demand[scenario][item] - coverage, max(abs(data.demand[scenario][item]), abs(available), abs(exercise[item]), abs(shortage[item]))))
    exercise_cost = sum(data.exercise_cost[item] * exercise[item] for item in data.items)
    entries.append(_entry("budget", "fixed_total_budget", pre + exercise_cost - data.budget, max(abs(data.budget), abs(pre), abs(exercise_cost))))
    maxima = {
        family: max((row for row in entries if row["family"] == family), key=lambda row: row["absolute_violation"], default=_entry(family, "unavailable", 0, 1))
        for family in FAMILIES
    }
    return {
        "kind": "exact_recourse",
        "scenario_id": scenario,
        "scenario_identity": scenario_identity(data, scenario),
        "result_availability": result_availability,
        "raw_first_stage_cost": pre,
        "budget": data.budget,
        "raw_budget_residual": pre + exercise_cost - data.budget,
        "maxima": maxima,
    }


def _old_failures() -> dict[str, dict[str, Any]]:
    scientific = {row["simulation_id"]: row for row in csv.DictReader((SOURCE / "scientific_results.csv").open(encoding="utf-8", newline=""))}
    failures = {key: {"failure_category": row["failure_type"], "failure_message": row["failure_message"]} for key, row in scientific.items() if row["status"] == "FAILED"}
    for shard in sorted((SOURCE / "raw_a1").glob("*.jsonl.gz")):
        with gzip.open(shard, "rt", encoding="utf-8") as handle:
            for line in handle:
                raw = json.loads(line)
                simulation_id = raw["simulation_id"]
                if simulation_id not in failures:
                    continue
                failure = failures[simulation_id]
                failure["input"] = raw["input"]
                failure["old_raw_record_sha256"] = canonical_json_sha256(raw)
                result = raw.get("a1_result")
                if result is None:
                    traceback_text = raw.get("traceback", "")
                    failure["stage"] = "restricted_master_validation" if "_solve_master" in traceback_text else "exact_recourse_validation"
                    failure["phase"] = "unavailable"
                    failure["scenario_id"] = "unavailable"
                    failure["scenario_identity"] = "unavailable"
                    continue
                failure["stage"] = "exact_oracle"
                failure["phase"] = "unavailable"
                failure["scenario_id"] = "unavailable"
                failure["scenario_identity"] = "unavailable"
                for trace in result["trace"]:
                    for phase_name in ("memory", "candidate", "full_exact_certification"):
                        phase = trace.get(phase_name) or {}
                        evaluations = phase.get("results", []) if phase_name == "full_exact_certification" else phase.get("evaluations", [])
                        for evaluation in evaluations:
                            if evaluation["solver"]["status"] != "optimal":
                                failure.update(
                                    phase=phase_name,
                                    scenario_id=evaluation["scenario_id"],
                                    scenario_identity=evaluation["scenario_identity"],
                                    solver_status=evaluation["solver"]["solver_status"],
                                    solver_termination=evaluation["solver"]["termination"],
                                )
    return failures


def _distribution(values: list[float]) -> dict[str, float]:
    array = np.asarray(values, dtype=float)
    return {
        "min": float(np.min(array)), "median": float(np.median(array)),
        "P90": float(np.percentile(array, 90)), "P95": float(np.percentile(array, 95)),
        "P99": float(np.percentile(array, 99)), "max": float(np.max(array)),
    }


def main() -> int:
    if OUTPUT.exists():
        raise RuntimeError(f"non-overwrite audit output already exists: {OUTPUT}")
    config = load_config(CONFIG)
    samples = {row["simulation_id"]: row for row in _read_samples(SOURCE / "samples.csv")}
    neutral, fixture = load_rawls24_neutral_fixture(ROOT, config)
    failures = _old_failures()
    if len(failures) != 121 or set(failures) - set(samples):
        raise RuntimeError("frozen pre-fix failure identity is not exactly 121 valid sample IDs")

    original_master_validation = master_module.validate_qfr_solution
    original_recourse_validation = exact_module.validate_recourse_result
    original_recourse_solve = exact_module.solve_exact_recourse
    context: dict[str, Any] = {}

    def audited_master_validation(data, model, **kwargs):
        report = _master_constraint_audit(data, model)
        context.setdefault("reports", []).append(report)
        try:
            return original_master_validation(data, model, **kwargs)
        except Exception as exc:
            report["validation_exception"] = f"{type(exc).__name__}: {exc}"
            raise

    def audited_recourse_validation(data, decision, result):
        report = _recourse_audit(data, decision, result["scenario_id"], result)
        context.setdefault("reports", []).append(report)
        try:
            return original_recourse_validation(data, decision, result)
        except Exception as exc:
            report["validation_exception"] = f"{type(exc).__name__}: {exc}"
            raise

    def audited_recourse_solve(data, decision, scenario):
        result = original_recourse_solve(data, decision, scenario)
        if result["solver"]["status"] != "optimal":
            report = _recourse_audit(data, decision, scenario, None)
            report.update(
                solver_status=result["solver"]["solver_status"],
                solver_termination=result["solver"]["termination"],
                solver_outcome=result["solver"]["status"],
            )
            context.setdefault("reports", []).append(report)
        return result

    master_module.validate_qfr_solution = audited_master_validation
    exact_module.validate_recourse_result = audited_recourse_validation
    exact_module.solve_exact_recourse = audited_recourse_solve
    a1_module.solve_exact_recourse = audited_recourse_solve
    case_rows: list[dict[str, Any]] = []
    detail: dict[str, Any] = {}
    try:
        for index, simulation_id in enumerate(sorted(failures), start=1):
            failure = failures[simulation_id]
            sample = samples[simulation_id]
            if sample["input_sha256"] != failure["input"]["input_sha256"]:
                raise RuntimeError(f"input hash changed for {simulation_id}")
            data = data_for_sample(neutral, fixture["metadata"], sample)
            context.clear()
            replay_exception = None
            try:
                replay = solve_qfr_improved_ccg(data, "M2", memory_phase_enabled=True)
                replay_status = replay["status"]
                replay_diagnostic = replay["diagnostic"]
            except Exception as exc:
                replay_status = "exception"
                replay_diagnostic = str(exc)
                replay_exception = f"{type(exc).__name__}: {exc}"
            failing_reports = [row for row in context.get("reports", []) if row.get("validation_exception") or row.get("solver_outcome") != "optimal" and "solver_outcome" in row]
            if not failing_reports:
                raise RuntimeError(f"audit failed to capture numerical failure for {simulation_id}")
            report = failing_reports[-1]
            maxima = report["maxima"]
            row = {
                "simulation_id": simulation_id,
                "input_sha256": sample["input_sha256"],
                "old_failure_category": failure["failure_category"],
                "old_failure_message": failure["failure_message"],
                "old_stage": failure["stage"],
                "old_phase": failure.get("phase", "unavailable"),
                "old_scenario_id": failure.get("scenario_id", "unavailable"),
                "old_scenario_identity": failure.get("scenario_identity", "unavailable"),
                "solver_status": report.get("solver_status", failure.get("solver_status", "optimal_loaded_solution")),
                "solver_termination": report.get("solver_termination", failure.get("solver_termination", "optimal")),
                "replay_status": replay_status,
                "replay_diagnostic": replay_diagnostic,
                "audit_kind": report["kind"],
                "audit_scenario_id": report.get("scenario_id", failure.get("scenario_id", "unavailable")),
                "audit_scenario_identity": report.get("scenario_identity", failure.get("scenario_identity", "unavailable")),
                "validation_exception": report.get("validation_exception", replay_exception or "unavailable"),
                "budget_residual": report.get("raw_budget_residual", maxima["budget"]["absolute_violation"]),
            }
            for family in FAMILIES:
                maximum = maxima[family]
                row[f"{family}_label"] = maximum["label"]
                row[f"{family}_reference"] = maximum["reference_magnitude"]
                row[f"{family}_absolute_violation"] = maximum["absolute_violation"]
                row[f"{family}_relative_violation"] = maximum["relative_violation"]
            case_rows.append(row)
            detail[simulation_id] = {
                "frozen_failure": failure,
                "replay": {"status": replay_status, "diagnostic": replay_diagnostic},
                "captured_failure_report": report,
            }
            if index % 20 == 0:
                print(f"audit progress {index}/121", flush=True)
    finally:
        master_module.validate_qfr_solution = original_master_validation
        exact_module.validate_recourse_result = original_recourse_validation
        exact_module.solve_exact_recourse = original_recourse_solve
        a1_module.solve_exact_recourse = original_recourse_solve

    categories: dict[str, int] = {}
    stages: dict[str, int] = {}
    for row in case_rows:
        categories[row["old_failure_message"]] = categories.get(row["old_failure_message"], 0) + 1
        key = f"{row['old_stage']}::{row['old_phase']}::{row['audit_scenario_id']}"
        stages[key] = stages.get(key, 0) + 1
    distributions = {
        family: {
            "absolute_violation": _distribution([float(row[f"{family}_absolute_violation"]) for row in case_rows]),
            "relative_violation": _distribution([float(row[f"{family}_relative_violation"]) for row in case_rows]),
        }
        for family in FAMILIES
    }
    summary = {
        "scope": "RAWLS24_LAYER_A_121_FAILURE_NUMERICAL_AUDIT_PRE_FIX",
        "status": "COMPLETE_DIAGNOSTIC_ONLY_NO_TOLERANCE_CHANGE",
        "case_count": len(case_rows),
        "failure_categories": categories,
        "failure_stage_scenario_counts": stages,
        "violation_distributions": distributions,
        "input_sample_table_sha256": sha256_file(SOURCE / "samples.csv"),
        "source_results_manifest_sha256": sha256_file(SOURCE / "simulation_manifest.json"),
        "source_results_hashes_sha256": sha256_file(SOURCE / "HASHES.sha256"),
        "data_identity": fixture["dataset_identity"],
        "neutral_fixture_sha256": fixture["neutral_fixture_sha256"],
        "scientific_changes": False,
        "tolerance_changes": False,
    }
    summary["summary_sha256"] = canonical_json_sha256(summary)
    OUTPUT.mkdir(parents=True)
    with (OUTPUT / "case_audit.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(case_rows[0]))
        writer.writeheader()
        writer.writerows(case_rows)
    (OUTPUT / "case_audit.json").write_text(json.dumps(detail, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    (OUTPUT / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    paths = sorted(path for path in OUTPUT.iterdir() if path.name != "HASHES.sha256")
    (OUTPUT / "HASHES.sha256").write_text("\n".join(f"{sha256_file(path)}  {path.name}" for path in paths) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
