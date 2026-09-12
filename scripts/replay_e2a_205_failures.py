#!/usr/bin/env python
"""Capture complete diagnostic replay evidence for all retained E2-A failures."""

from __future__ import annotations

from collections import Counter
import csv
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from robust_budget_allocation.algorithms.qfr_final_a1 import FINAL_A1_IDENTITY, solve_qfr_final_a1  # noqa: E402
from robust_budget_allocation.algorithms.qfr_state import QFRFirstStage  # noqa: E402
from robust_budget_allocation.formal.e2a import (  # noqa: E402
    BUDGET, CASES, DESIGN_RELATIVE, SAMPLE_SHA256, data_for_case_sample,
    load_base_fixture, load_samples, read_csv,
)
from robust_budget_allocation.formal.e2a_diagnostics import (  # noqa: E402
    first_stage_evidence, scenario_diagnostic, taxonomy_counts,
)
from robust_budget_allocation.io.atomic import atomic_write_csv, atomic_write_json, atomic_write_text  # noqa: E402
from robust_budget_allocation.io.hashing import canonical_json_sha256, sha256_file  # noqa: E402

SOURCE = ROOT / "formal_results/e2_final/e2a/e2a_retained_failures.csv"
FORMAL_RESULTS = ROOT / "formal_results/e2_final/e2a/e2a_scientific_results.csv"
OUTPUT = ROOT / "formal_results/e2_final/e2a/diagnostics"
FINAL_A1_PATH = ROOT / "src/robust_budget_allocation/algorithms/qfr_final_a1.py"
ORACLE_PATH = ROOT / "src/robust_budget_allocation/algorithms/qfr_exact_oracle.py"
DETERMINISM_POSITIONS = (0, 51, 102, 153, 204)


def _git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def _failed_trace(result):
    candidates = [
        row for row in result["trace"]
        if row.get("full_exact_certification")
        and row["full_exact_certification"]["status"] != "complete"
    ]
    return candidates[-1] if candidates else None


def _decision_for_replay(result):
    failed = _failed_trace(result)
    if failed is not None:
        return QFRFirstStage.from_dict(failed["first_stage"]), failed, "FAILED_FULL_CERTIFICATION_DECISION"
    if result.get("incumbent") is not None:
        return QFRFirstStage.from_dict(result["incumbent"]["first_stage"]), None, "CERTIFIED_REPLAY_INCUMBENT"
    last = next((row for row in reversed(result["trace"]) if row.get("first_stage")), None)
    if last is None:
        raise RuntimeError("replay produced no first-stage decision")
    return QFRFirstStage.from_dict(last["first_stage"]), None, "LAST_AVAILABLE_REPLAY_DECISION"


def _json_cell(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def main():
    failures = read_csv(SOURCE)
    if len(failures) != 205:
        raise RuntimeError(f"retained failure population must be 205, found {len(failures)}")
    identities = [(row["case_id"], row["simulation_id"], row["input_sha256"]) for row in failures]
    if len(set(identities)) != 205:
        raise RuntimeError("retained failure identities are not unique")
    samples = {row["simulation_id"]: row for row in load_samples(ROOT)}
    payload, metadata = load_base_fixture(ROOT)
    original_result_sha = sha256_file(FORMAL_RESULTS)
    original_design_sha = sha256_file(ROOT / DESIGN_RELATIVE)
    original_a1_sha = sha256_file(FINAL_A1_PATH)
    original_oracle_sha = sha256_file(ORACLE_PATH)
    replay_rows, first_rows, scenario_rows, witness_rows = [], [], [], []
    deterministic_records = {}
    for position, source in enumerate(failures):
        case_id, simulation_id = source["case_id"], source["simulation_id"]
        sample = samples[simulation_id]
        if sample["input_sha256"] != source["input_sha256"]:
            raise RuntimeError("retained failure/sample input identity mismatch")
        data = data_for_case_sample(payload, metadata, case_id, sample)
        replay = solve_qfr_final_a1(data, "M2")
        decision, failed_trace, decision_role = _decision_for_replay(replay)
        first = first_stage_evidence(data, decision)
        recorded_failing = [] if failed_trace is None else [
            row["scenario_id"] for row in failed_trace["full_exact_certification"]["results"]
            if row["solver"]["status"] != "optimal"
        ]
        replay_row = {
            "case_id": case_id,
            "simulation_id": simulation_id,
            "sample_index": sample["sample_index"],
            "input_sha256": sample["input_sha256"],
            "original_status": source["status"],
            "original_failure_type": source["failure_type"],
            "original_result_sha256": source["result_sha256"],
            "replay_status": replay["status"],
            "reproduced_oracle_failure": replay["status"] == "oracle_failure" and failed_trace is not None,
            "failure_stage": "FULL_EXACT_CERTIFICATION" if failed_trace is not None else "NOT_REPRODUCED",
            "decision_role": decision_role,
            "first_stage_sha256": decision.sha256,
            "failing_scenarios": ";".join(recorded_failing),
            "failing_scenario_count": len(recorded_failing),
            "iterations": replay["iterations"],
            "complete_full_exact_certification_calls": replay["complete_full_exact_certification_calls"],
        }
        replay_rows.append(replay_row)
        first_row = {
            "case_id": case_id, "simulation_id": simulation_id, "sample_index": sample["sample_index"],
            "input_sha256": sample["input_sha256"], "decision_role": decision_role,
            "first_stage_sha256": first["first_stage_sha256"],
            "Q": _json_cell(first["Q"]), "F": _json_cell(first["F"]), "z": _json_cell(first["z"]),
            "first_stage_cost": first["first_stage_cost"], "B": first["budget"],
            "first_stage_cost_minus_B": first["first_stage_cost_minus_B"],
            "budget_violation": first["budget_violation"], "budget_reference_scale": first["budget_reference_scale"],
            "budget_tolerance": first["budget_tolerance"], "first_stage_feasibility_validation": first["validation_pass"],
            "validation_error": first["validation_error"] or "", "evidence_sha256": first["evidence_sha256"],
        }
        first_rows.append(first_row)
        current_scenarios = []
        for scenario in data.scenarios:
            diagnostic, witness = scenario_diagnostic(data, decision, scenario)
            row = {"case_id": case_id, "simulation_id": simulation_id, "sample_index": sample["sample_index"],
                   "input_sha256": sample["input_sha256"], "first_stage_sha256": decision.sha256, **diagnostic}
            scenario_rows.append(row)
            current_scenarios.append(row)
            if witness is not None:
                for family, values in witness["constraint_families"].items():
                    witness_rows.append({
                        "case_id": case_id, "simulation_id": simulation_id, "sample_index": sample["sample_index"],
                        "input_sha256": sample["input_sha256"], "first_stage_sha256": decision.sha256,
                        "scenario_id": scenario, "witness_sha256": witness["witness_sha256"],
                        "witness_not_optimum_or_certificate": True, "constraint_family": family,
                        "feasible": values["feasible"], "maximum_violation": values["maximum_violation"],
                        "reference_scale": values["reference_scale"], "applicable_tolerance": values["applicable_tolerance"],
                    })
        replay_row["infeasible_scenarios"] = ";".join(row["scenario_id"] for row in current_scenarios if row["production_termination"] == "infeasible")
        replay_row["scenario_taxonomy"] = _json_cell(taxonomy_counts(current_scenarios))
        replay_row["replay_evidence_sha256"] = canonical_json_sha256(replay_row)
        if position in DETERMINISM_POSITIONS:
            deterministic_records[(case_id, simulation_id)] = {
                "status": replay["status"], "first_stage_sha256": decision.sha256,
                "failing_scenarios": recorded_failing,
            }
        if (position + 1) % 5 == 0 or position == 204:
            print(f"diagnostic replay {position + 1}/205", flush=True)
    determinism_rows = []
    for position in DETERMINISM_POSITIONS:
        source = failures[position]
        case_id, simulation_id = source["case_id"], source["simulation_id"]
        data = data_for_case_sample(payload, metadata, case_id, samples[simulation_id])
        replay = solve_qfr_final_a1(data, "M2")
        decision, failed_trace, _ = _decision_for_replay(replay)
        failing = [] if failed_trace is None else [
            row["scenario_id"] for row in failed_trace["full_exact_certification"]["results"]
            if row["solver"]["status"] != "optimal"
        ]
        first = deterministic_records[(case_id, simulation_id)]
        stable = replay["status"] == first["status"] and decision.sha256 == first["first_stage_sha256"] and failing == first["failing_scenarios"]
        determinism_rows.append({"case_id": case_id, "simulation_id": simulation_id, "first_status": first["status"],
                                 "second_status": replay["status"], "first_stage_sha256": decision.sha256,
                                 "failing_scenarios": ";".join(failing), "stable": stable})
    if sha256_file(FORMAL_RESULTS) != original_result_sha or sha256_file(ROOT / DESIGN_RELATIVE) != original_design_sha:
        raise RuntimeError("formal E2-A results or scientific design changed during diagnostics")
    if sha256_file(FINAL_A1_PATH) != original_a1_sha or sha256_file(ORACLE_PATH) != original_oracle_sha:
        raise RuntimeError("Final A1/oracle changed during diagnostics")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    atomic_write_csv(OUTPUT / "e2a_205_failure_replay.csv", tuple(replay_rows[0]), replay_rows)
    atomic_write_csv(OUTPUT / "e2a_205_first_stage_evidence.csv", tuple(first_rows[0]), first_rows)
    atomic_write_csv(OUTPUT / "e2a_205_scenario_taxonomy.csv", tuple(scenario_rows[0]), scenario_rows)
    atomic_write_csv(OUTPUT / "e2a_205_witness_validation.csv", tuple(witness_rows[0]), witness_rows)
    atomic_write_csv(OUTPUT / "e2a_205_determinism_check.csv", tuple(determinism_rows[0]), determinism_rows)
    scenario_taxonomy = taxonomy_counts(scenario_rows)
    case_categories = Counter()
    multi_mechanism = 0
    for replay in replay_rows:
        taxonomy = json.loads(replay["scenario_taxonomy"])
        categories = {key[0] for key, count in taxonomy.items() if count and key != "OPTIMAL"}
        if not replay["reproduced_oracle_failure"]:
            categories.add("F")
        first = next(row for row in first_rows if row["case_id"] == replay["case_id"] and row["simulation_id"] == replay["simulation_id"])
        if first["first_stage_feasibility_validation"] is not True:
            categories.add("B")
        for category in categories:
            case_categories[category] += 1
        multi_mechanism += len(categories) > 1
    taxonomy = {
        "schema_version": 1, "scope": "E2A_205_FAILURE_TAXONOMY_V1",
        "requested": 205, "completed": len(replay_rows),
        "reproduced": sum(row["reproduced_oracle_failure"] for row in replay_rows),
        "non_reproduced": sum(not row["reproduced_oracle_failure"] for row in replay_rows),
        "first_stage_budget_or_feasibility_issue_cases": sum(row["first_stage_feasibility_validation"] != True for row in first_rows),
        "total_scenario_checks": len(scenario_rows), "scenario_taxonomy": scenario_taxonomy,
        "production_optimal": sum(row["production_status"] == "optimal" for row in scenario_rows),
        "production_infeasible": sum(row["production_termination"] == "infeasible" for row in scenario_rows),
        "production_other_failure": sum(row["production_status"] != "optimal" and row["production_termination"] != "infeasible" for row in scenario_rows),
        "scaled_attempted": sum(row["diagnostic_scaled_retry_attempted"] for row in scenario_rows),
        "scaled_optimal": sum(row["scaled_status"] == "optimal" for row in scenario_rows),
        "witness_scenarios": len(witness_rows) // 4,
        "witness_feasible_scenarios": sum(row["witness_feasible"] is True for row in scenario_rows),
        "witness_infeasible_scenarios": sum(row["witness_feasible"] is False for row in scenario_rows),
        "case_taxonomy_counts_overlapping": {key: case_categories.get(key, 0) for key in "ABCDEF"},
        "cases_with_multiple_failure_mechanisms": multi_mechanism,
        "determinism_subset": {"size": len(determinism_rows), "stable": sum(row["stable"] for row in determinism_rows)},
    }
    taxonomy["taxonomy_sha256"] = canonical_json_sha256(taxonomy)
    atomic_write_json(OUTPUT / "e2a_205_failure_taxonomy.json", taxonomy)
    manifest = {
        "schema_version": 1, "scope": "E2A_205_DIAGNOSTIC_MANIFEST_V1", "status": "COMPLETE",
        "git": {"branch": _git("branch", "--show-current"), "commit": _git("rev-parse", "HEAD"), "tree": _git("rev-parse", "HEAD^{tree}")},
        "population": {"source": SOURCE.relative_to(ROOT).as_posix(), "sha256": sha256_file(SOURCE), "count": 205},
        "identity": {"sample_sha256": SAMPLE_SHA256, "budget": BUDGET, "algorithm": FINAL_A1_IDENTITY},
        "protected_hashes": {"formal_scientific_results": original_result_sha, "scientific_design": original_design_sha,
                             "final_a1": original_a1_sha, "exact_oracle": original_oracle_sha},
        "guardrails": {"diagnostic_only": True, "formal_results_overwritten": False, "Final_A1_modified": False,
                       "scientific_design_modified": False, "E2_B_runs": 0, "E2_C_runs": 0, "E2_D_runs": 0},
        "taxonomy_sha256": taxonomy["taxonomy_sha256"],
    }
    atomic_write_json(OUTPUT / "e2a_205_diagnostic_manifest.json", manifest)
    files = sorted(path for path in OUTPUT.iterdir() if path.is_file() and path.name != "HASHES.sha256")
    atomic_write_text(OUTPUT / "HASHES.sha256", "".join(f"{sha256_file(path)}  {path.name}\n" for path in files))
    print(json.dumps(taxonomy, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
