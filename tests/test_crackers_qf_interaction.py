"""Identity and consistency checks for the Crackers Q-F S200 supplement."""

from __future__ import annotations

import json
from pathlib import Path

from robust_budget_allocation.formal.crackers_qf_interaction import (
    CASES,
    EXPECTED_S200,
    F_PAIR,
    OUTPUT,
    POLICY_TOLERANCE,
    audit,
    data_for_sample,
    preflight,
    summarize,
    treated_sample,
)
from robust_budget_allocation.formal.e2a import OUTPUT_ITEMS, load_base_fixture, read_csv
from robust_budget_allocation.formal.e3 import s200_samples
from robust_budget_allocation.formal.e2d_audit import verify_hash_inventory


ROOT = Path(__file__).resolve().parents[1]


def test_supplement_preflight_and_grid_are_frozen():
    report = preflight(ROOT)
    assert report["status"] == "PASS"
    assert report["S200_sha256"] == EXPECTED_S200
    assert len(report["S200_ids"]) == len(set(report["S200_ids"])) == 200
    assert len(CASES) == 9
    assert {(v["a_C"], v["m_F"], v["phi"], v["psi"]) for v in CASES.values()} == {
        (a, m, *F_PAIR[m]) for a in (1.0, 0.9, 0.8) for m in (0.8, 1.0, 1.2)
    }


def test_treatment_changes_only_crackers_retention_and_f_economics():
    report = preflight(ROOT)
    background = s200_samples(ROOT, report)[0]
    base, metadata = load_base_fixture(ROOT)
    for case, treatment in CASES.items():
        treated = treated_sample(case, background)
        data = data_for_sample(base, metadata, case, treated)
        assert data.retention["Crackers"] == treatment["a_C"]
        assert data.retention["Water"] == data.retention["Seasonal Influenza Vaccine"] == 1.0
        assert data.storage_cost["Seasonal Influenza Vaccine"] == 0.0833333333333333
        assert treated["phi"] == treatment["phi"] and treated["psi"] == treatment["psi"]
        for field in background:
            if field not in {"phi", "psi"}:
                assert treated[field] == background[field]


def test_committed_supplement_population_rates_and_hashes():
    directory = ROOT / OUTPUT
    if not (directory / "manifest.json").exists():
        return
    verify_hash_inventory(directory)
    rows = read_csv(directory / "scientific_results.csv")
    assert len(rows) == 1800
    by_case = {case: [row for row in rows if row["case_id"] == case] for case in CASES}
    summaries = {case: summarize(case, cell) for case, cell in by_case.items()}
    validation = audit(preflight(ROOT), rows, summaries)
    assert validation["status"] == "PASS", validation["errors"]
    for case, cell in by_case.items():
        assert len(cell) == 200
        assert all(row["certificate_status"] == "PASS" for row in cell)
        for row in cell:
            for label in OUTPUT_ITEMS.values():
                assert str(float(row[f"Q_{label}"]) > POLICY_TOLERANCE) == row[f"Q_active_{label}"]
                assert str(float(row[f"F_{label}"]) > POLICY_TOLERANCE) == row[f"F_active_{label}"]
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["attempted"] == manifest["solved"] == manifest["certified"] == 1800
    assert manifest["failed"] == 0 and manifest["resampled"] is False

