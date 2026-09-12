"""Solver-free checks for the Formal E2-D common-reference audit."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from robust_budget_allocation.formal.e2d_audit import (
    OUTPUT, claim_rows, common_reference_rows, paired_tables, preflight, summaries,
)

ROOT = Path(__file__).resolve().parents[1]


def _rows(name: str) -> list[dict[str, str]]:
    with (ROOT / OUTPUT / name).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_preflight_preserves_all_frozen_hash_inventories():
    report = preflight(ROOT)
    assert report["status"] == "PASS"
    assert report["e1_rows"] == 1000 and report["e2d_rows"] == 5000
    assert set(report["frozen_hashes"]) == {
        "e1_HASHES", "e2a_HASHES", "e2a_diagnostics_HASHES",
        "e2a_recertification_HASHES", "e2b_HASHES", "e2c_HASHES", "e2d_HASHES",
    }
    assert report["new_scientific_optimization_runs"] == 0


def test_common_reference_population_and_baseline_anchor():
    rows, anchor = common_reference_rows(ROOT)
    assert len(rows) == 6000
    assert anchor["tested"] == anchor["passed"] == 1000 and anchor["failed"] == 0
    assert {cell: sum(row["cell"] == cell for row in rows) for cell in set(row["cell"] for row in rows)}
    assert all(row["beta_ref"] == 4.0 for row in rows)
    assert all(row["lambda_ref_Water"] == row["lambda_ref_Vaccine"] == row["lambda_ref_Crackers"] == 1.0 for row in rows)


def test_reference_formula_is_exactly_component_reconstruction():
    rows, _ = common_reference_rows(ROOT)
    for row in rows:
        assert abs(row["T_COST_REF"] - (row["first_stage_cost"] + row["emergency_expenditure"] + row["reference_shortage_loss"])) < 1e-6
        assert abs(row["reference_shortage_loss"] - sum(row[f"reference_shortage_loss_{item}"] for item in ("Water", "Vaccine", "Crackers"))) < 1e-6


def test_paired_identity_and_summary_verdicts():
    common, _ = common_reference_rows(ROOT)
    beta, priority = paired_tables(common)
    assert len(beta) == 1000 and len(priority) == 3000
    summary = summaries(common, beta, priority)
    assert summary["diminishing_response_verdict"] == "PARTIALLY_SUPPORTED"
    crowd = summary["priority_crowding_out"]
    assert all(value["TARGET_BENEFIT"] and value["NON_TARGET_CROWDING_OUT"] for value in crowd.values())
    assert crowd["E2D_LAMBDA_WATER"]["PORTFOLIO_REFERENCE_COST_INCREASE"] is False
    assert crowd["E2D_LAMBDA_VACCINE"]["PORTFOLIO_REFERENCE_COST_INCREASE"] is True
    assert crowd["E2D_LAMBDA_CRACKERS"]["PORTFOLIO_REFERENCE_COST_INCREASE"] is True
    means = {case: value["T_COST_REF"]["mean"] for case, value in summary["paired_priority"].items()}
    assert max(means, key=means.get) == "E2D_LAMBDA_CRACKERS"


def test_published_audit_schema_and_zero_run_guardrails():
    manifest = json.loads((ROOT / OUTPUT / "manifest.json").read_text(encoding="utf-8"))
    audit = json.loads((ROOT / OUTPUT / "e2d_interpretation_audit.json").read_text(encoding="utf-8"))
    assert manifest["scientific_optimization_runs"] == manifest["E3_runs"] == 0
    assert manifest["new_worst_scenario_search"] is False
    assert audit["RAW_AGGREGATE_SHORTAGE_IS_CROSS_UNIT_DESCRIPTIVE_ONLY"] is True
    assert audit["E2D_SCIENTIFIC_FREEZE"] == "YES"
    assert len(_rows("common_reference_results.csv")) == 6000
    assert len(_rows("paired_beta_reference.csv")) == 1000
    assert len(_rows("paired_priority_reference.csv")) == 3000
    assert {row["status"] for row in claim_rows()} <= {"SAFE_AS_WRITTEN", "NEEDS_QUALIFICATION", "SHOULD_NOT_BE_USED"}
