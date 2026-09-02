from __future__ import annotations

import json
import math
from pathlib import Path

from robust_budget_allocation.data.qfr_e1_historical import (
    DATASET_KIND,
    EXPECTED_SCENARIOS,
    build_e1_historical_data,
)
from robust_budget_allocation.formal.e1_historical import (
    EXPECTED_DATA_SHA256,
    build_case_data,
    load_authorities,
    solver_free_preflight,
)


ROOT = Path(__file__).resolve().parents[1]


def test_rawls15_dataset_regenerates_exactly() -> None:
    stored = json.loads((ROOT / "configs/e1_historical_rawls15_data_v1.json").read_text(encoding="utf-8"))
    assert build_e1_historical_data(ROOT) == stored
    assert stored["data_sha256"] == EXPECTED_DATA_SHA256
    assert stored["dataset_kind"] == DATASET_KIND
    assert tuple(stored["scenario_ordering"]) == EXPECTED_SCENARIOS
    assert stored["scenario_counts"] == {"single": 15, "combined": 0, "no_hurricane": 0, "total": 15}
    assert all(row["scenario_type"] == "single" and len(row["hurricanes"]) == 1 for row in stored["scenarios"])
    assert math.isclose(sum(row["probability"] for row in stored["scenarios"]), 1.0, abs_tol=1e-12)
    assert math.isclose(stored["source_single_probability_sum"], 0.75, abs_tol=1e-12)


def test_bref_and_fbar_are_mechanical_rawls15_derivations() -> None:
    ready = load_authorities(ROOT)["ready"]
    assert ready["reference_budget_rule"] == "sum_i((cQ_i+h_i*tau)*Dref_i/a_i)"
    assert math.isclose(ready["reference_budget"], sum(ready["reference_budget_components"].values()), abs_tol=1e-9)
    assert ready["reference_budget"] == 6721988.79033174
    assert ready["old_51_reference_budget"] == 7975014.2749022
    assert ready["flexible_capacity"] == {
        "Water": 18000000.0,
        "Seasonal Influenza Vaccine": 955734.406438632,
        "Crackers": 186200000.0,
    }
    assert ready["old_51_flexible_capacity"] == {
        "Water": 27000000.0,
        "Seasonal Influenza Vaccine": 1144366.1971831,
        "Crackers": 206878000.0,
    }


def test_only_budget_changes_across_registered_case_payloads() -> None:
    authority = load_authorities(ROOT)
    assert len(authority["cases"]) == 9
    baseline = dict(authority["ready"]["qfr_data"])
    for case in authority["cases"]:
        candidate = build_case_data(authority["ready"], case["budget_ratio"]).to_dict()
        expected = dict(baseline)
        expected["budget"] = authority["ready"]["reference_budget"] * case["budget_ratio"]
        assert candidate == expected


def test_solver_free_preflight_reports_frozen_scope() -> None:
    result = solver_free_preflight(ROOT)
    assert result["status"] == "PASS"
    assert result["dataset_kind"] == DATASET_KIND
    assert result["scenario_count"] == 15
    assert tuple(result["scenario_ids"]) == EXPECTED_SCENARIOS
    assert result["case_count"] == 9
