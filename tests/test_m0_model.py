from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace

import pyomo.environ as pyo
from pyomo.repn import generate_standard_repn
import pytest

from robust_budget_allocation.data.model_data import BudgetAllocationData
from robust_budget_allocation.io.hashing import canonical_json_sha256
from robust_budget_allocation.models import m0
from robust_budget_allocation.runtime.environment import EnvironmentPreflightError
from robust_budget_allocation.runtime.solver import SolveOutcome


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "n2_m0_hand_cases.json"
CASES = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))["cases"]


def set_hand_solution(model, expected):
    for name in ("q", "x", "u", "h"):
        for key, value in expected[name].items():
            getattr(model, name)[key].set_value(value)
    model.theta.set_value(expected["worst_loss"])


def assert_balances(data, result):
    assert result.objective == pytest.approx(result.C_Q + result.worst_loss)
    assert result.C_Q <= data.budget + 1e-7
    assert result.unused_budget == pytest.approx(data.budget - result.C_Q)
    for w in data.scenarios:
        assert result.x[w] + result.u[w] == pytest.approx(data.demand[w])
        delivered = sum(data.base_fulfillment[w][j] * result.q[j] for j in data.suppliers)
        assert result.x[w] + result.h[w] == pytest.approx(delivered)
        assert result.u[w] >= 0 and result.h[w] >= 0
    assert result.worst_loss == pytest.approx(max(data.shortage_penalty * v for v in result.u.values()))


def test_exact_model_components_and_cash_coefficients(m0_data):
    model = m0.build_m0(m0_data)
    assert set(model.component_map(pyo.Var)) == {"q", "theta", "x", "u", "h"}
    assert all(v.is_continuous() for v in model.component_data_objects(pyo.Var))
    assert set(model.component_map(pyo.Constraint)) == {
        "cash_budget", "demand_balance", "resource_balance", "worst_loss",
    }
    budget = generate_standard_repn(model.cash_budget.body)
    assert [v.name for v in budget.linear_vars] == ["q[supplier]"]
    assert budget.linear_coefs == (2.0,)
    assert pyo.value(model.cash_budget.upper) == 20
    objective = generate_standard_repn(model.total_cost.expr)
    assert dict(zip((v.name for v in objective.linear_vars), objective.linear_coefs)) == {
        "q[supplier]": 2, "theta": 1,
    }
    assert all(generate_standard_repn(c.body).is_linear()
               for c in model.component_data_objects(pyo.Constraint))


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_hand_assignment_satisfies_frozen_equations_without_solver(case):
    data = BudgetAllocationData.from_dict(case["data"])
    model = m0.build_m0(data)
    set_hand_solution(model, case["expected"])
    for constraint in model.component_data_objects(pyo.Constraint):
        body = pyo.value(constraint.body)
        if constraint.has_lb():
            assert body >= pyo.value(constraint.lower) - 1e-9
        if constraint.has_ub():
            assert body <= pyo.value(constraint.upper) + 1e-9
    assert pyo.value(model.total_cost) == pytest.approx(case["expected"]["objective"])
    extracted = m0._extract_solution(data, model)
    assert extracted["objective"] == pytest.approx(case["expected"]["objective"])


def test_nonworst_reporting_does_not_add_objective_or_modify_quantity():
    case = next(c for c in CASES if c["id"] == "nonworst_allocation_slack")
    data = BudgetAllocationData.from_dict(case["data"])
    model = m0.build_m0(data)
    set_hand_solution(model, case["expected"])
    model.x["full"].set_value(4)
    model.u["full"].set_value(2)
    model.h["full"].set_value(4)
    result = m0._extract_solution(data, model)
    assert result["raw_solution"]["u"]["full"] == 2
    assert result["u"]["full"] == 0
    assert result["h"]["full"] == 2
    assert result["q"] == {"supplier": 8}
    assert result["objective"] == result["raw_solution"]["objective"] == 28


@pytest.mark.parametrize("bad", ["balance", "cap", "theta", "nan"])
def test_invalid_loaded_solution_is_rejected(bad):
    case = CASES[0]
    data = BudgetAllocationData.from_dict(case["data"])
    model = m0.build_m0(data)
    set_hand_solution(model, case["expected"])
    if bad == "balance":
        model.x["scenario"].set_value(0)
    elif bad == "cap":
        model.q["supplier"].set_value(11, skip_validation=True)
    elif bad == "theta":
        model.theta.set_value(10)
    else:
        model.theta.set_value(float("nan"), skip_validation=True)
    with pytest.raises(ValueError):
        m0._extract_solution(data, model)


@pytest.mark.parametrize("status", ["solver_error", "locally_optimal", "iteration_limit", "time_limit", "unknown", "invalid_solver_status"])
def test_nonoptimal_runtime_never_returns_certified_values(m0_data, monkeypatch, status):
    # Synthetic error-path test only, never represented as licensed evidence.
    monkeypatch.setattr(m0, "ensure_preflight_once", lambda: SimpleNamespace(to_dict=lambda: {"test_double": True}))
    monkeypatch.setattr(m0, "solve_model", lambda *a, **kw: SolveOutcome(status, "gurobi_direct", 0, status))
    result = m0.solve_m0(m0_data)
    assert result.status == status
    assert result.objective is None and result.worst_loss is None and result.q == {}
    assert result.audit["solver_outcome"]["status"] == status


def test_preflight_failure_propagates(m0_data, monkeypatch):
    def fail():
        raise EnvironmentPreflightError("test license unavailable")
    monkeypatch.setattr(m0, "ensure_preflight_once", fail)
    with pytest.raises(EnvironmentPreflightError):
        m0.solve_m0(m0_data)


def test_invalid_optimal_payload_becomes_numerical_invalid(m0_data, monkeypatch):
    monkeypatch.setattr(m0, "ensure_preflight_once", lambda: SimpleNamespace(to_dict=lambda: {"test_double": True}))
    def invalid_solution(model, **kwargs):
        set_hand_solution(model, CASES[0]["expected"])
        model.theta.set_value(10)
        return SolveOutcome("optimal", "gurobi_direct", 0, "optimal")
    monkeypatch.setattr(m0, "solve_model", invalid_solution)
    result = m0.solve_m0(m0_data)
    assert result.status == "numerical_invalid"
    assert result.objective is None and result.q == {}
    assert "worst shortage loss" in result.diagnostics[0]


@pytest.mark.gurobi
@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_real_m0_hand_solutions_and_audit(case, tmp_path):
    data = BudgetAllocationData.from_dict(case["data"])
    result = m0.solve_m0(data, audit_inputs=[FIXTURE_PATH])
    assert result.status == "optimal", result.diagnostics
    for name, expected in case["expected"].items():
        assert getattr(result, name) == pytest.approx(expected), name
    assert_balances(data, result)
    assert len(result.audit["source"]["git"]["commit_sha"]) == 40
    assert len(result.audit["source"]["git"]["tree_sha"]) == 40
    assert result.audit["data_sha256"] == data.data_sha256
    assert result.audit["environment"]["gurobi_optimizer"] == "13.0.2"
    assert result.audit["environment"]["license_available"] is True
    destination = tmp_path / "development-result.json"
    result.write_json(destination)
    payload = json.loads(destination.read_text(encoding="utf-8"))
    digest = payload.pop("result_sha256")
    assert digest == canonical_json_sha256(payload)
    assert payload["classification"] == "development/correctness_evidence"


@pytest.mark.gurobi
@pytest.mark.parametrize("budget", [0, 2, 4, 6, 8, 10])
def test_budget_grid_property_has_hand_derived_optimum(m0_data, budget):
    data = replace(m0_data, budget=budget, demand={"scenario": 4})
    result = m0.solve_m0(data)
    expected_q = min(4, budget / 2)
    assert result.status == "optimal"
    assert result.q["supplier"] == pytest.approx(expected_q)
    assert result.objective == pytest.approx(2 * expected_q + 10 * (4 - expected_q))
    assert_balances(data, result)


@pytest.mark.gurobi
def test_fulfillment_decrease_at_same_purchase_increases_shortage():
    full, impaired = [m0.solve_m0(BudgetAllocationData.from_dict(c["data"])) for c in CASES[1:3]]
    assert full.status == impaired.status == "optimal"
    assert full.q == impaired.q == {"supplier": 2}
    assert impaired.u["scenario"] > full.u["scenario"]


@pytest.mark.gurobi
@pytest.mark.parametrize("boundary", ["zero_demand", "zero_fulfillment"])
def test_zero_boundaries_remain_feasible(m0_data, boundary):
    data = (replace(m0_data, demand={"scenario": 0}) if boundary == "zero_demand"
            else replace(m0_data, base_fulfillment={"scenario": {"supplier": 0}}))
    result = m0.solve_m0(data)
    assert result.status == "optimal"
    assert result.q == {"supplier": 0}
    assert_balances(data, result)
