import pytest
from pyomo.opt import SolverStatus, TerminationCondition

from robust_budget_allocation.runtime import environment as environment_runtime
from robust_budget_allocation.runtime import solver as solver_runtime
from robust_budget_allocation.runtime.solver import (
    SolverConfiguration,
    normalize_termination,
    solve_model,
    validate_solver_configuration,
)


def test_solver_interface_mismatch_is_rejected() -> None:
    with pytest.raises(ValueError, match="solver interface"):
        validate_solver_configuration(SolverConfiguration(interface="highs"))


def test_threads_must_equal_one() -> None:
    with pytest.raises(ValueError, match="Threads"):
        validate_solver_configuration(SolverConfiguration(threads=2))


@pytest.mark.parametrize(
    ("solver_status", "termination", "expected"),
    [
        (SolverStatus.ok, TerminationCondition.optimal, "optimal"),
        (SolverStatus.ok, TerminationCondition.globallyOptimal, "optimal"),
        (SolverStatus.ok, TerminationCondition.locallyOptimal, "locally_optimal"),
        (SolverStatus.error, TerminationCondition.optimal, "solver_error"),
        (SolverStatus.ok, TerminationCondition.maxIterations, "iteration_limit"),
        (SolverStatus.ok, TerminationCondition.maxTimeLimit, "time_limit"),
        (SolverStatus.ok, TerminationCondition.unknown, "unknown"),
        ("invalid-status", TerminationCondition.optimal, "invalid_solver_status"),
    ],
)
def test_termination_normalization(
    solver_status: object,
    termination: object,
    expected: str,
) -> None:
    assert normalize_termination(solver_status, termination) == expected


def test_repeated_solve_model_runs_preflight_once(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeSolutions:
        def load_from(self, _result: object) -> None:
            pass

    class FakeModel:
        solutions = FakeSolutions()

    class FakeSolver:
        def __init__(self) -> None:
            self.options: dict[str, object] = {}

        def available(self, *, exception_flag: bool) -> bool:
            assert not exception_flag
            return True

        def solve(self, _model: object, **_kwargs: object) -> object:
            solver = type(
                "SolverRecord",
                (),
                {
                    "status": SolverStatus.ok,
                    "termination_condition": TerminationCondition.optimal,
                },
            )()
            return type("Result", (), {"solver": solver})()

    calls = 0

    def fake_preflight() -> object:
        nonlocal calls
        calls += 1
        return object()

    environment_runtime._reset_preflight_cache_for_tests()
    monkeypatch.setattr(environment_runtime, "run_preflight", fake_preflight)
    monkeypatch.setattr("pyomo.environ.SolverFactory", lambda _interface: FakeSolver())
    try:
        assert solver_runtime.solve_model(FakeModel()).status == "optimal"
        assert solver_runtime.solve_model(FakeModel()).status == "optimal"
        assert calls == 1
    finally:
        environment_runtime._reset_preflight_cache_for_tests()


@pytest.mark.gurobi
def test_real_gurobi_direct_solve() -> None:
    from pyomo.environ import ConcreteModel, Objective, Var, minimize, value

    model = ConcreteModel()
    model.x = Var(bounds=(2, None))
    model.objective = Objective(expr=model.x, sense=minimize)
    outcome = solve_model(model)
    assert outcome.status == "optimal"
    assert outcome.solver == "gurobi_direct"
    assert value(model.x) == pytest.approx(2.0)
