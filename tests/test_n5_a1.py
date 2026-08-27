"""A1 correctness and deterministic lifecycle/state-machine tests, not benchmarks."""

from copy import deepcopy
import json
from pathlib import Path

import pytest

from robust_budget_allocation.algorithms import memory_guided_ccg as a1
from robust_budget_allocation.algorithms.a1_candidates import candidate_plan
from robust_budget_allocation.algorithms.a1_memory import ScenarioMemory
from robust_budget_allocation.algorithms.a1_verification import verify_three, verify_a1
from robust_budget_allocation.algorithms.common import ROOT
from robust_budget_allocation.algorithms.extensive_form import solve_extensive_form
from robust_budget_allocation.algorithms.standard_ccg import solve_a0
from robust_budget_allocation.data.mechanism_data import OptionData
from robust_budget_allocation.io.hashing import sha256_file

FIXTURE = ROOT / "tests/fixtures/n5_correctness.json"
CASES = json.loads(FIXTURE.read_text(encoding="utf-8"))["cases"]


def data(index=13):
    return OptionData.from_dict(CASES[index]["data"])


def no_purchase(d):
    return dict(q_by_level={j: {k: 0 for k in d.reliability.levels[j]} for j in d.base.suppliers},
                reliability_choice={j: "0" for j in d.base.suppliers}, y_F=0)


def memory_row(w, loss=1):
    return dict(scenario=w, loss=loss, status="optimal")


def test_protocol_hash_frozen_and_no_cross_solve_argument():
    import inspect
    assert sha256_file(ROOT / a1.A1_PROTOCOL_PATH) == a1.A1_PROTOCOL_SHA256
    assert set(inspect.signature(a1.solve_a1).parameters) == {"data", "max_iterations", "audit_inputs"}
    assert a1.a1_settings()["cross_solve_memory"] is False


def test_memory_order_capacity_eviction_and_active_skip():
    ids = [f"s{i:02d}" for i in range(10)]
    memory = ScenarioMemory("data", ids)
    update = memory.update([memory_row(w, i) for i, w in enumerate(ids)], 1, "EXACT")
    assert [e["scenario"] for e in update["evicted"]] == ["s01", "s00"]
    assert len(memory.snapshot()) == 8
    plan = memory.inspection_plan(["s09", "s09"])
    assert plan["skipped_active"] == ["s09"]
    assert plan["planned"] == ["s08", "s07"]
    # Newer observations take priority for retention, even at lower loss.
    update = memory.update([memory_row("s00", 0)], 2, "CANDIDATE")
    assert update["evicted"][0]["scenario"] == "s02"
    copied = memory.snapshot()
    copied[0]["last_loss"] = 1000
    assert memory.snapshot()[0]["last_loss"] != 1000


def test_memory_score_and_recency_ties_use_canonical_id():
    memory = ScenarioMemory("data", ["zeta", "alpha", "beta"])
    memory.update([memory_row("zeta", 5), memory_row("alpha", 5)], 1, "EXACT")
    memory.update([memory_row("beta", 5)], 2, "CANDIDATE")
    assert memory.inspection_plan([])["planned"] == ["beta", "alpha"]


@pytest.mark.parametrize("fault,reason", [("stale", "stale"), ("data", "identity_mismatch"),
    ("future", "invalid_iteration"), ("nan", "invalid_loss"), ("negative", "invalid_loss"),
    ("source", "invalid_source"), ("unknown", "unknown_scenario"), ("malformed", "malformed_entry")])
def test_stale_or_invalid_memory_removed(fault, reason):
    memory = ScenarioMemory("data", ["w"])
    memory.update([memory_row("w")], 1, "EXACT")
    if fault == "data": memory._entries["w"]["data_sha256"] = "other-run"
    if fault == "future": memory._entries["w"]["last_iteration"] = 5
    if fault == "nan": memory._entries["w"]["last_loss"] = float("nan")
    if fault == "negative": memory._entries["w"]["last_loss"] = -1
    if fault == "source": memory._entries["w"]["last_source"] = []
    if fault == "unknown": memory.scenarios = frozenset()
    if fault == "malformed": memory._entries["w"] = None
    removed = memory.prune(6 if fault == "stale" else 3)
    assert removed[0]["reason"] == reason and memory.snapshot() == []


def test_memory_ttl_boundary_and_empty_state():
    memory = ScenarioMemory("data", ["w"])
    assert memory.inspection_plan([])["planned"] == []
    memory.update([memory_row("w")], 1, "EXACT")
    assert memory.prune(5) == []
    assert memory.prune(6)[0]["reason"] == "stale"
    assert ScenarioMemory("data", ["w"]).snapshot() == []


def test_candidate_ranking_tie_exclusions_and_exhaustion():
    d = data()
    decision = no_purchase(d)
    plan = candidate_plan(d, decision, ["a_initial", "a_initial"], [])
    assert plan["ranking"] == ["b_first_fails", "c_second_fails"]
    assert plan["scores"] == {"b_first_fails": 40, "c_second_fails": 40}
    assert plan["planned"] == ["b_first_fails"]
    assert plan["excluded"] == [{"scenario": "a_initial", "reason": "active"}]
    plan = candidate_plan(d, decision, ["a_initial", "b_first_fails"], ["c_second_fails"])
    assert plan["pool"] == plan["ranking"] == plan["planned"] == []
    assert plan["excluded"][-1]["reason"] == "already_inspected"


def test_score_uses_no_emergency_price_or_future_oracle():
    d = data(15)
    decision = no_purchase(d)
    before = candidate_plan(d, decision, [], [])
    payload = d.to_dict()
    payload["emergency_price"] = {w: 999 for w in d.base.scenarios}
    after = candidate_plan(OptionData.from_dict(payload), decision, [], [])
    assert before == after
    assert before["ranking"][0] == "b_buffered"


@pytest.mark.gurobi
@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_three_way_correctness(case):
    d = OptionData.from_dict(case["data"])
    ef, zero, one = solve_extensive_form(d), solve_a0(d), a1.solve_a1(d)
    checks = verify_three(d, ef, zero, one)
    assert checks["status"] == "PASS" and checks["full_omega_feasible"]
    if "expected_objective" in case: assert one["objective"] == pytest.approx(case["expected_objective"])
    if "expected_memory_hits" in case: assert one["phase_i_hits"] == case["expected_memory_hits"]
    if "expected_phase_iii_calls" in case: assert one["phase_iii_calls"] == case["expected_phase_iii_calls"]
    if "expected_worst" in case: assert one["incumbent"]["oracle"]["worst_scenario"] == case["expected_worst"]


@pytest.mark.gurobi
def test_memory_hit_skips_later_phases_and_preserves_exact_ub():
    result = a1.solve_a1(data(15))
    assert result["status"] == "certified"
    initial, hit, final = result["trace"]
    assert initial["phase_i"]["hit"] is False and initial["phase_ii"]["hit"] is False
    assert initial["scenario_source"] == "EXACT" and initial["candidate_UB"] == 121
    assert hit["phase_i"]["hit"] is True and hit["added_scenario"] == "d_second_needed"
    assert hit["phase_ii"] is hit["phase_iii"] is None and hit["phase_iii_called"] is False
    assert hit["candidate_UB"] is None and hit["UB"] == initial["UB"]
    assert hit["certified"] is False and hit["convergence"] is False
    assert final["certified"] is True and final["phase_iii_called"] is True
    assert final["phase_ii"]["pool"] == []
    verify_a1(data(15), result)


@pytest.mark.gurobi
def test_candidate_hit_is_not_ub_and_empty_pool_requires_certification():
    result = a1.solve_a1(data())
    first = result["trace"][0]
    assert not first["phase_i"]["hit"] and first["phase_ii"]["hit"]
    assert first["phase_iii"] is None
    assert first["UB"] is first["candidate_UB"] is first["gap"] is None
    assert first["certified"] is False
    assert result["phase_ii_hits"] == 2
    assert result["trace"][-1]["phase_ii"]["pool"] == []
    assert result["trace"][-1]["phase_iii_called"] and result["certified"]


@pytest.mark.gurobi
def test_iteration_limit_after_candidate_hit_is_failure():
    result = a1.solve_a1(data(), max_iterations=1)
    assert result["status"] == "iteration_limit" and not result["certified"]
    assert result["objective"] is result["UB"] is None
    assert result["phase_ii_hits"] == 1 and result["phase_iii_calls"] == 0


@pytest.mark.parametrize("limit", [0, -1, 1.2, True])
def test_iteration_limit_domain(limit):
    with pytest.raises(ValueError): a1.solve_a1(data(), max_iterations=limit)


@pytest.mark.parametrize("status", ["solver_error", "infeasible", "unbounded", "time_limit", "iteration_limit", "locally_optimal", "unknown", "numerical_failure"])
def test_master_failure_no_certification(monkeypatch, status):
    monkeypatch.setattr(a1, "audit", lambda *args, **kwargs: {"synthetic_negative_test": True})
    monkeypatch.setattr(a1, "solve_exact", lambda model: {"status": status})
    result = a1.solve_a1(data())
    assert result["status"] == status and not result["certified"]
    assert result["objective"] is result["UB"] is None and result["phase_iii_calls"] == 0


@pytest.mark.gurobi
@pytest.mark.parametrize("failure", ["candidate", "memory", "exact", "partial_exact", "duplicate_selected"])
def test_phase_failures_do_not_certify(monkeypatch, failure):
    if failure in ("candidate", "memory"):
        actual = a1.evaluate_scenario
        def evaluate(d, decision, w):
            if failure == "candidate" or w == "d_second_needed":
                return {"scenario": w, "status": "time_limit"}
            return actual(d, decision, w)
        monkeypatch.setattr(a1, "evaluate_scenario", evaluate)
    if failure == "exact":
        monkeypatch.setattr(a1, "exact_oracle", lambda *args: {"status": "oracle_failure", "cause": "solver_error", "scenarios": []})
    if failure == "partial_exact":
        actual = a1.exact_oracle
        def partial(*args):
            proof = actual(*args)
            proof["scenarios"].pop()
            return proof
        monkeypatch.setattr(a1, "exact_oracle", partial)
    if failure == "duplicate_selected":
        actual = a1.inspect
        def duplicate(d, decision, eta, planned):
            phase = actual(d, decision, eta, planned)
            if planned:
                w = min(d.base.scenarios)
                evaluated = a1.evaluate_scenario(d, decision, w)
                phase.update(selected=w, hit=True, evaluations=[evaluated])
            return phase
        monkeypatch.setattr(a1, "inspect", duplicate)
    result = a1.solve_a1(data(15) if failure == "memory" else data(0) if failure in ("exact", "partial_exact") else data())
    assert result["status"] == ("convergence_failure" if failure == "duplicate_selected" else "oracle_failure")
    assert not result["certified"] and result["objective"] is None


def without_time(value):
    if isinstance(value, dict): return {k: without_time(v) for k, v in value.items() if k != "runtime_seconds"}
    if isinstance(value, list): return [without_time(v) for v in value]
    return value


@pytest.mark.gurobi
def test_fresh_memory_and_deterministic_trace_replay():
    first, second = a1.solve_a1(data(15)), a1.solve_a1(data(15))
    assert first["trace"][0]["memory_before"] == second["trace"][0]["memory_before"] == []
    assert without_time(first["trace"]) == without_time(second["trace"])
    verify_a1(data(15), first)
    verify_a1(data(15), second)


@pytest.mark.gurobi
def test_three_algorithms_share_one_real_preflight(monkeypatch):
    from robust_budget_allocation.runtime import environment
    calls = []
    actual = environment.run_preflight
    def counted():
        calls.append(1)
        return actual()
    monkeypatch.setattr(environment, "_PREFLIGHT_REPORT", None)
    monkeypatch.setattr(environment, "run_preflight", counted)
    d = data(0)
    verify_three(d, solve_extensive_form(d), solve_a0(d), a1.solve_a1(d))
    assert calls == [1]
