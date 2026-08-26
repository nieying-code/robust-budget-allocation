"""Compatibility imports for the generic runtime environment module."""

from .runtime.environment import (  # noqa: F401
    EnvironmentFacts,
    EnvironmentPreflightError,
    EnvironmentReport,
    LOCKED_RUNTIME,
    RuntimeRequirements,
    detect_environment_facts,
    ensure_preflight_once,
    run_preflight,
    validate_environment_facts,
)

EXPECTED_PYTHON = LOCKED_RUNTIME.python
EXPECTED_PYOMO = LOCKED_RUNTIME.pyomo
EXPECTED_GUROBIPY = LOCKED_RUNTIME.gurobipy
EXPECTED_GUROBI = LOCKED_RUNTIME.gurobi_optimizer
EXPECTED_INTERFACE = LOCKED_RUNTIME.solver_interface
EXPECTED_THREADS = LOCKED_RUNTIME.threads
