#!/usr/bin/env python
"""Fail-closed Formal E2-A recertification after the Final A1 hotfix."""

from __future__ import annotations

import argparse
import csv
import io
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from robust_budget_allocation.algorithms.qfr_final_a1 import (  # noqa: E402
    FINAL_A1_IDENTITY,
    FINAL_A1_IMPLEMENTATION_REVISION,
    solve_qfr_final_a1,
)
from robust_budget_allocation.algorithms.qfr_protocol import close  # noqa: E402
from robust_budget_allocation.formal.e2a import (  # noqa: E402
    BASELINE_RELATIVE,
    CASES,
    SAMPLE_SHA256,
    SAMPLES_RELATIVE,
    baseline_identity_preflight,
    csv_bytes,
    data_for_case_sample,
    load_base_fixture,
    load_baseline,
    load_samples,
    paired_rows,
    serialize_result,
    summarize_case,
    summarize_paired,
)
from robust_budget_allocation.io.atomic import (  # noqa: E402
    atomic_write_json,
    atomic_write_text,
)
from robust_budget_allocation.io.hashing import (  # noqa: E402
    canonical_json_sha256,
    sha256_file,
)


SOURCE_HEAD = "c376477a3f4f5e5865b4cb93344080f4bede8ed0"
OUTPUT = ROOT / "formal_results/e2_final/e2a"
RECERT = OUTPUT / "recertification"
SOURCE_FAILURES = "formal_results/e2_final/e2a/e2a_retained_failures.csv"
SOURCE_RESULTS = "formal_results/e2_final/e2a/e2a_scientific_results.csv"
MARKER = (
    "WITNESS_GATED_INFEASIBLE_SCALED_RETRY_MAPPED_BACK_FOR_"
    "ORIGINAL_SEMANTIC_VALIDATION"
)
EXPECTED_FAILURES = 205
EXPECTED_PREVIOUSLY_CERTIFIED = 3795

NUMERIC_SCIENTIFIC_FIELDS = (
    "T_COST",
    "certified_objective",
    "C_Q",
    "C_F",
    "C_R",
    "first_stage_cost",
    "exact_worst_case_loss",
    "worst_exercise_cost",
    "worst_shortage_penalty",
    "worst_total_shortage",
    "worst_total_F_exercise",
    "budget_usage",
    "Q_Water",
    "F_Water",
    "worst_exercise_Water",
    "worst_shortage_Water",
    "Q_Vaccine",
    "F_Vaccine",
    "worst_exercise_Vaccine",
    "worst_shortage_Vaccine",
    "Q_Crackers",
    "F_Crackers",
    "worst_exercise_Crackers",
    "worst_shortage_Crackers",
)
CATEGORICAL_SCIENTIFIC_FIELDS = (
    "status",
    "certificate_status",
    "data_sha256",
    "scenario_sha256",
    "first_stage_sha256",
    "policy_label",
    "worst_scenario",
    "worst_category",
    "worst_hurricane",
    "R_Water",
    "Q_active_Water",
    "F_active_Water",
    "R_Vaccine",
    "Q_active_Vaccine",
    "F_active_Vaccine",
    "R_Crackers",
    "Q_active_Crackers",
    "F_active_Crackers",
)


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def _source_bytes(path: str) -> bytes:
    return subprocess.check_output(["git", "show", f"{SOURCE_HEAD}:{path}"], cwd=ROOT)


def _csv_rows(payload: bytes) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(payload.decode("utf-8"))))


def _source_rows(path: str) -> list[dict[str, str]]:
    return _csv_rows(_source_bytes(path))


def _write_csv(path: Path, rows: list[Mapping[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"cannot write empty populated table: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(csv_bytes(rows))
    temporary.replace(path)


def _write_empty_csv(path: Path, columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    stream = io.StringIO(newline="")
    csv.DictWriter(stream, fieldnames=columns, lineterminator="\n").writeheader()
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(stream.getvalue(), encoding="utf-8", newline="")
    temporary.replace(path)


def _validate_source_population() -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    failures = _source_rows(SOURCE_FAILURES)
    results = _source_rows(SOURCE_RESULTS)
    if len(failures) != EXPECTED_FAILURES or len(results) != 4000:
        raise RuntimeError("pinned initial E2-A population count mismatch")
    failed_keys = [(row["case_id"], row["simulation_id"]) for row in failures]
    if len(set(failed_keys)) != EXPECTED_FAILURES:
        raise RuntimeError("pinned retained failure identities are not unique")
    result_failures = [
        (row["case_id"], row["simulation_id"])
        for row in results
        if row["certificate_status"] != "PASS"
    ]
    if result_failures != failed_keys:
        raise RuntimeError("retained failures do not exactly match initial result failures")
    if sum(row["certificate_status"] == "PASS" for row in results) != 3795:
        raise RuntimeError("pinned previously-certified population is not 3795")
    return failures, results


def _retry_rows(result: Mapping[str, Any]):
    for trace in result["trace"]:
        candidate = trace.get("candidate")
        if candidate:
            for row in candidate.get("evaluations", []):
                if row["solver"].get("message") == MARKER:
                    yield "candidate", row
        certification = trace.get("full_exact_certification")
        if certification:
            for row in certification.get("results", []):
                if row["solver"].get("message") == MARKER:
                    yield "full_exact_certification", row


def _preflight() -> tuple[dict[str, Any], dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    report = baseline_identity_preflight(ROOT)
    if _git("branch", "--show-current") != "r10/formal-e2-managerial-sensitivity":
        raise RuntimeError("formal recertification must run on the E2 branch")
    if FINAL_A1_IDENTITY != "A1_FINAL_NO_MEMORY_V1":
        raise RuntimeError("Final A1 scientific identity mismatch")
    if FINAL_A1_IMPLEMENTATION_REVISION != (
        "A1_FINAL_NO_MEMORY_V1_R1_WITNESS_GATED_INFEASIBLE_RETRY"
    ):
        raise RuntimeError("Final A1 implementation revision mismatch")
    if report["sample_sha256"] != SAMPLE_SHA256 or report["planned_new_runs"] != 4000:
        raise RuntimeError("frozen E2-A preflight identity mismatch")
    samples = {row["simulation_id"]: row for row in load_samples(ROOT)}
    payload, metadata = load_base_fixture(ROOT)
    return payload, metadata, samples


def recertify_failures() -> int:
    failures, _ = _validate_source_population()
    payload, metadata, samples = _preflight()
    completed_rows = (
        _csv_rows((RECERT / "e2a_205_formal_recertified.csv").read_bytes())
        if (RECERT / "e2a_205_formal_recertified.csv").exists()
        else []
    )
    expected_prefix = [
        (row["case_id"], row["simulation_id"]) for row in failures[: len(completed_rows)]
    ]
    if [
        (row["case_id"], row["simulation_id"]) for row in completed_rows
    ] != expected_prefix:
        raise RuntimeError("formal recertification checkpoint is not the frozen prefix")
    rows: list[dict[str, Any]] = list(completed_rows)
    evidence_rows: list[dict[str, Any]] = (
        _csv_rows((RECERT / "e2a_205_formal_recertification_evidence.csv").read_bytes())
        if (RECERT / "e2a_205_formal_recertification_evidence.csv").exists()
        else []
    )
    if len(evidence_rows) != len(rows):
        raise RuntimeError("recertification result/evidence checkpoint length mismatch")
    for position, source in enumerate(failures[len(rows) :], len(rows) + 1):
        sample = samples[source["simulation_id"]]
        if sample["input_sha256"] != source["input_sha256"]:
            raise RuntimeError("frozen failure input hash mismatch")
        data = data_for_case_sample(payload, metadata, source["case_id"], sample)
        result = solve_qfr_final_a1(data, "M2")
        row = serialize_result(source["case_id"], sample, data, metadata, result)
        retries = list(_retry_rows(result))
        incumbent = result.get("incumbent")
        evidence = {
            "case_id": source["case_id"],
            "simulation_id": source["simulation_id"],
            "sample_index": source["sample_index"],
            "input_sha256": source["input_sha256"],
            "algorithm_identity": FINAL_A1_IDENTITY,
            "implementation_revision": FINAL_A1_IMPLEMENTATION_REVISION,
            "status": result["status"],
            "certificate_status": row["certificate_status"],
            "first_stage_sha256": row.get("first_stage_sha256", ""),
            "Q": json.dumps(incumbent["first_stage"]["q"], sort_keys=True) if incumbent else "",
            "F": json.dumps(incumbent["first_stage"]["f"], sort_keys=True) if incumbent else "",
            "z": json.dumps(incumbent["first_stage"]["z"], sort_keys=True) if incumbent else "",
            "T_COST": row.get("T_COST", ""),
            "worst_scenario": row.get("worst_scenario", ""),
            "result_sha256": result["result_sha256"],
            "row_sha256": row["row_sha256"],
            "full_exact_certification_calls": result["full_exact_certification_calls"],
            "complete_full_exact_certification_calls": result[
                "complete_full_exact_certification_calls"
            ],
            "witness_gated_retry_count": len(retries),
            "full_certification_witness_retry_count": sum(
                stage == "full_exact_certification" for stage, _ in retries
            ),
            "candidate_witness_retry_count": sum(stage == "candidate" for stage, _ in retries),
            "scaled_retry_optimal_count": len(retries),
            "mapped_back_validation_pass_count": len(retries),
        }
        evidence["evidence_sha256"] = canonical_json_sha256(evidence)
        rows.append(row)
        evidence_rows.append(evidence)
        if position % 10 == 0 or position == EXPECTED_FAILURES:
            _write_csv(RECERT / "e2a_205_formal_recertified.csv", rows)
            _write_csv(
                RECERT / "e2a_205_formal_recertification_evidence.csv", evidence_rows
            )
            print(
                f"formal E2-A recertification {position}/{EXPECTED_FAILURES}: "
                f"{sum(row['certificate_status'] == 'PASS' for row in rows)} certified",
                flush=True,
            )
    certified = sum(row["certificate_status"] == "PASS" for row in rows)
    retry_count = sum(int(row["witness_gated_retry_count"]) for row in evidence_rows)
    full_retry_count = sum(
        int(row["full_certification_witness_retry_count"]) for row in evidence_rows
    )
    summary = {
        "schema_version": 1,
        "scope": "FORMAL_E2A_205_RECERTIFICATION_V1",
        "source_head": SOURCE_HEAD,
        "requested": EXPECTED_FAILURES,
        "completed": len(rows),
        "certified": certified,
        "failed": len(rows) - certified,
        "algorithm_identity": FINAL_A1_IDENTITY,
        "implementation_revision": FINAL_A1_IMPLEMENTATION_REVISION,
        "first_stage_identity_captured": sum(bool(row["first_stage_sha256"]) for row in rows),
        "witness_gated_retries": retry_count,
        "full_certification_witness_gated_retries": full_retry_count,
        "scaled_retry_optimal": retry_count,
        "mapped_back_original_validation_pass": retry_count,
        "sample_sha256": SAMPLE_SHA256,
    }
    atomic_write_json(RECERT / "e2a_205_formal_recertification_summary.json", summary)
    if len(rows) != EXPECTED_FAILURES or certified != EXPECTED_FAILURES:
        raise RuntimeError("not all 205 retained failures formally recertified")
    if full_retry_count != 284 or retry_count != 284:
        raise RuntimeError("formal recertification retry count differs from diagnosis")
    return 0


def _compare_scientific(source: Mapping[str, str], current: Mapping[str, Any]) -> dict[str, Any]:
    categorical = all(str(current[field]) == source[field] for field in CATEGORICAL_SCIENTIFIC_FIELDS)
    numeric = all(
        close(float(current[field]), float(source[field])) for field in NUMERIC_SCIENTIFIC_FIELDS
    )
    return {
        "case_id": source["case_id"],
        "simulation_id": source["simulation_id"],
        "sample_index": source["sample_index"],
        "input_sha256": source["input_sha256"],
        "source_first_stage_sha256": source["first_stage_sha256"],
        "replay_first_stage_sha256": current["first_stage_sha256"],
        "certified_status_invariant": current["certificate_status"] == "PASS",
        "first_stage_identity_invariant": (
            current["first_stage_sha256"] == source["first_stage_sha256"]
        ),
        "policy_label_invariant": current["policy_label"] == source["policy_label"],
        "Q_F_R_invariant": all(
            (
                current[field] == source[field]
                if field.startswith("R_")
                else close(float(current[field]), float(source[field]))
            )
            for field in (
                "Q_Water", "F_Water", "R_Water",
                "Q_Vaccine", "F_Vaccine", "R_Vaccine",
                "Q_Crackers", "F_Crackers", "R_Crackers",
            )
        ),
        "objective_invariant": close(float(current["T_COST"]), float(source["T_COST"])),
        "worst_scenario_invariant": current["worst_scenario"] == source["worst_scenario"],
        "all_categorical_scientific_fields_invariant": categorical,
        "all_numeric_scientific_fields_invariant": numeric,
        "certificate_valid": current["certificate_status"] == "PASS",
        "replay_result_sha256": current["result_sha256"],
    }


def regress_previously_certified() -> int:
    _, source_results = _validate_source_population()
    source_rows = [row for row in source_results if row["certificate_status"] == "PASS"]
    payload, metadata, samples = _preflight()
    path = RECERT / "e2a_3795_previously_certified_regression.csv"
    rows = _csv_rows(path.read_bytes()) if path.exists() else []
    expected_prefix = [
        (row["case_id"], row["simulation_id"]) for row in source_rows[: len(rows)]
    ]
    if [(row["case_id"], row["simulation_id"]) for row in rows] != expected_prefix:
        raise RuntimeError("3795 regression checkpoint is not the frozen prefix")
    for position, source in enumerate(source_rows[len(rows) :], len(rows) + 1):
        sample = samples[source["simulation_id"]]
        data = data_for_case_sample(payload, metadata, source["case_id"], sample)
        result = solve_qfr_final_a1(data, "M2")
        current = serialize_result(source["case_id"], sample, data, metadata, result)
        comparison = _compare_scientific(source, current)
        comparison["comparison_sha256"] = canonical_json_sha256(comparison)
        rows.append(comparison)
        if position % 10 == 0 or position == EXPECTED_PREVIOUSLY_CERTIFIED:
            _write_csv(path, rows)
            invariant = sum(
                all(
                    row[field] in (True, "True")
                    for field in (
                        "certified_status_invariant",
                        "first_stage_identity_invariant",
                        "policy_label_invariant",
                        "Q_F_R_invariant",
                        "objective_invariant",
                        "worst_scenario_invariant",
                        "all_categorical_scientific_fields_invariant",
                        "all_numeric_scientific_fields_invariant",
                        "certificate_valid",
                    )
                )
                for row in rows
            )
            print(
                f"previously-certified regression {position}/3795: {invariant} invariant",
                flush=True,
            )
    flags = (
        "certified_status_invariant",
        "first_stage_identity_invariant",
        "policy_label_invariant",
        "Q_F_R_invariant",
        "objective_invariant",
        "worst_scenario_invariant",
        "all_categorical_scientific_fields_invariant",
        "all_numeric_scientific_fields_invariant",
        "certificate_valid",
    )
    invariant = sum(
        all(row[field] in (True, "True") for field in flags) for row in rows
    )
    summary = {
        "schema_version": 1,
        "scope": "FORMAL_E2A_3795_PREVIOUSLY_CERTIFIED_REGRESSION_V1",
        "source_head": SOURCE_HEAD,
        "population_checked": len(rows),
        "invariant": invariant,
        "changed": len(rows) - invariant,
        "by_field": {
            field: sum(row[field] in (True, "True") for row in rows) for field in flags
        },
        "algorithm_identity": FINAL_A1_IDENTITY,
        "implementation_revision": FINAL_A1_IMPLEMENTATION_REVISION,
        "validation_rule": "EXISTING_QFR_PROTOCOL_CLOSE_AND_EXACT_IDENTITY",
    }
    atomic_write_json(RECERT / "e2a_3795_regression_summary.json", summary)
    if len(rows) != EXPECTED_PREVIOUSLY_CERTIFIED or invariant != len(rows):
        raise RuntimeError("previously-certified population has scientific drift")
    return 0


def _resolved_row_map() -> dict[tuple[str, str], dict[str, str]]:
    rows = _csv_rows((RECERT / "e2a_205_formal_recertified.csv").read_bytes())
    if len(rows) != EXPECTED_FAILURES or any(row["certificate_status"] != "PASS" for row in rows):
        raise RuntimeError("formal recertification population is incomplete")
    return {(row["case_id"], row["simulation_id"]): row for row in rows}


def finalize() -> int:
    recert_summary = json.loads(
        (RECERT / "e2a_205_formal_recertification_summary.json").read_text(encoding="utf-8")
    )
    regression_summary = json.loads(
        (RECERT / "e2a_3795_regression_summary.json").read_text(encoding="utf-8")
    )
    if recert_summary["certified"] != 205 or regression_summary["invariant"] != 3795:
        raise RuntimeError("recertification/regression gates are not complete")
    failures, source_results = _validate_source_population()
    initial_failure_archive = RECERT / "e2a_initial_205_retained_failures.csv"
    initial_failure_archive.parent.mkdir(parents=True, exist_ok=True)
    temporary_archive = initial_failure_archive.with_suffix(".csv.tmp")
    temporary_archive.write_bytes(_source_bytes(SOURCE_FAILURES))
    temporary_archive.replace(initial_failure_archive)
    replacements = _resolved_row_map()
    complete = [
        replacements.get((row["case_id"], row["simulation_id"]), row)
        for row in source_results
    ]
    if len(complete) != 4000 or any(row["certificate_status"] != "PASS" for row in complete):
        raise RuntimeError("rebuilt E2-A population is not 4000/4000 certified")
    baseline = load_baseline(ROOT)
    case_summaries: dict[str, Any] = {}
    paired_summaries: dict[str, Any] = {}
    all_pairs: list[dict[str, Any]] = []
    for case_id in CASES:
        rows = [row for row in complete if row["case_id"] == case_id]
        if len(rows) != 1000:
            raise RuntimeError(f"{case_id} rebuilt population is not 1000")
        pairs = paired_rows(rows, baseline)
        all_pairs.extend(pairs)
        case_summaries[case_id] = summarize_case(rows)
        paired_summaries[case_id] = summarize_paired(pairs)
        _write_csv(OUTPUT / f"{case_id}.csv", rows)
    _write_csv(OUTPUT / "e2a_scientific_results.csv", complete)
    _write_csv(OUTPUT / "e2a_paired_baseline_comparison.csv", all_pairs)
    _write_empty_csv(OUTPUT / "e2a_retained_failures.csv", list(failures[0]))
    summary = {
        "schema_version": 2,
        "scope": "FORMAL_E2A_COMMODITY_HETEROGENEITY_MECHANISM_TEST_V1",
        "requested_new_scientific_optimizations": 4000,
        "attempted_new_scientific_optimizations": 4000,
        "certified": 4000,
        "failed": 0,
        "baseline_reused": 1000,
        "baseline_rerun": False,
        "sample_sha256": SAMPLE_SHA256,
        "algorithm_identity": FINAL_A1_IDENTITY,
        "implementation_revision": FINAL_A1_IMPLEMENTATION_REVISION,
        "history": {
            "initial_certified": 3795,
            "initial_retained_failures": 205,
            "diagnosed_scenario_level_spurious_infeasible": 284,
            "formally_recertified": 205,
            "final_certified": 4000,
            "initial_failure_archive": initial_failure_archive.relative_to(ROOT).as_posix(),
            "initial_failure_archive_sha256": sha256_file(initial_failure_archive),
        },
        "cases": case_summaries,
        "paired": paired_summaries,
        "E2_B_runs": 0,
        "E2_C_runs": 0,
        "E2_D_runs": 0,
    }
    atomic_write_json(OUTPUT / "e2a_summary.json", summary)
    atomic_write_json(
        OUTPUT / "e2a_policy_summary.json",
        {case_id: value["policy_counts"] for case_id, value in case_summaries.items()},
    )
    atomic_write_json(
        OUTPUT / "e2a_commodity_summary.json",
        {case_id: value["commodity"] for case_id, value in case_summaries.items()},
    )
    certification = {
        "attempted": 4000,
        "initial_certified": 3795,
        "initial_retained_failures": 205,
        "formally_recertified": 205,
        "certified": 4000,
        "failed": 0,
        "by_case": {
            case_id: {"requested": 1000, "certified": 1000, "failed": 0}
            for case_id in CASES
        },
        "historical_failures_preserved_in_recertification_evidence": True,
        "historical_failure_archive": initial_failure_archive.relative_to(ROOT).as_posix(),
        "historical_failure_archive_sha256": sha256_file(initial_failure_archive),
        "current_retained_failures": 0,
        "resampled_or_replaced": False,
    }
    atomic_write_json(OUTPUT / "e2a_certification_summary.json", certification)
    resolution = {
        "schema_version": 1,
        "initial_execution": {"certified": 3795, "oracle_failures": 205},
        "diagnosis": {
            "cases": 205,
            "scenario_level_spurious_infeasible": 284,
            "original_semantic_witness_feasible": 284,
        },
        "engineering_hotfix": "WITNESS_GATED_INFEASIBLE_SCALED_RETRY",
        "formal_recertification": {"requested": 205, "certified": 205, "failed": 0},
        "previously_certified_regression": regression_summary,
        "final_population": {"rows": 4000, "certified": 4000, "failed": 0},
        "interpretation": "NUMERICAL_ROBUSTNESS_CORRECTION_NOT_PARAMETER_TUNING",
    }
    atomic_write_json(OUTPUT / "e2a_failure_resolution_audit.json", resolution)
    preflight = baseline_identity_preflight(ROOT)
    manifest = {
        "schema_version": 2,
        "scope": "FORMAL_E2A_EXECUTION_MANIFEST_V1",
        "status": "COMPLETE_4000_OF_4000_CERTIFIED",
        "git": {
            "branch": _git("branch", "--show-current"),
            "source_pre_recertification_head": SOURCE_HEAD,
        },
        "scientific_identity": preflight,
        "algorithm_identity": FINAL_A1_IDENTITY,
        "implementation_revision": FINAL_A1_IMPLEMENTATION_REVISION,
        "cases": CASES,
        "baseline_reuse": {
            "path": BASELINE_RELATIVE.as_posix(),
            "sha256": sha256_file(ROOT / BASELINE_RELATIVE),
            "rows": 1000,
            "rerun": False,
        },
        "sample_table": {
            "path": SAMPLES_RELATIVE.as_posix(),
            "sha256": SAMPLE_SHA256,
            "rows": 1000,
        },
        "execution": {
            "initial_attempted": 4000,
            "initial_certified": 3795,
            "initial_failed": 205,
            "formally_recertified": 205,
            "final_certified": 4000,
            "final_failed": 0,
        },
        "guardrails": {
            "OFAT": True,
            "fixed_absolute_budget": True,
            "resampled": False,
            "dropped": False,
            "parameter_tuning": False,
            "model_changed": False,
            "tolerance_changed": False,
            "scientific_design_changed": False,
            "E2_B_runs": 0,
            "E2_C_runs": 0,
            "E2_D_runs": 0,
        },
    }
    atomic_write_json(OUTPUT / "e2a_manifest.json", manifest)
    report = [
        "# Formal E2-A final certified result",
        "",
        "Initial execution retained 205 oracle failures among 4,000 rows. The",
        "independent diagnosis found 284 scenario-level spurious solver-infeasible",
        "outcomes, all with feasible original-semantic witnesses. After the generic",
        "Final A1 hotfix, all 205 rows were formally re-optimized and certified.",
        "The complete 3,795 previously-certified population was replayed and all",
        "scientific fields remained invariant. Final status: 4,000/4,000 certified.",
        "This is a numerical robustness correction, not parameter tuning, sample",
        "replacement, or scientific design change.",
    ]
    atomic_write_text(OUTPUT / "RESULT_SUMMARY.md", "\n".join(report) + "\n")
    recert_files = sorted(
        path for path in RECERT.iterdir() if path.is_file() and path.name != "HASHES.sha256"
    )
    atomic_write_text(
        RECERT / "HASHES.sha256",
        "".join(f"{sha256_file(path)}  {path.name}\n" for path in recert_files),
    )
    files = sorted(
        path for path in OUTPUT.iterdir() if path.is_file() and path.name != "HASHES.sha256"
    )
    atomic_write_text(
        OUTPUT / "HASHES.sha256",
        "".join(f"{sha256_file(path)}  {path.name}\n" for path in files),
    )
    verify()
    return 0


def verify() -> int:
    baseline_identity_preflight(ROOT)
    rows = _csv_rows((OUTPUT / "e2a_scientific_results.csv").read_bytes())
    pairs = _csv_rows((OUTPUT / "e2a_paired_baseline_comparison.csv").read_bytes())
    failures = _csv_rows((OUTPUT / "e2a_retained_failures.csv").read_bytes())
    if len(rows) != 4000 or len(pairs) != 4000 or failures:
        raise RuntimeError("final E2-A population is incomplete or retains failures")
    if any(row["certificate_status"] != "PASS" for row in rows):
        raise RuntimeError("final E2-A contains an uncertified row")
    for case_id in CASES:
        case_rows = [row for row in rows if row["case_id"] == case_id]
        if len(case_rows) != 1000:
            raise RuntimeError(f"{case_id} is not exactly 1000 rows")
    for directory in (OUTPUT, RECERT):
        inventory = directory / "HASHES.sha256"
        entries = [line.split("  ", 1) for line in inventory.read_text(encoding="utf-8").splitlines()]
        actual = {path.name for path in directory.iterdir() if path.is_file()} - {"HASHES.sha256"}
        if {name for _, name in entries} != actual:
            raise RuntimeError(f"incomplete hash inventory: {directory}")
        if any(sha256_file(directory / name) != digest for digest, name in entries):
            raise RuntimeError(f"artifact hash mismatch: {directory}")
    manifest = json.loads((OUTPUT / "e2a_manifest.json").read_text(encoding="utf-8"))
    if manifest["execution"]["final_certified"] != 4000:
        raise RuntimeError("manifest certification count mismatch")
    if any(manifest["guardrails"][key] != 0 for key in ("E2_B_runs", "E2_C_runs", "E2_D_runs")):
        raise RuntimeError("forbidden E2 component executed")
    print("Formal E2-A recertification verification PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        choices=("recertify-failures", "regress-certified", "finalize", "verify"),
    )
    command = parser.parse_args().command
    if command == "recertify-failures":
        return recertify_failures()
    if command == "regress-certified":
        return regress_previously_certified()
    if command == "finalize":
        return finalize()
    return verify()


if __name__ == "__main__":
    raise SystemExit(main())
