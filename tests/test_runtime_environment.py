from dataclasses import replace

import pytest

from robust_budget_allocation.runtime.environment import (
    EnvironmentFacts,
    EnvironmentPreflightError,
    LOCKED_RUNTIME,
    validate_environment_facts,
)


@pytest.fixture
def valid_facts() -> EnvironmentFacts:
    return EnvironmentFacts(
        python=LOCKED_RUNTIME.python,
        python_implementation=LOCKED_RUNTIME.python_implementation,
        pyomo=LOCKED_RUNTIME.pyomo,
        gurobipy=LOCKED_RUNTIME.gurobipy,
        gurobi_optimizer=LOCKED_RUNTIME.gurobi_optimizer,
        solver_interface=LOCKED_RUNTIME.solver_interface,
        threads=LOCKED_RUNTIME.threads,
        solver_available=True,
        license_available=True,
        platform="test-platform",
    )


def test_correct_runtime_facts_pass(valid_facts: EnvironmentFacts) -> None:
    validate_environment_facts(valid_facts)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("python", (3, 12, 9), "Python"),
        ("pyomo", "0.0.0", "Pyomo"),
        ("gurobipy", "0.0.0", "gurobipy"),
        ("gurobi_optimizer", (0, 0, 0), "Gurobi Optimizer"),
        ("solver_interface", "highs", "solver interface"),
        ("threads", 2, "Threads"),
        ("license_available", False, "license"),
    ],
)
def test_runtime_mismatch_fails_fast(
    valid_facts: EnvironmentFacts,
    field: str,
    value: object,
    message: str,
) -> None:
    with pytest.raises(EnvironmentPreflightError, match=message):
        validate_environment_facts(replace(valid_facts, **{field: value}))
