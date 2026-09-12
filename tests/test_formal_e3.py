"""Solver-free identity, population, and artifact checks for Formal E3."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from robust_budget_allocation.formal.e2a import POLICY_TOLERANCE
from robust_budget_allocation.formal.e2d_audit import verify_hash_inventory
from robust_budget_allocation.formal.e3 import (
    E3A_CASES,
    E3B_CASES,
    EXPECTED_S100,
    EXPECTED_S200,
    load_samples,
    preflight,
    read_csv,
    treatment_sample,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "formal_results/e3_final"


def test_e3_preflight_and_frozen_identities():
    report = preflight(ROOT)
    assert report["status"] == "PASS"
    assert report["sample_sha256"] == "ac617befc8fbb7510e1b64b617c7e0339ea948ca519d0d18131f3b8048c131e0"
    assert report["S200_sha256"] == EXPECTED_S200
    assert report["S100_sha256"] == EXPECTED_S100
    assert len(report["S200_ids"]) == 200 == len(set(report["S200_ids"]))
    assert len(report["S100_ids"]) == 100 == len(set(report["S100_ids"]))
    assert set(report["S100_ids"]) <= set(report["S200_ids"])
    assert report["E4_runs"] == 0


def test_e3a_grid_and_e3b_recovery_are_exactly_frozen():
    report = preflight(ROOT)
    assert len(E3A_CASES) == len(E3B_CASES) == 9
    assert {(v["h_V_tau"], v["m_F"], v["phi"], v["psi"]) for v in E3A_CASES.values()} == {
        (h, m, p, x)
        for h in (0.0, 0.5, 1.0)
        for m, (p, x) in {0.8: (0.16, 0.68), 1.0: (0.2, 0.85), 1.2: (0.24, 1.02)}.items()
    }
    recovery = report["E3B_design_recovery"]
    assert recovery["status"] == "PASS" and recovery["S100_used"] is False
    assert recovery["per_cell_sample_size"] == 200 and recovery["total_optimizations"] == 1800
    assert report["E3B_F_risk"]["levels"] == {"Low": 975, "Medium": 169, "High": 794}
    assert report["E3B_reliability"]["levels"] == {"Unfavorable": 374, "Reference": 427, "Favorable": 755}


def test_all_e3_rows_are_paired_certified_and_not_resampled():
    expected = [f"LA-{i:04d}" for i in preflight(ROOT)["S200_ids"]]
    for part, cases in (("e3a", E3A_CASES), ("e3b", E3B_CASES)):
        combined = read_csv(OUTPUT / part / "scientific_results.csv")
        assert len(combined) == 1800
        for case in cases:
            rows = read_csv(OUTPUT / part / f"{case}.csv")
            assert len(rows) == 200
            assert [row["simulation_id"] for row in rows] == expected
            assert all(row["certificate_status"] == "PASS" and row["status"] == "certified" for row in rows)
            assert all(row["algorithm_identity"] == "A1_FINAL_NO_MEMORY_V1" for row in rows)
            assert all(row["implementation_revision"] == "A1_FINAL_NO_MEMORY_V1_R1_WITNESS_GATED_INFEASIBLE_RETRY" for row in rows)


def test_e3b_treatments_change_only_frozen_donor_field_groups():
    report = preflight(ROOT)
    samples = load_samples(ROOT)
    backgrounds = {row["simulation_id"]: row for row in samples}
    all_samples = {int(row["sample_index"]): row for row in samples}
    for case, treatment in E3B_CASES.items():
        rows = read_csv(OUTPUT / "e3b" / f"{case}.csv")
        assert {row["F_risk_donor_id"] for row in rows} == {f"LA-{report['E3B_F_risk']['levels'][treatment['F_risk']]:04d}"}
        assert {row["reliability_donor_id"] for row in rows} == {f"LA-{report['E3B_reliability']['levels'][treatment['reliability_economics']]:04d}"}
        for row in rows:
            background = backgrounds[row["simulation_id"]]
            treated = treatment_sample("E3B", case, background, report, all_samples)
            assert all(float(treated[f"rho_Q{k}"]) == float(background[f"rho_Q{k}"]) for k in range(1, 6))
            assert float(treated["phi"]) == float(background["phi"])
            assert float(treated["psi"]) == float(background["psi"])


def test_policy_and_activation_classification_are_internally_consistent():
    for part in ("e3a", "e3b"):
        for row in read_csv(OUTPUT / part / "scientific_results.csv"):
            q = [float(row[f"Q_{item}"]) for item in ("Water", "Vaccine", "Crackers")]
            f = [float(row[f"F_{item}"]) for item in ("Water", "Vaccine", "Crackers")]
            assert [str(v > POLICY_TOLERANCE) for v in q] == [row[f"Q_active_{item}"] for item in ("Water", "Vaccine", "Crackers")]
            assert [str(v > POLICY_TOLERANCE) for v in f] == [row[f"F_active_{item}"] for item in ("Water", "Vaccine", "Crackers")]
            assert row["policy_label"] in {"P1", "P2", "P3a", "P3b", "P4", "P5"}


def test_e3_manifests_hashes_and_worst_scenario_evidence():
    verify_hash_inventory(OUTPUT / "e3a")
    verify_hash_inventory(OUTPUT / "e3b")
    manifest = json.loads((OUTPUT / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["attempted"] == manifest["certified"] == 3600
    assert manifest["failed"] == manifest["E4_runs"] == 0
    for part in ("e3a", "e3b"):
        rows = read_csv(OUTPUT / part / "scientific_results.csv")
        assert {row["worst_scenario"] for row in rows} == {"h09"}
        assert len(read_csv(OUTPUT / part / "paired_panel.csv")) == 200
        assert len(read_csv(OUTPUT / part / "interaction_contrasts.csv")) > 0


def test_e3b_cell_definition_and_cross_unit_guardrail():
    definitions = read_csv(OUTPUT / "e3b" / "cell_definition.csv")
    assert len(definitions) == 9 and {row["case_id"] for row in definitions} == set(E3B_CASES)
    for part in ("e3a", "e3b"):
        analysis = json.loads((OUTPUT / part / f"{part}_analysis.json").read_text(encoding="utf-8"))
        assert analysis["shortage_reporting"] == "CROSS_UNIT_DESCRIPTIVE_ONLY"
        assert analysis["attempted"] == analysis["certified"] == 1800
        assert analysis["failed"] == analysis["E4_runs"] == 0
