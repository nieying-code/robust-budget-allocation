"""Solver-free identity and saved-evidence tests for Formal E5-B."""

import csv
import json
from pathlib import Path

from robust_budget_allocation.formal.e2d_audit import verify_hash_inventory
from robust_budget_allocation.formal.e5b import E5B, EXPECTED_GENERATOR_SHA256, SEEDS, SIZES, preflight

ROOT=Path(__file__).resolve().parents[1]


def test_e5b_frozen_preflight_and_generator():
    report=preflight(ROOT)
    assert report["status"]=="PASS"
    assert report["generator_sha256"]==EXPECTED_GENERATOR_SHA256
    assert tuple(report["seeds"])==SEEDS and tuple(report["scenario_sizes"])==SIZES
    assert report["unique_instances"]==120
    assert report["A0_timed_runs"]==report["A1_timed_runs"]==360
    assert report["nested_prefixes_verified"] is True
    assert report["memory_present"] is False and report["E5C_runs"]==0


def test_e5b_replicate_selection_is_frozen_and_shared():
    report=preflight(ROOT)
    assert len(report["parameter_row_ids"])==30
    assert all(1<=int(row)<=1000 for row in report["parameter_row_ids"])
    assert all(set(rep["prefix_sha256"])=={"50","100","200","500"} for rep in report["replicates"])


def test_e5b_saved_evidence_if_present():
    directory=ROOT/E5B; path=directory/"raw_timing.csv"
    if not path.exists(): return
    verify_hash_inventory(directory)
    with path.open(encoding="utf-8",newline="") as handle: rows=list(csv.DictReader(handle))
    assert len(rows)==720 and len({(r["benchmark_instance_id"],r["algorithm"],r["repetition"]) for r in rows})==720
    assert {r["certificate_status"] for r in rows}=={"PASS"}
    assert sum(r["algorithm"]=="A0" for r in rows)==sum(r["algorithm"]=="A1" for r in rows)==360
    assert not any("memory" in field.lower() for field in rows[0])
    analysis=json.loads((directory/"analysis.json").read_text(encoding="utf-8"))
    assert analysis["correctness"]["agreement"]==120
    assert analysis["E5C_runs"]==0
