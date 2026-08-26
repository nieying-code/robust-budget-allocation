import pytest
from pyomo.opt import SolverStatus, TerminationCondition

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
    ("termination", "expected"),
    [
        (TerminationCondition.optimal, "optimal"),
        (TerminationCondition.infeasible, "infeasible"),
        (TerminationCondition.unbounded, "unbounded"),
        (TerminationCondition.maxTimeLimit, "time_limit"),
        (TerminationCondition.unknown, "unknown"),
    ],
)
def test_termination_normalization(termination: object, expected: str) -> None:
    assert normalize_termination(SolverStatus.ok, termination) == expected


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
