import math
from pathlib import Path

import pyomo.environ as pyo

from robust_budget_allocation.diagnostics.qfr24_state_availability import (
    BUDGET_RATIOS, ITEMS, build_authority, build_diagnostic_ef, case_data,
)


ROOT = Path(__file__).resolve().parents[1]


def test_weights_and_reference_constraints():
    authority = build_authority(ROOT)
    assert len(authority["scenario_ids"]) == 24
    assert math.isclose(sum(authority["scenario_weights"].values()), 1.0, abs_tol=1e-15)
    assert math.isclose(authority["weight_checks"]["Florida"], 0.4, abs_tol=1e-15)
    assert math.isclose(authority["weight_checks"]["Major"], 0.4444444444, abs_tol=1e-15)
    assert math.isclose(authority["weight_checks"]["Minor"], 0.5555555556, abs_tol=1e-15)
    assert abs(float(authority["weight_checks_decimal"]["total"]) - 1.0) < 1e-15
    assert authority["weight_checks_decimal"]["Florida"] == "0.4000000000"
    assert authority["weight_checks_decimal"]["Major"] == "0.4444444444"
    assert authority["weight_checks_decimal"]["Minor"] == "0.5555555556"
    displayed = [0.0264718, 0.0823384, 0.0253566, 0.0788695]
    actual = [float(v) for v in authority["group_weights_decimal"].values()]
    assert all(abs(a - b) < 5e-8 for a, b in zip(actual, displayed, strict=True))
    assert authority["reference_weight_role"] == "B_REF_ONLY_NOT_ROBUST_SCENARIO_PROBABILITY"


def test_dref_bref_and_budgets_are_mechanical():
    authority = build_authority(ROOT)
    data = case_data(authority, 1.0)
    for item in ITEMS:
        expected = math.fsum(authority["scenario_weights"][s] * data.demand[s][item] for s in data.scenarios)
        assert math.isclose(authority["D_ref"][item], expected, abs_tol=1e-8)
    assert math.isclose(authority["B_ref"], sum(authority["B_ref_components"].values()), abs_tol=1e-8)
    for ratio in BUDGET_RATIOS:
        assert math.isclose(case_data(authority, ratio).budget, ratio * authority["B_ref"], abs_tol=1e-8)


def test_state_availability_replaces_only_rho_expression():
    authority = build_authority(ROOT)
    data = case_data(authority, 1.0)
    model = build_diagnostic_ef(data, "M2", authority["direct_f_availability"])
    by_name = {meta["hurricane_name"]: sid for sid, meta in authority["metadata"].items()}
    for name, expected in {"Alicia": [0.70, 0.82, 0.92], "Katrina": [0.45, 0.65, 0.85]}.items():
        sid = by_name[name]
        for level, value in enumerate(expected):
            for item in ITEMS:
                assert pyo.value(model.rho[item, sid, level]) == value


def test_economics_unchanged_and_no_low_scenarios():
    authority = build_authority(ROOT)
    data = case_data(authority, 1.0)
    assert {meta["state"] for meta in authority["metadata"].values()} == {"Medium", "High"}
    for item in ITEMS:
        assert math.isclose(data.reservation_cost[item] / data.q_unit_cost[item], 0.2)
        assert math.isclose(data.exercise_cost[item] / data.q_unit_cost[item], 0.85)
        assert all(
            math.isclose(data.reliability_cost[item][r] / data.q_unit_cost[item], expected)
            for r, expected in enumerate([0.0, 0.1, 0.25])
        )
        assert math.isclose(data.shortage_cost[item] / data.q_unit_cost[item], 4.0)
    assert "probability" not in data.to_dict()
