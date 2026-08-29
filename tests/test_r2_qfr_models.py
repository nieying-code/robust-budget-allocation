from copy import deepcopy
import json
from pathlib import Path

import pyomo.environ as pyo
from pyomo.repn import generate_standard_repn
import pytest

from robust_budget_allocation.data.qfr_data import QFRData
from robust_budget_allocation.models.qfr_m0 import build_qfr_m0
from robust_budget_allocation.models.qfr_m1 import build_qfr_m1
from robust_budget_allocation.models.qfr_m2 import build_qfr_m2
from robust_budget_allocation.models.qfr_support import validate_qfr_solution
from robust_budget_allocation.runtime.solver import solve_model


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "r2_qfr_test_fixture.json"
PAYLOAD = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def qfr_data():
    return QFRData.from_dict(PAYLOAD["data"])


def coefficients(expression):
    repn = generate_standard_repn(expression)
    assert repn.is_linear()
    return {variable.name: float(coefficient) for variable, coefficient in zip(
        repn.linear_vars, repn.linear_coefs
    )}


def constraint_signature(component):
    result = []
    for index in component:
        constraint = component[index]
        result.append((
            index,
            coefficients(constraint.body),
            None if constraint.lower is None else float(pyo.value(constraint.lower)),
            None if constraint.upper is None else float(pyo.value(constraint.upper)),
        ))
    return result


def load_all_shortage_solution(data, model):
    for item in data.items:
        model.Q[item].set_value(0)
        for scenario in data.scenarios:
            model.u[item, scenario].set_value(data.demand[scenario][item])
    if model._qfr_kind != "M0":
        for item in data.items:
            for level in model.R:
                model.F[item, level].set_value(0)
                model.z[item, level].set_value(0)
            for scenario in data.scenarios:
                model.x[item, scenario].set_value(0)
    worst = max(
        sum(data.shortage_cost[item] * data.demand[scenario][item] for item in data.items)
        for scenario in data.scenarios
    )
    model.theta.set_value(worst)


def test_m0_m1_m2_have_only_frozen_stage_variables(qfr_data):
    m0, m1, m2 = build_qfr_m0(qfr_data), build_qfr_m1(qfr_data), build_qfr_m2(qfr_data)
    assert set(m0.component_map(pyo.Var)) == {"Q", "theta", "u"}
    assert set(m1.component_map(pyo.Var)) == {"Q", "theta", "u", "F", "z", "x"}
    assert set(m2.component_map(pyo.Var)) == {"Q", "theta", "u", "F", "z", "x"}
    assert tuple(m1.R) == (0,)
    assert tuple(m2.R) == (0, 1, 2)
    assert all(m2.z[item, level].is_binary() for item in qfr_data.items for level in m2.R)
    for model in (m0, m1, m2):
        assert model._qfr_data_sha256 == qfr_data.data_sha256
        assert model._qfr_scenario_sha256 == qfr_data.scenario_sha256
        for constraint in model.component_data_objects(pyo.Constraint):
            assert generate_standard_repn(constraint.body).is_linear()
        assert generate_standard_repn(model.total_cost.expr).is_linear()


def test_heterogeneous_q_cost_and_effective_inventory_are_item_indexed(qfr_data):
    model = build_qfr_m0(qfr_data)
    q_coefficients = coefficients(model.C_Q.expr)
    for item in qfr_data.items:
        assert q_coefficients[f"Q[{item}]"] == pytest.approx(
            qfr_data.q_unit_cost[item] + qfr_data.storage_cost[item] * qfr_data.tau
        )
        model.Q[item].set_value(2)
        assert pyo.value(model.effective_Q[item]) == pytest.approx(2 * qfr_data.retention[item])


def test_m2_f_r_fulfillment_capacity_and_one_level_structure(qfr_data):
    model = build_qfr_m2(qfr_data)
    for item in qfr_data.items:
        assert pyo.value(model.one_reliability_level[item].upper) == 1
        for level in model.R:
            link = coefficients(model.capacity_link[item, level].body)
            assert link[f"F[{item},{level}]"] == pytest.approx(1)
            assert link[f"z[{item},{level}]"] == pytest.approx(-qfr_data.flexible_capacity[item])
    for level in model.R:
        assert pyo.value(model.rho["ordinary", "moderate", level]) == pytest.approx(1)
    for item in qfr_data.items:
        for level in model.R:
            model.F[item, level].set_value(0)
            model.z[item, level].set_value(0)
        model.F[item, 2].set_value(1)
        model.z[item, 2].set_value(1)
        for scenario in qfr_data.scenarios:
            expected = 1 - (1 - qfr_data.reliability_mitigation[item][2]) * qfr_data.disruption[scenario][item]
            assert pyo.value(model.fulfillable_F[item, scenario]) == pytest.approx(expected)


def test_fixed_total_budget_excludes_shortage_but_objective_epigraph_includes_it(qfr_data):
    for model in (build_qfr_m0(qfr_data), build_qfr_m1(qfr_data), build_qfr_m2(qfr_data)):
        for scenario in qfr_data.scenarios:
            budget = coefficients(model.scenario_budget[scenario].body)
            assert not any(name.startswith("u[") for name in budget)
            if model._qfr_kind == "M0":
                assert not any(name.startswith("x[") for name in budget)
            else:
                for item in qfr_data.items:
                    assert budget[f"x[{item},{scenario}]"] == pytest.approx(
                        qfr_data.exercise_cost[item]
                    )
            loss = coefficients(model.worst_loss[scenario].body)
            assert loss["theta"] == pytest.approx(-1)
            for item in qfr_data.items:
                assert loss[f"u[{item},{scenario}]"] == pytest.approx(
                    qfr_data.shortage_cost[item]
                )
                if model._qfr_kind != "M0":
                    assert loss[f"x[{item},{scenario}]"] == pytest.approx(
                        qfr_data.exercise_cost[item]
                    )


def test_m2_base_reliability_is_structurally_identical_to_m1(qfr_data):
    m1 = build_qfr_m1(qfr_data)
    m2_base = build_qfr_m2(qfr_data, reliability_levels=(0,))
    assert set(m1.component_map(pyo.Var)) == set(m2_base.component_map(pyo.Var))
    assert set(m1.component_map(pyo.Constraint)) == set(m2_base.component_map(pyo.Constraint))
    for expression in ("C_Q", "C_F", "C_R", "C_pre"):
        assert coefficients(getattr(m1, expression).expr) == coefficients(getattr(m2_base, expression).expr)
    for name in (
        "one_reliability_level",
        "capacity_link",
        "exercise_limit",
        "demand_balance",
        "scenario_budget",
        "worst_loss",
    ):
        assert constraint_signature(getattr(m1, name)) == constraint_signature(getattr(m2_base, name))
    assert coefficients(m1.total_cost.expr) == coefficients(m2_base.total_cost.expr)


def test_m1_f_zero_projects_to_m0_and_has_no_r_spending_or_value(qfr_data):
    m0 = build_qfr_m0(qfr_data)
    restricted = build_qfr_m1(qfr_data, disable_f=True)
    assert all(
        restricted.F[item, 0].fixed and pyo.value(restricted.F[item, 0]) == 0
        for item in qfr_data.items
    )
    assert all(
        restricted.z[item, 0].fixed and pyo.value(restricted.z[item, 0]) == 0
        for item in qfr_data.items
    )
    assert coefficients(restricted.C_R.expr) == {}
    assert pyo.value(restricted.C_F) == pytest.approx(0)
    assert pyo.value(restricted.C_R) == pytest.approx(0)
    assert coefficients(m0.C_Q.expr) == coefficients(restricted.C_Q.expr)
    for scenario in qfr_data.scenarios:
        assert coefficients(m0.shortage_loss[scenario].expr) == coefficients(
            restricted.shortage_loss[scenario].expr
        )


@pytest.mark.parametrize("builder", [build_qfr_m0, build_qfr_m1, build_qfr_m2])
def test_independent_accounting_accepts_common_all_shortage_feasible_point(qfr_data, builder):
    model = builder(qfr_data)
    load_all_shortage_solution(qfr_data, model)
    accounting = validate_qfr_solution(qfr_data, model)
    assert accounting.data_sha256 == qfr_data.data_sha256
    assert accounting.scenario_sha256 == qfr_data.scenario_sha256
    assert accounting.to_dict()["data_sha256"] == qfr_data.data_sha256
    assert accounting.to_dict()["scenario_sha256"] == qfr_data.scenario_sha256
    assert accounting.C_F == pytest.approx(0)
    assert accounting.C_R == pytest.approx(0)
    assert all(value == pytest.approx(qfr_data.budget) for value in accounting.unused_cash.values())
    assert accounting.objective == pytest.approx(accounting.theta)


@pytest.mark.parametrize("violation", ["demand", "capacity", "budget", "epigraph", "fractional_z"])
def test_independent_accounting_rejects_invalid_loaded_values(qfr_data, violation):
    model = build_qfr_m2(qfr_data)
    load_all_shortage_solution(qfr_data, model)
    if violation == "demand":
        model.u["ordinary", "moderate"].set_value(0)
    elif violation == "capacity":
        model.x["ordinary", "moderate"].set_value(1)
    elif violation == "budget":
        model.Q["ordinary"].set_value(100)
    elif violation == "epigraph":
        model.theta.set_value(0)
    else:
        model.z["ordinary", 0].set_value(0.5, skip_validation=True)
    with pytest.raises(ValueError):
        validate_qfr_solution(qfr_data, model)


@pytest.mark.parametrize("mutation", ["disruption", "static_cost", "retention"])
def test_validation_rejects_same_indices_with_different_scientific_data(qfr_data, mutation):
    model = build_qfr_m2(qfr_data)
    load_all_shortage_solution(qfr_data, model)
    changed = deepcopy(PAYLOAD["data"])
    if mutation == "disruption":
        changed["disruption"]["moderate"]["ordinary"] = 0.1
    elif mutation == "static_cost":
        changed["q_unit_cost"]["ordinary"] += 0.25
    else:
        changed["retention"]["ordinary"] = 0.9
    other = QFRData.from_dict(changed)
    assert other.items == qfr_data.items and other.scenarios == qfr_data.scenarios
    with pytest.raises(ValueError, match="identity"):
        validate_qfr_solution(other, model)


@pytest.mark.parametrize(
    ("attribute", "replacement"),
    [
        ("_qfr_data_sha256", None),
        ("_qfr_data_sha256", "0" * 64),
        ("_qfr_scenario_sha256", None),
        ("_qfr_scenario_sha256", "f" * 64),
    ],
)
def test_validation_rejects_missing_or_changed_model_identity(qfr_data, attribute, replacement):
    model = build_qfr_m2(qfr_data)
    load_all_shortage_solution(qfr_data, model)
    if replacement is None:
        delattr(model, attribute)
    else:
        setattr(model, attribute, replacement)
    with pytest.raises(ValueError, match="identity"):
        validate_qfr_solution(qfr_data, model)


def test_m1_is_always_restricted_to_base_reliability(qfr_data):
    assert tuple(build_qfr_m1(qfr_data).R) == (0,)


@pytest.mark.parametrize("levels", [(0, 1), (3,), (), (0, 0)])
def test_unfrozen_or_invalid_m2_level_restrictions_are_rejected(qfr_data, levels):
    with pytest.raises(ValueError):
        build_qfr_m2(qfr_data, reliability_levels=levels)


@pytest.mark.gurobi
def test_programmatic_nesting_optimal_values(qfr_data):
    m0 = build_qfr_m0(qfr_data)
    m1_f_zero = build_qfr_m1(qfr_data, disable_f=True)
    m1 = build_qfr_m1(qfr_data)
    m2_base = build_qfr_m2(qfr_data, reliability_levels=(0,))
    outcomes = [solve_model(model) for model in (m0, m1_f_zero, m1, m2_base)]
    assert all(outcome.status == "optimal" for outcome in outcomes)
    values = [validate_qfr_solution(qfr_data, model) for model in (m0, m1_f_zero, m1, m2_base)]
    assert values[0].objective == pytest.approx(values[1].objective, abs=1e-7, rel=1e-9)
    assert values[2].objective == pytest.approx(values[3].objective, abs=1e-7, rel=1e-9)
    assert values[1].C_F == pytest.approx(0)
    assert values[1].C_R == pytest.approx(0)


@pytest.mark.gurobi
def test_full_m2_three_item_fixture_builds_solves_and_validates(qfr_data):
    model = build_qfr_m2(qfr_data)
    outcome = solve_model(model)
    assert outcome.status == "optimal", outcome
    accounting = validate_qfr_solution(qfr_data, model)
    assert accounting.model_kind == "M2"
    assert accounting.reliability_levels == (0, 1, 2)
    assert all(value >= -1e-7 for value in accounting.unused_cash.values())
