import json
import math
from pathlib import Path

from robust_budget_allocation.data.qfr_formal import ACTIVE_ITEMS, build_formal_data
from robust_budget_allocation.io.hashing import canonical_json_sha256


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/r6_formal_data_v1.json"
READY = ROOT / "configs/r6_formal_ready_data_v1.json"


def _product():
    return build_formal_data(CONFIG)


def test_r6_scenario_backbone_is_exact_and_probability_complete():
    product = _product()
    assert product["scenario_counts"] == {"single": 15, "combined": 35, "no_hurricane": 1}
    assert len(product["scenarios"]) == 51
    assert len({row["scenario_id"] for row in product["scenarios"]}) == 51
    assert math.isclose(product["probability_sum"], 1.0, rel_tol=0.0, abs_tol=1e-12)
    valid = {f"h{number:02d}" for number in range(1, 16)}
    assert all(set(row["hurricanes"]) <= valid for row in product["scenarios"])


def test_r6_worst_category_and_no_hurricane_disruption_are_exact():
    product = _product()
    row16 = product["scenarios"][15]
    assert row16["hurricanes"] == ["h01", "h02"]
    assert row16["category"] == 5
    assert row16["q_availability"] == 0.0
    assert row16["disruption"] == 1.0
    no_hurricane = product["scenarios"][-1]
    assert no_hurricane["scenario_type"] == "no_hurricane"
    assert no_hurricane["formal_demand"] == {item: 0.0 for item in ACTIVE_ITEMS}
    assert no_hurricane["q_availability"] == 1.0
    assert no_hurricane["disruption"] == 0.0


def test_r6_three_distinct_demand_transformations_are_exact():
    product = _product()
    row = product["scenarios"][0]
    assert row["formal_demand"]["Water"] == 350_000.0
    assert math.isclose(
        row["formal_demand"]["Seasonal Influenza Vaccine"],
        (140.0 / 13.916) * 500.0,
        rel_tol=0.0,
        abs_tol=1e-10,
    )
    assert row["formal_demand"]["Crackers"] == 14_000.0 * 525.0
    assert math.isclose(
        13.916 * row["formal_demand"]["Seasonal Influenza Vaccine"],
        140.0 * 500.0,
        rel_tol=0.0,
        abs_tol=1e-9,
    )


def test_r6_active_parameters_and_cost_architecture_are_exact():
    product = _product()
    params = product["parameters"]
    assert tuple(params["q_unit_cost"]) == ACTIVE_ITEMS
    assert params["retention"] == {"Water": 1.0, "Seasonal Influenza Vaccine": 1.0, "Crackers": 0.9}
    assert math.isclose(params["storage_cost_per_month"]["Seasonal Influenza Vaccine"], 1 / 12, abs_tol=1e-15)
    assert params["storage_horizon_cost"]["Seasonal Influenza Vaccine"] == 0.5
    assert math.isclose(params["shortage_cost"]["Water"], 3.8862, abs_tol=1e-12)
    assert math.isclose(params["shortage_cost"]["Seasonal Influenza Vaccine"], 139.16, abs_tol=1e-12)
    assert math.isclose(params["shortage_cost"]["Crackers"], 0.37488, abs_tol=1e-12)
    assert params["reservation_cost"]["Seasonal Influenza Vaccine"] == 2.7832
    assert params["exercise_cost"]["Seasonal Influenza Vaccine"] == 11.8286
    assert math.isclose(2.7832 + 11.8286, 14.6118, abs_tol=1e-12)
    assert math.isclose(14.6118 / 14.416, 1.013582130965594, abs_tol=1e-15)
    assert all(math.isclose(phi + psi, 1.05, abs_tol=1e-12) for phi, psi in params["f_split_sensitivity"])
    assert params["reliability_mitigation"] == [0.0, 0.5, 0.8]
    serialized = json.dumps(product)
    assert all(term not in serialized for term in ("Insulin", "Medical Oxygen", "IV Saline"))


def test_r6_qfr_schema_builds_without_solving_and_reliability_only_prices_f():
    product = _product()
    qfr = product["qfr_data"]
    assert qfr["items"] == list(ACTIVE_ITEMS)
    assert qfr["schema_version"] == 3
    assert qfr["reliability_mitigation"]["Water"] == {"0": 0.0, "1": 0.5, "2": 0.8}
    assert not any(name in qfr for name in ("supplier", "emergency_budget", "q_reliability_cost"))
    assert product["scientific_runs"] == 0


def test_r6_scale_audit_handles_zero_demand_and_is_deterministic():
    first = _product()
    second = _product()
    assert first == second
    assert first["data_sha256"] == second["data_sha256"]
    audit = first["economic_scale_audit"]
    assert audit["effective_q_exposure"]["zero_total_scenarios_excluded_from_shares"] == 1
    assert audit["shortage_exposure"]["zero_total_scenarios_excluded_from_shares"] == 1
    assert "scale_guard_flags" not in audit


def test_r6_generated_formal_ready_data_matches_generator_and_hash():
    stored = json.loads(READY.read_text(encoding="utf-8"))
    generated = _product()
    assert stored == generated
    bare = dict(stored)
    digest = bare.pop("data_sha256")
    assert digest == canonical_json_sha256(bare)
