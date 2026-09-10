"""Solver-free checks for Formal E2-C reliability boundary evidence."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from robust_budget_allocation.algorithms.qfr_final_a1 import (
    FINAL_A1_IDENTITY,
    FINAL_A1_IMPLEMENTATION_REVISION,
)
from robust_budget_allocation.formal.e2c import frozen_hashes, validate_preflight
from robust_budget_allocation.io.hashing import sha256_file


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "formal_results/e2_final/e2c"


def rows(name: str) -> list[dict[str, str]]:
    with (OUTPUT / name).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_preflight_and_algorithm_identity():
    report = validate_preflight(ROOT)
    assert report["sample_rows"] == report["result_rows"] == 1000
    assert report["sample_sha256"] == "ac617befc8fbb7510e1b64b617c7e0339ea948ca519d0d18131f3b8048c131e0"
    assert FINAL_A1_IDENTITY == "A1_FINAL_NO_MEMORY_V1"
    assert FINAL_A1_IMPLEMENTATION_REVISION == "A1_FINAL_NO_MEMORY_V1_R1_WITNESS_GATED_INFEASIBLE_RETRY"
    assert report["E2_C_new_scientific_optimization_runs"] == 0


def test_observation_population_and_r_f_linking():
    observations = rows("reliability_observations.csv")
    assert len(observations) == 3000
    assert len({row["simulation_id"] for row in observations}) == 1000
    assert sum(row["F_active_item"] == "True" for row in observations) == 1160
    for row in observations:
        assert (row["reliability_level"] != "NONE") == (row["F_active_item"] == "True")
        if row["reliability_level"] in {"R1", "R2"}:
            assert row["F_active_item"] == "True"


def test_efficiency_formulas_are_reconstructible():
    for row in rows("reliability_observations.csv"):
        eta1, eta2 = float(row["eta_1"]), float(row["eta_2"])
        cr1, cr2 = float(row["c_R1_ratio"]), float(row["c_R2_ratio"])
        assert float(row["A_R1"]) == eta1 / cr1
        assert float(row["A_R2"]) == (eta2 - eta1) / (cr2 - cr1)
        assert float(row["F_exposure"]) == float(row["F_quantity"]) * float(row["rho_F_severity_score"])


def test_f_active_and_reliability_counts():
    analysis = json.loads((OUTPUT / "e2c_analysis.json").read_text(encoding="utf-8"))
    assert analysis["population"] == {
        "total_E1_rows": 1000,
        "F_active_rows": 792,
        "F_inactive_rows": 208,
        "aggregate_reliability_counts": {"NONE": 208, "R0": 668, "R1": 81, "R2": 43},
    }
    assert analysis["item_reliability_counts"] == {"NONE": 1840, "R0": 1023, "R1": 86, "R2": 51}
    assert analysis["E2B_supplementary_paid_R_total"] == {"B075": 143, "B100": 137, "B125": 134}


def test_fixed_quintile_outputs_and_interaction_maps():
    for name in ("ar1_bin_summary.csv", "ar2_bin_summary.csv"):
        table = rows(name)
        assert len(table) == 5
        assert {int(row["quintile"]) for row in table} == {1, 2, 3, 4, 5}
        assert sum(int(row["N"]) for row in table) == 1160
    for name in ("ar1_fexposure_map.csv", "ar2_fexposure_map.csv"):
        table = rows(name)
        assert len(table) == 25
        assert sum(int(row["N"]) for row in table) == 1160


def test_commodity_counts_and_boundary_effects():
    commodity = {row["commodity"]: row for row in rows("commodity_reliability_summary.csv")}
    assert {name: (int(row["F_active"]), int(row["R0"]), int(row["R1"]), int(row["R2"])) for name, row in commodity.items()} == {
        "Water": (356, 343, 5, 8), "Vaccine": (225, 158, 49, 18), "Crackers": (579, 522, 32, 25)
    }
    boundary = {row["comparison"]: row for row in rows("boundary_analysis.csv")}
    assert float(boundary["R0_vs_R1+R2"]["rank_biserial"]) > 0.5
    assert float(boundary["R1_vs_R2"]["rank_biserial"]) > 0.95
    assert all(row["interpretation"] == "EMPIRICAL_DECISION_BOUNDARY_NOT_STRUCTURAL_THEOREM" for row in boundary.values())


def test_hash_inventory_frozen_inputs_and_zero_runs():
    manifest = json.loads((OUTPUT / "manifest.json").read_text(encoding="utf-8"))
    assert frozen_hashes(ROOT) == manifest["frozen_artifact_hashes"]
    inventory = {}
    for line in (OUTPUT / "HASHES.sha256").read_text(encoding="utf-8").splitlines():
        digest, name = line.split("  ", 1); inventory[name] = digest
    assert set(inventory) == {path.name for path in OUTPUT.iterdir() if path.is_file()} - {"HASHES.sha256"}
    assert all(sha256_file(OUTPUT / name) == digest for name, digest in inventory.items())
    assert manifest["analysis"]["optimization_runs"] == 0
    assert manifest["guardrails"]["E2_D_runs"] == 0
