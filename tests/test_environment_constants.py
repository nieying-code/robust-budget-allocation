from robust_budget_allocation.environment import (
    EXPECTED_GUROBI,
    EXPECTED_GUROBIPY,
    EXPECTED_INTERFACE,
    EXPECTED_PYOMO,
    EXPECTED_PYTHON,
    EXPECTED_THREADS,
)


def test_locked_environment_constants() -> None:
    assert EXPECTED_PYTHON == (3, 12, 10)
    assert EXPECTED_PYOMO == "6.10.1"
    assert EXPECTED_GUROBIPY == "13.0.2"
    assert EXPECTED_GUROBI == (13, 0, 2)
    assert EXPECTED_INTERFACE == "gurobi_direct"
    assert EXPECTED_THREADS == 1
