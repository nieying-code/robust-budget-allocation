from copy import deepcopy
import json
from pathlib import Path

import pyomo.environ as pyo
from pyomo.repn import generate_standard_repn
import pytest

from robust_budget_allocation.algorithms.qfr_exact_oracle import build_exact_recourse
from robust_budget_allocation.algorithms.qfr_protocol import (
    scenario_identity,
    solve_exact,
    static_data_sha256,
    subset_data,
)
from robust_budget_allocation.algorithms.qfr_state import QFRFirstStage
from robust_budget_allocation.data.qfr_data import QFRData
from robust_budget_allocation.data.qfr_revision import load_pilot_baseline
from robust_budget_allocation.models.qfr_m0 import build_qfr_m0
from robust_budget_allocation.models.qfr_m1 import build_qfr_m1
from robust_budget_allocation.models.qfr_m2 import build_qfr_m2
from robust_budget_allocation.models.qfr_support import validate_qfr_solution


ROOT = Path(__file__).resolve().parents[1]
PILOT_CONFIG = ROOT / "configs/qfr_pilot_baseline_v2_1.json"
CORRECTNESS_FIXTURE = ROOT / "tests/fixtures/qfr_availability_correctness_v2_1.json"


def revised_payload():
    fixture = json.loads(CORRECTNESS_FIXTURE.read_text(encoding="utf-8"))
    return deepcopy(fixture["cases"][0]["data"])


def revised_data() -> QFRData:
    return QFRData.from_dict(revised_payload())


def coefficients(expression):
    repn = generate_standard_repn(expression)
    assert repn.is_linear()
    return {
        variable.name: float(coefficient)
        for variable, coefficient in zip(repn.linear_vars, repn.linear_coefs)
    }


def zero_decision(data: QFRData, kind: str) -> QFRFirstStage:
    levels = () if kind == "M0" else ((0,) if kind == "M1" else (0, 1, 2))
    return QFRFirstStage(
        model_kind=kind,
        reliability_levels=levels,
        data_sha256=data.data_sha256,
        scenario_sha256=data.scenario_sha256,
        static_data_sha256=static_data_sha256(data),
        q={item: 0.0 for item in data.items},
        f={item: {level: 0.0 for level in levels} for item in data.items},
        z={item: {level: 0 for level in levels} for item in data.items},
    )


def test_revision_schema_binds_q_availability_and_preserves_legacy_identity():
    data = revised_data()
    assert data.schema_version == 3
    assert QFRData.from_dict(data.to_dict()).data_sha256 == data.data_sha256
    changed = revised_payload()
    changed["q_availability"]["b_medium"]["ordinary"] = 0.8
    other = QFRData.from_dict(changed)
    assert other.data_sha256 != data.data_sha256
    assert other.scenario_sha256 != data.scenario_sha256
    assert scenario_identity(other, "b_medium") != scenario_identity(data, "b_medium")

    legacy_payload = json.loads(
        (ROOT / "tests/fixtures/r2_qfr_test_fixture.json").read_text(encoding="utf-8")
    )["data"]
    legacy = QFRData.from_dict(legacy_payload)
    assert legacy.schema_version == 2
    assert legacy.to_dict() == legacy_payload
    assert all(
        legacy.q_availability[scenario][item] == 1.0
        for scenario in legacy.scenarios
        for item in legacy.items
    )


@pytest.mark.parametrize("bad", [-0.01, 1.01, float("nan"), float("inf")])
def test_q_availability_domain_is_closed_unit_interval(bad):
    payload = revised_payload()
    payload["q_availability"]["b_medium"]["ordinary"] = bad
    with pytest.raises(ValueError, match="q_availability"):
        QFRData.from_dict(payload)


def test_q_availability_requires_complete_item_scenario_coverage():
    payload = revised_payload()
    del payload["q_availability"]["b_medium"]["ordinary"]
    with pytest.raises(ValueError, match="q_availability"):
        QFRData.from_dict(payload)


def test_revision_requires_positive_ordered_base_fulfillment():
    for level, bad in (("0", 0.0), ("1", 0.2), ("2", 1.0)):
        payload = revised_payload()
        payload["reliability_mitigation"]["ordinary"][level] = bad
        with pytest.raises(ValueError, match="reliability_mitigation"):
            QFRData.from_dict(payload)


def test_retention_and_q_availability_act_as_independent_factors():
    data = revised_data()
    model = build_qfr_m0(data)
    item, scenario = "perishable", "b_medium"
    model.Q[item].set_value(10.0)
    assert pyo.value(model.retained_Q[item]) == pytest.approx(10.0 * data.retention[item])
    assert pyo.value(model.effective_Q[item, scenario]) == pytest.approx(
        10.0 * data.retention[item] * data.q_availability[scenario][item]
    )
    balance = coefficients(model.demand_balance[item, scenario].body)
    assert balance[f"Q[{item}]"] == pytest.approx(
        data.retention[item] * data.q_availability[scenario][item]
    )


def test_exact_recourse_uses_the_same_scenario_q_availability():
    data = revised_data()
    decision = zero_decision(data, "M0")
    decision = QFRFirstStage(
        **{**decision.__dict__, "q": {item: 2.0 for item in data.items}}
    )
    scenario = "c_severe"
    recourse = build_exact_recourse(data, decision, scenario)
    for item in data.items:
        body = coefficients(recourse.demand_balance[item].body)
        assert body == {f"u[{item}]": pytest.approx(1.0)}
        repn = generate_standard_repn(recourse.demand_balance[item].body)
        assert float(repn.constant) == pytest.approx(
            data.retention[item] * data.q_availability[scenario][item] * 2.0
        )


def test_restricted_master_preserves_q_availability_identity():
    data = revised_data()
    restricted = subset_data(data, ("b_medium",))
    assert restricted.schema_version == 3
    assert dict(restricted.q_availability["b_medium"]) == dict(
        data.q_availability["b_medium"]
    )
    assert restricted.scenario_sha256 != data.scenario_sha256


def test_revised_programmatic_nesting_is_structural():
    data = revised_data()
    m0 = build_qfr_m0(data)
    m1_zero = build_qfr_m1(data, disable_f=True)
    m1 = build_qfr_m1(data)
    m2_base = build_qfr_m2(data, reliability_levels=(0,))
    for item in data.items:
        for scenario in data.scenarios:
            assert coefficients(m0.demand_balance[item, scenario].body)[f"Q[{item}]"] == pytest.approx(
                coefficients(m1_zero.demand_balance[item, scenario].body)[f"Q[{item}]"]
            )
            assert pyo.value(m1.rho[item, scenario, 0]) == pytest.approx(
                pyo.value(m2_base.rho[item, scenario, 0])
            )


@pytest.mark.gurobi
def test_revised_programmatic_nesting_optimal_values():
    data = revised_data()
    models = (
        build_qfr_m0(data),
        build_qfr_m1(data, disable_f=True),
        build_qfr_m1(data),
        build_qfr_m2(data, reliability_levels=(0,)),
    )
    outcomes = [solve_exact(model) for model in models]
    assert all(outcome.status == "optimal" for outcome in outcomes)
    accounting = [validate_qfr_solution(data, model) for model in models]
    assert accounting[0].objective == pytest.approx(accounting[1].objective, abs=1e-7, rel=1e-9)
    assert accounting[2].objective == pytest.approx(accounting[3].objective, abs=1e-7, rel=1e-9)
    assert accounting[1].C_F == pytest.approx(0.0)
    assert accounting[1].C_R == pytest.approx(0.0)


@pytest.mark.parametrize("builder", [build_qfr_m0, build_qfr_m1, build_qfr_m2])
def test_revised_loaded_solution_accounting_is_scenario_specific(builder):
    data = revised_data()
    model = builder(data)
    for item in data.items:
        model.Q[item].set_value(2.0)
        for scenario in data.scenarios:
            available = (
                data.retention[item]
                * data.q_availability[scenario][item]
                * 2.0
            )
            model.u[item, scenario].set_value(
                max(0.0, data.demand[scenario][item] - available)
            )
        if model._qfr_kind != "M0":
            for level in model.R:
                model.F[item, level].set_value(0.0)
                model.z[item, level].set_value(0)
            for scenario in data.scenarios:
                model.x[item, scenario].set_value(0.0)
    losses = {
        scenario: sum(
            data.shortage_cost[item] * pyo.value(model.u[item, scenario])
            for item in data.items
        )
        for scenario in data.scenarios
    }
    model.theta.set_value(max(losses.values()))
    accounting = validate_qfr_solution(data, model).to_dict()
    for item in data.items:
        for scenario in data.scenarios:
            assert accounting["effective_q"][item][scenario] == pytest.approx(
                data.retention[item]
                * data.q_availability[scenario][item]
                * 2.0
            )


def test_frozen_pilot_configuration_is_constructed_without_rounding_or_execution():
    baseline = load_pilot_baseline(PILOT_CONFIG, 1.0)
    data = baseline.data
    assert baseline.reference_budget == pytest.approx(306313.545054945, abs=1e-9)
    assert data.storage_cost["Measles Vaccine"] == pytest.approx(0.08 / 6)
    assert data.storage_cost["Measles Vaccine"] * data.tau == pytest.approx(0.08)
    assert data.flexible_capacity == {
        "Sugar": pytest.approx(80400.0),
        "Measles Vaccine": pytest.approx(11256.0),
        "Rice": pytest.approx(80400.0),
    }
    expected = {
        "omega_1": (0.8, 1.0, 0.0),
        "omega_2": (1.0, 1.0, 0.0),
        "omega_3": (1.0, 0.85, 0.5),
        "omega_4": (1.2, 0.85, 0.5),
        "omega_5": (1.0, 0.7, 1.0),
    }
    nominal = {"Sugar": 67000.0, "Measles Vaccine": 9380.0, "Rice": 67000.0}
    for scenario, (multiplier, q_rho, delta) in expected.items():
        for item in data.items:
            assert data.demand[scenario][item] == pytest.approx(nominal[item] * multiplier)
            assert data.q_availability[scenario][item] == pytest.approx(q_rho)
            assert data.disruption[scenario][item] == pytest.approx(delta)
            for level, eta in enumerate((0.2, 0.5, 0.8)):
                fulfillment = 1 - (1 - eta) * delta
                expected_f = {
                    0.0: (1.0, 1.0, 1.0),
                    0.5: (0.6, 0.75, 0.9),
                    1.0: (0.2, 0.5, 0.8),
                }[delta][level]
                assert fulfillment == pytest.approx(expected_f)
    assert data.shortage_cost == {
        "Sugar": pytest.approx(2.2),
        "Measles Vaccine": pytest.approx(1.56),
        "Rice": pytest.approx(14.4),
    }
    for item in data.items:
        q_cost = data.q_unit_cost[item]
        assert data.reservation_cost[item] == pytest.approx(0.2 * q_cost)
        assert data.exercise_cost[item] == pytest.approx(0.85 * q_cost)
        assert data.reliability_cost[item] == {
            0: pytest.approx(0.0),
            1: pytest.approx(0.10 * q_cost),
            2: pytest.approx(0.25 * q_cost),
        }


@pytest.mark.parametrize("ratio", [0.9, 1.0, 1.1])
def test_pilot_budget_ratios_are_computed_from_unrounded_reference(ratio):
    baseline = load_pilot_baseline(PILOT_CONFIG, ratio)
    assert baseline.data.budget == pytest.approx(ratio * 306313.545054945)


def test_no_unregistered_pilot_scenario_or_budget_ratio_is_accepted(tmp_path):
    with pytest.raises(ValueError, match="budget ratio"):
        load_pilot_baseline(PILOT_CONFIG, 1.2)
    payload = json.loads(PILOT_CONFIG.read_text(encoding="utf-8"))
    payload["scenarios"].append(
        {"id": "unregistered", "demand_multiplier": 1.2, "q_availability": 0.7, "disruption": 1.0}
    )
    changed = tmp_path / "changed.json"
    changed.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="exactly five"):
        load_pilot_baseline(changed, 1.0)
