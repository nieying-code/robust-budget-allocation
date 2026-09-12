"""Formal E2-A 205-row recertification and 3795-row non-regression evidence."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from robust_budget_allocation.algorithms.qfr_final_a1 import (
    FINAL_A1_IDENTITY,
    FINAL_A1_IMPLEMENTATION_REVISION,
)
from robust_budget_allocation.formal.e2a import CASES, SAMPLE_SHA256, summarize_case
from robust_budget_allocation.io.hashing import sha256_file


ROOT = Path(__file__).resolve().parents[1]
E2A = ROOT / "formal_results/e2_final/e2a"
RECERT = E2A / "recertification"


def rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_formal_recertification_is_exact_original_205_and_complete():
    initial = rows(RECERT / "e2a_initial_205_retained_failures.csv")
    recertified = rows(RECERT / "e2a_205_formal_recertified.csv")
    evidence = rows(RECERT / "e2a_205_formal_recertification_evidence.csv")
    assert len(initial) == len(recertified) == len(evidence) == 205
    expected = [(row["case_id"], row["simulation_id"], row["input_sha256"]) for row in initial]
    assert [(row["case_id"], row["simulation_id"], row["input_sha256"]) for row in recertified] == expected
    assert [(row["case_id"], row["simulation_id"], row["input_sha256"]) for row in evidence] == expected
    assert all(row["certificate_status"] == "PASS" for row in recertified)
    assert all(row["Q"] and row["F"] and row["z"] for row in evidence)
    assert all(row["algorithm_identity"] == FINAL_A1_IDENTITY for row in evidence)
    assert all(row["implementation_revision"] == FINAL_A1_IMPLEMENTATION_REVISION for row in evidence)
    assert sum(int(row["witness_gated_retry_count"]) for row in evidence) == 284
    assert sum(int(row["scaled_retry_optimal_count"]) for row in evidence) == 284
    assert sum(int(row["mapped_back_validation_pass_count"]) for row in evidence) == 284


def test_all_3795_previously_certified_rows_are_scientifically_invariant():
    comparisons = rows(RECERT / "e2a_3795_previously_certified_regression.csv")
    assert len(comparisons) == 3795
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
    assert all(all(row[field] == "True" for field in flags) for row in comparisons)
    summary = json.loads((RECERT / "e2a_3795_regression_summary.json").read_text(encoding="utf-8"))
    assert summary["population_checked"] == summary["invariant"] == 3795
    assert summary["changed"] == 0


def test_final_population_is_4000_of_4000_without_current_failures():
    scientific = rows(E2A / "e2a_scientific_results.csv")
    paired = rows(E2A / "e2a_paired_baseline_comparison.csv")
    retained = rows(E2A / "e2a_retained_failures.csv")
    assert len(scientific) == len(paired) == 4000
    assert retained == []
    assert all(row["certificate_status"] == "PASS" for row in scientific)
    for case_id in CASES:
        block = [row for row in scientific if row["case_id"] == case_id]
        assert len(block) == 1000
        assert [row["simulation_id"] for row in block] == [
            f"LA-{index:04d}" for index in range(1, 1001)
        ]


def test_final_summaries_are_rebuilt_from_complete_rows():
    scientific = rows(E2A / "e2a_scientific_results.csv")
    summary = json.loads((E2A / "e2a_summary.json").read_text(encoding="utf-8"))
    assert summary["certified"] == 4000 and summary["failed"] == 0
    assert summary["sample_sha256"] == SAMPLE_SHA256
    assert summary["baseline_reused"] == 1000 and summary["baseline_rerun"] is False
    assert summary["algorithm_identity"] == FINAL_A1_IDENTITY
    assert summary["implementation_revision"] == FINAL_A1_IMPLEMENTATION_REVISION
    for case_id in CASES:
        rebuilt = summarize_case([row for row in scientific if row["case_id"] == case_id])
        assert rebuilt == summary["cases"][case_id]


def test_final_manifest_preserves_scientific_guardrails():
    manifest = json.loads((E2A / "e2a_manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "COMPLETE_4000_OF_4000_CERTIFIED"
    assert manifest["algorithm_identity"] == FINAL_A1_IDENTITY
    assert manifest["implementation_revision"] == FINAL_A1_IMPLEMENTATION_REVISION
    assert manifest["sample_table"]["sha256"] == SAMPLE_SHA256
    assert manifest["baseline_reuse"]["rows"] == 1000
    assert manifest["baseline_reuse"]["rerun"] is False
    assert manifest["execution"] == {
        "initial_attempted": 4000,
        "initial_certified": 3795,
        "initial_failed": 205,
        "formally_recertified": 205,
        "final_certified": 4000,
        "final_failed": 0,
    }
    guardrails = manifest["guardrails"]
    assert guardrails["resampled"] is guardrails["dropped"] is False
    assert guardrails["parameter_tuning"] is False
    assert guardrails["model_changed"] is guardrails["tolerance_changed"] is False
    assert guardrails["scientific_design_changed"] is False
    assert guardrails["E2_B_runs"] == guardrails["E2_C_runs"] == guardrails["E2_D_runs"] == 0


def test_e2a_and_recertification_hash_inventories_are_complete():
    for directory in (E2A, RECERT):
        entries = [
            line.split("  ", 1)
            for line in (directory / "HASHES.sha256").read_text(encoding="utf-8").splitlines()
        ]
        expected = {path.name for path in directory.iterdir() if path.is_file()} - {"HASHES.sha256"}
        assert {name for _, name in entries} == expected
        assert all(sha256_file(directory / name) == digest for digest, name in entries)

