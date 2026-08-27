import json
from pathlib import Path
from types import SimpleNamespace

import pyomo.environ as pyo
from pyomo.repn import generate_standard_repn
from pyomo.opt import SolverStatus, TerminationCondition
import pytest

from robust_budget_allocation.data.mechanism_data import OptionData
from robust_budget_allocation.models.m0 import solve_m0
from robust_budget_allocation.models.m1 import build_m1, solve_m1
from robust_budget_allocation.models.m2 import build_m2, solve_m2
from robust_budget_allocation.models import mechanism_support as support
from robust_budget_allocation.runtime.solver import SolveOutcome, SolverConfiguration


FIXTURE = Path(__file__).parent / "fixtures/n3_mechanisms.json"
CASES = json.loads(FIXTURE.read_text(encoding="utf-8"))["cases"]


def coefficients(expr):
    repn = generate_standard_repn(expr)
    assert repn.is_linear()
    return {v.name: c for v, c in zip(repn.linear_vars, repn.linear_coefs)}


def accounting(data, result):
    base, rel = data.base, data.reliability
    assert result.status == "optimal", result.diagnostics
    assert result.C_Q == pytest.approx(sum(base.unit_cost[j] * result.q[j] for j in base.suppliers))
    cr = sum(rel.fixed_premium[j][result.reliability_choice[j]] + sum(
        rel.unit_premium[j][k] * result.q_by_level[j][k] for k in rel.levels[j]) for j in base.suppliers)
    assert result.C_R == pytest.approx(cr)
    assert result.option_fee == pytest.approx(data.option_fee * result.y_F)
    first = result.C_Q + result.C_R + result.option_fee
    losses = {}
    for w in base.scenarios:
        assert result.E[w] == pytest.approx(data.emergency_price[w] * result.g[w])
        assert result.E[w] <= data.option_cap * result.y_F + 1e-7
        assert first + result.E[w] <= base.budget + 1e-7
        assert result.unused_budget[w] == pytest.approx(base.budget - first - result.E[w])
        delivered = sum(rel.fulfillment[w][j][k] * result.q_by_level[j][k]
                        for j in base.suppliers for k in rel.levels[j])
        assert result.x[w] + result.u[w] == pytest.approx(base.demand[w])
        assert result.x[w] + result.h[w] == pytest.approx(delivered + result.g[w])
        assert min(result.u[w], result.h[w], result.g[w]) >= 0
        if result.y_F == 0:
            assert result.g[w] == pytest.approx(0)
            assert result.E[w] == pytest.approx(0)
        losses[w] = result.E[w] + base.shortage_penalty * result.u[w]
    assert result.worst_loss == pytest.approx(max(losses.values()))
    assert result.objective == pytest.approx(first + max(losses.values()))


def test_m1_m2_structural_accounting_and_no_extra_channels():
    data = OptionData.from_dict(CASES[10]["data"])
    one, two = build_m1(data.reliability), build_m2(data)
    assert set(one.component_map(pyo.Var)) == {"z", "q_level", "theta", "x", "u", "h"}
    assert set(two.component_map(pyo.Var)) == {"z", "q_level", "theta", "x", "u", "h", "y_F", "g"}
    assert two.z["supplier", "1"].is_binary() and two.y_F.is_binary()
    for model in (one, two):
        for c in model.component_data_objects(pyo.Constraint):
            coefficients(c.body)
        assert all(not name.startswith("u[") for name in coefficients(model.cash_budget.body))
    assert coefficients(one.C_R.expr) == {"z[supplier,'1']": .5, "q_level[supplier,'1']": .25}
    assert coefficients(two.total_cost.expr) == {
        "q_level[supplier,'0']": 1, "q_level[supplier,'1']": 1.25,
        "z[supplier,'1']": .5, "y_F": 1, "theta": 1,
    }
    budget = coefficients(two.scenario_budget["w"].body)
    assert budget["g[w]"] == 2 and budget["y_F"] == 1
    assert not any(name.startswith("u[") for name in budget)
    assert coefficients(two.worst_loss["w"].body) == {"g[w]": 2, "u[w]": 10, "theta": -1}
    assert coefficients(two.option_cap["w"].body) == {"g[w]": 2, "y_F": -10}
    assert pyo.value(two.scenario_budget["w"].upper) == 10


@pytest.mark.parametrize("restriction", ["missing_supplier", "unknown_level", "bad_option"])
def test_invalid_restriction_rejected(restriction):
    data = OptionData.from_dict(CASES[0]["data"])
    with pytest.raises(ValueError):
        if restriction == "missing_supplier": build_m1(data.reliability, fixed_reliability={})
        if restriction == "unknown_level": build_m1(data.reliability, fixed_reliability={"supplier": "unknown"})
        if restriction == "bad_option": build_m2(data, fixed_option=2)


@pytest.mark.gurobi
@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_mechanism_hand_cases(case):
    data = OptionData.from_dict(case["data"])
    result = (solve_m1(data.reliability, audit_inputs=[FIXTURE]) if case["model"] == "M1"
              else solve_m2(data, audit_inputs=[FIXTURE]))
    accounting(data, result)
    for name, expected in case["expected"].items():
        if name in ("reliability_choice", "worst_scenario"):
            assert getattr(result, name) == expected
        else:
            assert getattr(result, name) == pytest.approx(expected, abs=1e-7, rel=1e-9)
    if case["id"] == "expensive_emergency_no_exercise":
        assert result.g["expensive"] == pytest.approx(0)
    assert result.audit["solver_config"]["MIPGap"] == 0
    assert result.audit["environment"]["license_available"] is True


@pytest.mark.gurobi
@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_both_degeneration_relations(case):
    data = OptionData.from_dict(case["data"])
    zero = solve_m0(data.base)
    one_base = solve_m1(data.reliability, fixed_reliability={j: "0" for j in data.base.suppliers})
    one = solve_m1(data.reliability)
    two_off = solve_m2(data, fixed_option=0)
    assert zero.status == one_base.status == one.status == two_off.status == "optimal"
    for field in ("objective", "C_Q", "q", "u", "h", "x", "worst_loss"):
        assert getattr(one_base, field) == pytest.approx(getattr(zero, field), abs=1e-7, rel=1e-9)
    assert one_base.worst_scenario == zero.worst_scenario
    assert one_base.C_R == pytest.approx(0)
    for field in ("objective", "C_Q", "C_R", "q", "q_by_level", "u", "h", "x", "worst_loss", "unused_budget"):
        if field == "q_by_level":
            for j in data.base.suppliers:
                assert one.q_by_level[j] == pytest.approx(two_off.q_by_level[j], abs=1e-7, rel=1e-9)
        else:
            assert getattr(one, field) == pytest.approx(getattr(two_off, field), abs=1e-7, rel=1e-9)
    assert one.reliability_choice == two_off.reliability_choice
    assert one.worst_scenario == two_off.worst_scenario
    assert all(v == pytest.approx(0) for v in (*two_off.g.values(), *two_off.E.values()))
    assert zero.audit["scenario_sha256"] == one.audit["scenario_sha256"] == two_off.audit["scenario_sha256"]


@pytest.mark.parametrize("status", ["solver_error", "locally_optimal", "iteration_limit", "time_limit", "unknown", "invalid_solver_status"])
def test_nonoptimal_status_never_certified(monkeypatch, status):
    data = OptionData.from_dict(CASES[0]["data"])
    monkeypatch.setattr(support, "ensure_preflight_once", lambda: SimpleNamespace(to_dict=lambda: {"test_double": True}))
    monkeypatch.setattr(support, "_solve_mip", lambda *a: SolveOutcome(status, "gurobi_direct", 0, status))
    result = solve_m2(data)
    assert result.status == status and result.objective is None and result.q == {}


def test_mip_runtime_sets_zero_gaps_and_uses_status_validation(monkeypatch):
    options = {}
    fake = SimpleNamespace(options=options, solve=lambda *a, **k: SimpleNamespace(
        solver=SimpleNamespace(status=SolverStatus.error, termination_condition=TerminationCondition.optimal)))
    monkeypatch.setattr(support, "create_solver", lambda config: fake)
    result = support._solve_mip(object(), SolverConfiguration())
    assert options == {"MIPGap": 0.0, "MIPGapAbs": 0.0}
    assert result.status == "solver_error"


@pytest.mark.parametrize("violation", ["fractional_z", "quantity_link", "budget", "demand",
                                      "resource", "epigraph", "nan", "fixed_option", "fixed_reliability"])
def test_invalid_raw_solution_cannot_be_certified(violation):
    data = OptionData.from_dict(CASES[10]["data"])
    model = build_m2(data, fixed_option=0 if violation == "fixed_option" else None,
                     fixed_reliability={"supplier": "0"} if violation == "fixed_reliability" else None)
    model.z["supplier", "0"].set_value(0)
    model.z["supplier", "1"].set_value(1)
    model.q_level["supplier", "0"].set_value(0)
    model.q_level["supplier", "1"].set_value(2)
    model.y_F.set_value(1)
    model.g["w"].set_value(2)
    model.x["w"].set_value(4)
    model.u["w"].set_value(0)
    model.h["w"].set_value(0)
    model.theta.set_value(4)
    if violation == "fractional_z": model.z["supplier", "1"].set_value(.5, skip_validation=True)
    if violation == "quantity_link": model.q_level["supplier", "0"].set_value(1)
    if violation == "budget": model.g["w"].set_value(20)
    if violation == "demand": model.u["w"].set_value(1)
    if violation == "resource": model.h["w"].set_value(1)
    if violation == "epigraph": model.theta.set_value(0)
    if violation == "nan": model.theta.set_value(float("nan"), skip_validation=True)
    with pytest.raises(ValueError):
        support._extract(data, model, "M2")


@pytest.mark.gurobi
def test_deterministic_joint_fixture_repeats():
    data = OptionData.from_dict(CASES[10]["data"])
    first, second = solve_m2(data), solve_m2(data)
    for name in ("status", "objective", "C_Q", "C_R", "y_F", "q", "reliability_choice", "g", "E", "u", "h", "worst_scenario"):
        assert getattr(first, name) == getattr(second, name)
