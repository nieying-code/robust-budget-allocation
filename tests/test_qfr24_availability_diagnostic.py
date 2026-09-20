import math
from pathlib import Path

from robust_budget_allocation.diagnostics.qfr24_availability import (
    BUDGET_RATIOS,
    ITEMS,
    MODELS,
    build_diagnostic_authority,
    case_data,
)


ROOT = Path(__file__).resolve().parents[1]


def _authority():
    return build_diagnostic_authority(ROOT)


def test_diagnostic_is_exactly_24_scenarios_and_9_cases():
    authority = _authority()
    assert authority["scenario_count"] == 24
    assert authority["scenario_ids"] == [f"h{i:02d}" for i in range(1, 25)]
    assert tuple(authority["models"]) == MODELS
    assert tuple(authority["budget_ratios"]) == BUDGET_RATIOS
    assert authority["reference_weight"] == 1 / 24
    assert authority["reference_weight_role"] == "B_REF_NEUTRAL_NORMALIZATION_ONLY_NOT_EMPIRICAL_PROBABILITY"


def test_availability_schedules_are_exact_under_existing_model_equivalence():
    authority = _authority()
    assert authority["q_availability_cat1_to_cat5"] == [0.92, 0.84, 0.76, 0.68, 0.6]
    assert authority["f_availability"] == {
        "R0": [0.91, 0.82, 0.73, 0.64, 0.55],
        "R1": [0.92, 0.84, 0.76, 0.68, 0.6],
        "R2": [0.95, 0.9, 0.85, 0.8, 0.75],
    }
    eta = authority["model_equivalent_reliability_mitigation"]
    assert eta[0] == 0
    assert math.isclose(eta[1], 1 / 9, abs_tol=1e-15)
    assert math.isclose(eta[2], 4 / 9, abs_tol=1e-15)


def test_b_ref_and_fbar_are_mechanical_from_24_formal_demands():
    authority = _authority()
    data = case_data(authority, 1.0)
    assert data.budget == authority["B_ref"]
    for item in ITEMS:
        assert authority["reference_demand"][item] == sum(data.demand[s][item] for s in data.scenarios) / 24
        assert authority["F_bar"][item] == max(data.demand[s][item] for s in data.scenarios)
    assert math.isclose(sum(authority["reference_budget_components"].values()), authority["B_ref"], abs_tol=1e-8)


def test_economic_parameters_are_unchanged_and_robust_data_has_no_probabilities():
    authority = _authority()
    data = case_data(authority, 1.0)
    for item in ITEMS:
        assert math.isclose(data.reservation_cost[item] / data.q_unit_cost[item], 0.20, abs_tol=1e-15)
        assert math.isclose(data.exercise_cost[item] / data.q_unit_cost[item], 0.85, abs_tol=1e-15)
        for actual, expected in zip(
            [data.reliability_cost[item][level] / data.q_unit_cost[item] for level in range(3)],
            [0.0, 0.1, 0.25], strict=True,
        ):
            assert math.isclose(actual, expected, abs_tol=1e-15)
        assert math.isclose(data.shortage_cost[item] / data.q_unit_cost[item], 4.0, abs_tol=1e-15)
    assert "probability" not in data.to_dict()
