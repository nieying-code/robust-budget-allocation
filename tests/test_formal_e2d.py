"""Validation of frozen Formal E2-D evidence and OFAT identity."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from robust_budget_allocation.algorithms.qfr_final_a1 import FINAL_A1_IDENTITY, FINAL_A1_IMPLEMENTATION_REVISION
from robust_budget_allocation.formal.e2a import BUDGET, ITEMS, load_base_fixture, load_samples
from robust_budget_allocation.formal.e2d import CASES, data_for_case_sample, frozen_hashes, validate_e2d_design
from robust_budget_allocation.io.hashing import sha256_file

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "formal_results/e2_final/e2d"


def rows(name: str) -> list[dict[str, str]]:
    with (OUTPUT / name).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_preflight_and_frozen_design_identity():
    report = validate_e2d_design(ROOT)
    assert report["sample_sha256"] == "ac617befc8fbb7510e1b64b617c7e0339ea948ca519d0d18131f3b8048c131e0"
    assert report["planned_new_runs"] == 5000
    assert report["baseline_rerun"] is False
    assert report["budget"] == BUDGET
    assert FINAL_A1_IDENTITY == "A1_FINAL_NO_MEMORY_V1"
    assert FINAL_A1_IMPLEMENTATION_REVISION == "A1_FINAL_NO_MEMORY_V1_R1_WITNESS_GATED_INFEASIBLE_RETRY"


def test_e2d_changes_only_frozen_shortage_valuation_treatment():
    payload, metadata = load_base_fixture(ROOT)
    sample = load_samples(ROOT)[0]
    comparable = []
    for case, treatment in CASES.items():
        data = data_for_case_sample(payload, metadata, case, sample).to_dict()
        assert data["budget"] == BUDGET
        expected = dict(zip(ITEMS, treatment["lambda"], strict=True))
        assert data["shortage_cost"] == {
            item: treatment["beta"] * data["q_unit_cost"][item] * expected[item] for item in ITEMS
        }
        data.pop("shortage_cost")
        comparable.append(data)
    assert all(value == comparable[0] for value in comparable[1:])


def test_exact_5000_population_and_certification():
    scientific = rows("scientific_results.csv")
    assert len(scientific) == 5000
    for case, treatment in CASES.items():
        cell = [row for row in scientific if row["case_id"] == case]
        assert [row["simulation_id"] for row in cell] == [f"LA-{i:04d}" for i in range(1, 1001)]
        assert all(row["certificate_status"] == "PASS" for row in cell)
        assert all(row["algorithm_identity"] == FINAL_A1_IDENTITY for row in cell)
        assert all(row["implementation_revision"] == FINAL_A1_IMPLEMENTATION_REVISION for row in cell)
        assert all(float(row["beta"]) == treatment["beta"] for row in cell)


def test_paired_populations_and_summaries_are_complete():
    beta = rows("paired_beta_results.csv")
    priority = rows("paired_priority_results.csv")
    assert len(beta) == 1000
    assert len(priority) == 3000
    assert [row["simulation_id"] for row in beta] == [f"LA-{i:04d}" for i in range(1, 1001)]
    assert all(sum(row["case_id"] == case for row in priority) == 1000 for case in CASES if CASES[case]["part"] == "D2")
    analysis = json.loads((OUTPUT / "e2d_analysis.json").read_text(encoding="utf-8"))
    assert set(analysis["levels"]) == {"BETA4_BASELINE", "BETA2", "BETA6", "LAMBDA_WATER", "LAMBDA_VACCINE", "LAMBDA_CRACKERS"}
    for summary in analysis["levels"].values():
        assert summary["rows"] == 1000
        assert sum(summary["policy_counts"].values()) == 1000
        assert sum(summary["aggregate_reliability"].values()) == 3000
        assert sum(summary["worst_scenario_counts"].values()) == 1000
    assert len(analysis["commodity_priority_tradeoff"]) == 9


def test_manifest_hashes_frozen_evidence_and_no_baseline_or_e3_run():
    manifest = json.loads((OUTPUT / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["execution"] == {"planned": 5000, "attempted": 5000, "certified": 5000, "failed": 0}
    assert manifest["baseline_reuse"]["rows"] == 1000 and manifest["baseline_reuse"]["rerun"] is False
    assert manifest["guardrails"]["E3_runs"] == 0
    assert frozen_hashes(ROOT) == manifest["frozen_evidence_hashes"]
    inventory = {}
    for line in (OUTPUT / "HASHES.sha256").read_text(encoding="utf-8").splitlines():
        digest, name = line.split("  ", 1); inventory[name] = digest
    assert set(inventory) == {p.name for p in OUTPUT.iterdir() if p.is_file()} - {"HASHES.sha256"}
    assert all(sha256_file(OUTPUT / name) == digest for name, digest in inventory.items())
