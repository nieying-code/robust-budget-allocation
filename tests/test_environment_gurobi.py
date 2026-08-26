import pytest

from robust_budget_allocation.environment import run_preflight


@pytest.mark.gurobi
def test_locked_environment_and_license() -> None:
    assert run_preflight().status == "PASS"
