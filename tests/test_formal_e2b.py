"""Solver-free validation of the completed Formal E2-B evidence."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from robust_budget_allocation.algorithms.qfr_final_a1 import (
    FINAL_A1_IDENTITY,
    FINAL_A1_IMPLEMENTATION_REVISION,
)
from robust_budget_allocation.formal.e2a import load_samples
from robust_budget_allocation.formal.e2b import (
    BASELINE_CASE,
    B_REF,
    CASES,
    data_for_case_sample,
    frozen_hashes,
    load_base_fixture,
    validate_e2b_design,
)
from robust_budget_allocation.io.hashing import sha256_file


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "formal_results/e2_final/e2b"


def rows(name: str) -> list[dict[str, str]]:
    with (OUTPUT / name).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_preflight_identity_and_exact_budgets():
    report = validate_e2b_design(ROOT)
    assert report["sample_sha256"] == "ac617befc8fbb7510e1b64b617c7e0339ea948ca519d0d18131f3b8048c131e0"
    assert report["planned_new_runs"] == 2000
    assert report["baseline_rerun"] is False
    assert report["E2_A_frozen"] is True
    assert CASES["E2B_B075"]["budget"] == 0.75 * B_REF
    assert CASES["E2B_B125"]["budget"] == 1.25 * B_REF
    assert BASELINE_CASE == "E2B_B100"


def test_e2b_changes_only_budget_in_scientific_data():
    payload, metadata = load_base_fixture(ROOT)
    sample = load_samples(ROOT)[0]
    low = data_for_case_sample(payload, metadata, "E2B_B075", sample).to_dict()
    high = data_for_case_sample(payload, metadata, "E2B_B125", sample).to_dict()
    assert low.pop("budget") == CASES["E2B_B075"]["budget"]
    assert high.pop("budget") == CASES["E2B_B125"]["budget"]
    assert low == high


def test_new_population_is_exact_complete_and_certified():
    scientific = rows("scientific_results.csv")
    assert len(scientific) == 2000
    assert {row["case_id"] for row in scientific} == set(CASES)
    for case_id in CASES:
        cell = [row for row in scientific if row["case_id"] == case_id]
        assert [row["simulation_id"] for row in cell] == [f"LA-{index:04d}" for index in range(1, 1001)]
        assert all(row["certificate_status"] == "PASS" for row in cell)
        assert all(row["algorithm_identity"] == FINAL_A1_IDENTITY for row in cell)
        assert all(row["implementation_revision"] == FINAL_A1_IMPLEMENTATION_REVISION for row in cell)
        assert all(float(row["budget"]) == CASES[case_id]["budget"] for row in cell)


def test_paired_triplets_are_complete_and_baseline_is_read_only():
    paired = rows("paired_budget_results.csv")
    assert len(paired) == 1000
    assert [row["simulation_id"] for row in paired] == [f"LA-{index:04d}" for index in range(1, 1001)]
    assert len({row["input_sha256"] for row in paired}) == 1000
    manifest = json.loads((OUTPUT / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["baseline_reuse"]["rows"] == 1000
    assert manifest["baseline_reuse"]["rerun"] is False
    assert manifest["guardrails"]["E2_A_rerun"] is False
    assert manifest["guardrails"]["E2_C_runs"] == 0
    assert manifest["guardrails"]["E2_D_runs"] == 0


def test_summary_is_rebuilt_from_complete_rows():
    analysis = json.loads((OUTPUT / "e2b_analysis.json").read_text(encoding="utf-8"))
    assert set(analysis["levels"]) == {"B075", "B100", "B125"}
    for summary in analysis["levels"].values():
        assert summary["rows"] == 1000
        assert sum(summary["policy_counts"].values()) == 1000
        assert sum(summary["aggregate_reliability"].values()) == 3000
        assert summary["same_item_QF_coexistence"] >= 0
        assert sum(summary["worst_scenario_counts"].values()) == 1000
    assert set(analysis["paired"]) == {"B075_to_B100", "B100_to_B125", "B075_to_B125"}


def test_hash_inventory_and_frozen_evidence_identity():
    manifest = json.loads((OUTPUT / "manifest.json").read_text(encoding="utf-8"))
    assert frozen_hashes(ROOT) == manifest["frozen_evidence_hashes"]
    inventory: dict[str, str] = {}
    for line in (OUTPUT / "HASHES.sha256").read_text(encoding="utf-8").splitlines():
        digest, name = line.split("  ", 1)
        inventory[name] = digest
    assert set(inventory) == {path.name for path in OUTPUT.iterdir() if path.is_file()} - {"HASHES.sha256"}
    for name, digest in inventory.items():
        assert sha256_file(OUTPUT / name) == digest


@pytest.mark.gurobi
def test_final_a1_identity_remains_current():
    assert FINAL_A1_IDENTITY == "A1_FINAL_NO_MEMORY_V1"
    assert FINAL_A1_IMPLEMENTATION_REVISION == "A1_FINAL_NO_MEMORY_V1_R1_WITNESS_GATED_INFEASIBLE_RETRY"
