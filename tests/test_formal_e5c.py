"""Solver-free identity and saved-evidence tests for Formal E5-C."""

import csv
import json
from pathlib import Path

import pytest

from robust_budget_allocation.formal.e2d_audit import verify_hash_inventory
from robust_budget_allocation.formal.e5c import (
    E5C, EXPECTED_GENERATOR_SHA256, SEEDS, SIZES, data_for_instance,
    generated_replicate, preflight, sample_by_id,
)

ROOT = Path(__file__).resolve().parents[1]


def test_e5c_frozen_preflight_and_generator():
    report = preflight(ROOT)
    assert report["status"] == "PASS"
    assert report["generator_sha256"] == EXPECTED_GENERATOR_SHA256
    assert tuple(report["seeds"]) == SEEDS and tuple(report["item_sizes"]) == SIZES
    assert report["unique_instances"] == 90
    assert report["A0_timed_runs"] == report["A1_timed_runs"] == 270
    assert report["nested_items_verified"] and report["shared_scenarios_verified"]
    assert report["memory_present"] is False


def test_e5c_nested_data_and_budget_ratio():
    report = preflight(ROOT)
    generated = generated_replicate(ROOT, SEEDS[0])
    sample = sample_by_id(ROOT, report["replicates"][0]["parameter_row_id"])
    data = {size: data_for_instance(ROOT, generated, sample, size) for size in SIZES}
    assert tuple(data[3].items) == tuple(item["item_id"] for item in generated["master_9"][:3])
    assert data[6].items[:3] == data[3].items and data[9].items[:6] == data[6].items
    assert data[3].scenarios == data[6].scenarios == data[9].scenarios
    assert len(data[3].scenarios) == 100
    for size in SIZES:
        assert data[size].budget == pytest.approx(report["replicates"][0]["B_ref_bench"][str(size)])
        assert all(not scenario.lower().startswith("no") for scenario in data[size].scenarios)


def test_e5c_saved_evidence_if_present():
    directory = ROOT / E5C
    path = directory / "raw_timing.csv"
    if not path.exists():
        return
    verify_hash_inventory(directory)
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 540
    assert len({(row["benchmark_instance_id"], row["algorithm"], row["repetition"]) for row in rows}) == 540
    assert {row["certificate_status"] for row in rows} == {"PASS"}
    assert sum(row["algorithm"] == "A0" for row in rows) == sum(row["algorithm"] == "A1" for row in rows) == 270
    assert not any("memory" in field.lower() for field in rows[0])
    analysis = json.loads((directory / "analysis.json").read_text(encoding="utf-8"))
    assert analysis["correctness"]["agreement"] == 90
    assert analysis["execution"]["failed"] == 0

