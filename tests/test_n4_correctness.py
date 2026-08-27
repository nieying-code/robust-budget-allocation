"""N4 true licensed tests and explicitly synthetic negative protocol tests."""

from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pyomo.environ as pyo
from pyomo.opt import SolverStatus, TerminationCondition
import pytest

from robust_budget_allocation.data.mechanism_data import OptionData
from robust_budget_allocation.io.hashing import sha256_file
from robust_budget_allocation.models.m2 import build_m2, solve_m2
from robust_budget_allocation.algorithms import common, exact_oracle as oracle_module, standard_ccg as ccg
from robust_budget_allocation.algorithms.extensive_form import build_extensive_form, solve_extensive_form
from robust_budget_allocation.algorithms.verification import verify_pair

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/n4_correctness.json"
CASES = json.loads(FIXTURE.read_text(encoding="utf-8"))["cases"]


def data(index=13):
    return OptionData.from_dict(CASES[index]["data"])


def test_protocol_frozen_hash_and_tolerance():
    assert sha256_file(ROOT / common.PROTOCOL_PATH) == common.PROTOCOL_SHA256
    assert common.tolerance(0, 0) == pytest.approx(1.01e-7)
    assert common.tolerance(1e6, 0) == pytest.approx(.0010001)
    for value in (float("nan"), float("inf")):
        with pytest.raises(ValueError): common.tolerance(value, 0)


def test_ef_uses_exact_unchanged_m2_builder():
    ef, old = build_extensive_form(data()), build_m2(data())
    assert [(c.name, str(c.expr)) for c in ef.component_data_objects(pyo.Constraint)] == [
        (c.name, str(c.expr)) for c in old.component_data_objects(pyo.Constraint)]
    assert str(ef.total_cost.expr) == str(old.total_cost.expr)
    assert set(ef.Omega) == set(data().base.scenarios)
    reduced = common.build_master(data(), ["a_initial"])
    assert list(reduced.Omega) == ["a_initial"]
    assert str(reduced.C_Q.expr) == str(ef.C_Q.expr)
    assert str(reduced.C_R.expr) == str(ef.C_R.expr)
    assert hasattr(reduced, "cash_budget")


@pytest.mark.parametrize("subset", [[], ["bad"], ["a_initial", "a_initial"]])
def test_master_rejects_invalid_subset(subset):
    with pytest.raises(ValueError): common.build_master(data(), subset)


@pytest.mark.parametrize("limit", [0, -1, 1.5, True])
def test_iteration_limit_strict(limit):
    with pytest.raises(ValueError): ccg.solve_a0(data(), max_iterations=limit)


@pytest.mark.parametrize("solver_status,termination,expected", [
    (SolverStatus.ok, TerminationCondition.optimal, "optimal"),
    (SolverStatus.ok, TerminationCondition.globallyOptimal, "optimal"),
    (SolverStatus.ok, TerminationCondition.locallyOptimal, "locally_optimal"),
    (SolverStatus.error, TerminationCondition.optimal, "solver_error"),
    (SolverStatus.warning, TerminationCondition.optimal, "invalid_solver_status"),
    (SolverStatus.ok, TerminationCondition.maxTimeLimit, "time_limit"),
    (SolverStatus.ok, TerminationCondition.maxIterations, "iteration_limit"),
    (SolverStatus.ok, TerminationCondition.infeasible, "infeasible"),
    (SolverStatus.ok, TerminationCondition.unbounded, "unbounded"),
    (SolverStatus.unknown, TerminationCondition.unknown, "unknown"),
])
def test_exact_solver_status_acceptance_synthetic(monkeypatch, solver_status, termination, expected):
    raw = SimpleNamespace(solver=SimpleNamespace(status=solver_status, termination_condition=termination),
                          problem=SimpleNamespace(lower_bound=1))
    fake = SimpleNamespace(options={}, solve=lambda *a, **kw: raw)
    monkeypatch.setattr(common, "create_solver", lambda cfg: fake)
    monkeypatch.setattr(common, "validate_loaded_model", lambda m: None)
    model = SimpleNamespace(total_cost=1, solutions=SimpleNamespace(load_from=lambda r: None))
    result = common.solve_exact(model)
    assert result["status"] == expected
    assert fake.options == common.EXTRA_OPTIONS
    if expected != "optimal": assert result["objective"] is None


@pytest.mark.parametrize("bound", [float("inf"), float("nan"), -1])
def test_optimal_label_with_invalid_bound_fails(monkeypatch, bound):
    raw = SimpleNamespace(solver=SimpleNamespace(status=SolverStatus.ok, termination_condition=TerminationCondition.optimal),
                          problem=SimpleNamespace(lower_bound=bound))
    monkeypatch.setattr(common, "create_solver", lambda cfg: SimpleNamespace(options={}, solve=lambda *a, **kw: raw))
    monkeypatch.setattr(common, "validate_loaded_model", lambda m: None)
    result = common.solve_exact(SimpleNamespace(total_cost=1, solutions=SimpleNamespace(load_from=lambda r: None)))
    assert result["status"] == "numerical_failure" and result["objective"] is None


@pytest.mark.gurobi
@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_ef_a0_correctness(case):
    d = OptionData.from_dict(case["data"])
    ef, a0 = solve_extensive_form(d, audit_inputs=[FIXTURE]), ccg.solve_a0(d, audit_inputs=[FIXTURE])
    assert ef["status"] == "optimal", ef
    assert a0["status"] == "certified", a0
    checks = verify_pair(d, ef, a0)
    assert checks["status"] == "PASS"
    if "expected_objective" in case: assert ef["objective"] == pytest.approx(case["expected_objective"])
    if "expected_iterations" in case: assert a0["iterations"] == case["expected_iterations"]
    if "expected_worst" in case: assert a0["incumbent"]["oracle"]["worst_scenario"] == case["expected_worst"]
    previous = solve_m2(d)
    assert previous.status == "optimal"
    assert ef["objective"] == pytest.approx(previous.objective, abs=1e-7, rel=1e-9)
    # These cases have unambiguous economically relevant first-stage decisions.
    if case["id"] in ("option_value", "option_no_value", "joint_reliability_option_accounting", "three_round_cross_failures"):
        assert ef["first_stage"] == a0["incumbent"]["first_stage"]
        assert ef["oracle"]["worst_loss"] == a0["incumbent"]["oracle"]["worst_loss"]


@pytest.mark.gurobi
def test_real_iteration_exhaustion_not_converged():
    result = ccg.solve_a0(data(), max_iterations=1)
    assert result["status"] == "iteration_limit" and result["objective"] is None
    assert result["exact_oracle_calls"] == 1
    assert result["trace"][0]["violation"] > 0


@pytest.mark.parametrize("status", ["solver_error", "infeasible", "unbounded", "time_limit", "iteration_limit", "locally_optimal", "unknown", "numerical_failure"])
def test_master_failures_cannot_certify(monkeypatch, status):
    monkeypatch.setattr(ccg, "audit", lambda *a, **k: {"synthetic_negative_test": True})
    monkeypatch.setattr(ccg, "solve_exact", lambda *a: {"status": status})
    result = ccg.solve_a0(data())
    assert result["status"] == status and result["objective"] is None
    assert result["exact_oracle_calls"] == 0 and result["incumbent"] is None


@pytest.mark.gurobi
@pytest.mark.parametrize("failure", ["oracle_error", "partial", "repeated_violation", "bound_crossing"])
def test_corrupted_certification_paths_fail(monkeypatch, failure):
    if failure == "oracle_error":
        monkeypatch.setattr(ccg, "exact_oracle", lambda *a: {"status": "oracle_failure", "cause": "time_limit", "scenarios": []})
    if failure == "partial":
        original = ccg.exact_oracle
        def subset(*args):
            result = original(*args)
            result["scenarios"].pop()
            return result
        monkeypatch.setattr(ccg, "exact_oracle", subset)
    if failure in ("repeated_violation", "bound_crossing"):
        original_solve = ccg.solve_exact
        def altered(model):
            result = original_solve(model)
            if failure == "repeated_violation":
                model.theta.set_value(pyo.value(model.theta)-1, skip_validation=True)
                result["objective"] -= 1
                result["lower_bound"] -= 1
            else:
                result["lower_bound"] = 1e5
            return result
        monkeypatch.setattr(ccg, "solve_exact", altered)
    d = data(6) if failure == "repeated_violation" else data()
    result = ccg.solve_a0(d)
    expected = {"oracle_error": "oracle_failure", "partial": "oracle_failure",
                "repeated_violation": "convergence_failure", "bound_crossing": "numerical_failure"}[failure]
    assert result["status"] == expected and result["objective"] is None
    assert result["iterations"] == 1


@pytest.mark.gurobi
def test_price_penalty_tie_and_deterministic_oracle():
    payload = CASES[6]["data"]
    payload = deepcopy(payload)
    payload["emergency_price"]["w"] = payload["reliability"]["base"]["shortage_penalty"]
    d = OptionData.from_dict(payload)
    decision = dict(q_by_level={"supplier": {"0": 0, "1": 0}}, reliability_choice={"supplier": "0"}, y_F=1)
    first = oracle_module.exact_oracle(d, decision, 0)
    second = oracle_module.exact_oracle(d, decision, 0)
    assert first["status"] == second["status"] == "optimal"
    assert first["scenarios"][0]["g"] == second["scenarios"][0]["g"] == 0
    assert first["worst_loss"] == second["worst_loss"] == 50


@pytest.mark.gurobi
def test_saved_trace_rejects_mutation():
    d = data()
    ef, a0 = solve_extensive_form(d), ccg.solve_a0(d)
    for mutate in (
        lambda x: x["trace"][0].update(candidate_UB=1),
        lambda x: x.update(exact_oracle_calls=0),
        lambda x: x["incumbent"].update(iteration=1),
        lambda x: x["trace"][-1].update(convergence=False),
    ):
        corrupted = deepcopy(a0)
        mutate(corrupted)
        with pytest.raises(ValueError): verify_pair(d, ef, corrupted)


@pytest.mark.gurobi
def test_ef_and_multiple_a0_iterations_share_one_real_preflight(monkeypatch):
    from robust_budget_allocation.runtime import environment
    calls = []
    actual = environment.run_preflight
    def counted():
        calls.append(1)
        return actual()
    monkeypatch.setattr(environment, "_PREFLIGHT_REPORT", None)
    monkeypatch.setattr(environment, "run_preflight", counted)
    assert solve_extensive_form(data())["status"] == "optimal"
    assert ccg.solve_a0(data())["status"] == "certified"
    assert calls == [1]


@pytest.mark.parametrize("mutation", ["nan", "negative", "invalid_option", "nonselected_quantity", "cash"])
def test_invalid_first_stage_rejected(mutation):
    d = data(0)
    decision = dict(q_by_level={"supplier": {"0": 0, "1": 0}}, reliability_choice={"supplier": "0"}, y_F=0)
    if mutation == "nan": decision["q_by_level"]["supplier"]["0"] = float("nan")
    if mutation == "negative": decision["q_by_level"]["supplier"]["0"] = -1
    if mutation == "invalid_option": decision["y_F"] = True
    if mutation == "nonselected_quantity": decision["q_by_level"]["supplier"]["1"] = 1
    if mutation == "cash":
        payload = d.to_dict()
        payload["reliability"]["base"]["budget"] = 0
        d = OptionData.from_dict(payload)
        decision["y_F"] = 1
    with pytest.raises(ValueError): oracle_module.exact_oracle(d, decision, 0)
