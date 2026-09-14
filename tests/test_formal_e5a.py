"""Solver-free structural tests for frozen Formal E5-A."""

from pathlib import Path
import csv
import json

from robust_budget_allocation.formal.e5a import (
    A0_IDENTITY, E5A, EXPECTED_REVISION, EXPECTED_S200, execution_order, preflight,
)
from robust_budget_allocation.formal.e2d_audit import verify_hash_inventory

ROOT = Path(__file__).resolve().parents[1]


def test_e5a_preflight_frozen_identity():
    report = preflight(ROOT)
    assert report["status"] == "PASS"
    assert report["S200_sha256"] == EXPECTED_S200
    assert len(report["S200_ids"]) == len(set(report["S200_ids"])) == 200
    assert report["A0_identity"] == A0_IDENTITY
    assert report["A1_identity"] == "A1_FINAL_NO_MEMORY_V1"
    assert report["implementation_revision"] == EXPECTED_REVISION
    assert report["memory_present"] is False
    assert report["A0_timed_runs"] == report["A1_timed_runs"] == 600
    assert report["E5B_runs"] == report["E5C_runs"] == 0


def test_e5a_order_is_deterministic_and_balanced():
    orders = [execution_order(position, repetition) for position in range(1,201) for repetition in range(1,4)]
    assert orders.count(("A0","A1")) == orders.count(("A1","A0")) == 300
    assert execution_order(1,1) == ("A0","A1")
    assert execution_order(1,2) == ("A1","A0")


def test_e5a_no_memory_fields_or_imports():
    source=(ROOT/"src/robust_budget_allocation/formal/e5a.py").read_text(encoding="utf-8")
    runner=(ROOT/"scripts/run_formal_e5.py").read_text(encoding="utf-8")
    assert "qfr_a1_memory" not in source+runner
    assert "memory_hits" not in source+runner
    assert "solve_qfr_final_a1" in runner and "solve_qfr_standard_ccg" in runner


def test_e5a_saved_population_and_correctness():
    directory = ROOT / E5A
    with (directory/"raw_timing.csv").open(encoding="utf-8",newline="") as handle:
        rows=list(csv.DictReader(handle))
    assert len(rows)==1200
    assert len({(r["simulation_id"],r["algorithm"],r["repetition"]) for r in rows})==1200
    assert {r["certificate_status"] for r in rows}=={"PASS"}
    assert sum(r["algorithm"]=="A0" for r in rows)==600
    assert sum(r["algorithm"]=="A1" for r in rows)==600
    assert not any("memory" in field.lower() for field in rows[0])
    with (directory/"correctness_comparison.csv").open(encoding="utf-8",newline="") as handle:
        comparisons=list(csv.DictReader(handle))
    assert len(comparisons)==200
    assert all(r["objective_agreement"]=="True" for r in comparisons)
    assert all(r["A1_full_exact_certificate"]=="True" for r in comparisons)


def test_e5a_saved_manifests_and_hashes():
    verify_hash_inventory(ROOT/E5A)
    verify_hash_inventory(ROOT/"formal_results/e5_final")
    manifest=json.loads((ROOT/E5A/"manifest.json").read_text(encoding="utf-8"))
    assert manifest["timed_runs"]==manifest["certified"]==1200
    assert manifest["failed"]==0
    assert manifest["memory"] is False
    assert manifest["E5B_runs"]==manifest["E5C_runs"]==0
    assert manifest["model_changed"] is manifest["tolerance_changed"] is False
