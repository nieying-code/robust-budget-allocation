"""Gurobi-only solver construction and generic status normalization."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any

from pyomo.opt import SolverStatus, TerminationCondition

from .environment import LOCKED_RUNTIME, run_preflight


@dataclass(frozen=True)
class SolverConfiguration:
    interface: str = "gurobi_direct"
    threads: int = 1
    time_limit_seconds: float | None = None
    feasibility_tolerance: float | None = None
    optimality_tolerance: float | None = None


@dataclass(frozen=True)
class SolveOutcome:
    status: str
    solver: str
    runtime_seconds: float
    termination_condition: str
    message: str | None = None


def validate_solver_configuration(config: SolverConfiguration) -> None:
    if config.interface != LOCKED_RUNTIME.solver_interface:
        raise ValueError(
            f"solver interface must be {LOCKED_RUNTIME.solver_interface!r}; "
            f"got {config.interface!r}"
        )
    if config.threads != LOCKED_RUNTIME.threads:
        raise ValueError(f"Gurobi Threads must equal {LOCKED_RUNTIME.threads}")
    if config.time_limit_seconds is not None and config.time_limit_seconds <= 0:
        raise ValueError("time_limit_seconds must be positive")
    for name, value in (
        ("feasibility_tolerance", config.feasibility_tolerance),
        ("optimality_tolerance", config.optimality_tolerance),
    ):
        if value is not None and value <= 0:
            raise ValueError(f"{name} must be positive")


def normalize_termination(solver_status: Any, termination: Any) -> str:
    if termination in {
        TerminationCondition.optimal,
        TerminationCondition.globallyOptimal,
        TerminationCondition.locallyOptimal,
    }:
        return "optimal"
    if termination == TerminationCondition.infeasible:
        return "infeasible"
    if termination == TerminationCondition.unbounded:
        return "unbounded"
    if termination == TerminationCondition.infeasibleOrUnbounded:
        return "infeasible_or_unbounded"
    if termination in {
        TerminationCondition.maxTimeLimit,
        TerminationCondition.maxIterations,
    }:
        return "time_limit"
    if solver_status == SolverStatus.error:
        return "solver_error"
    return "unknown"


def create_solver(config: SolverConfiguration = SolverConfiguration()) -> Any:
    validate_solver_configuration(config)
    run_preflight()
    from pyomo.environ import SolverFactory

    solver = SolverFactory(config.interface)
    if solver is None or not solver.available(exception_flag=False):
        raise RuntimeError(f"solver interface {config.interface!r} is unavailable")
    solver.options["Threads"] = config.threads
    if config.time_limit_seconds is not None:
        solver.options["TimeLimit"] = float(config.time_limit_seconds)
    if config.feasibility_tolerance is not None:
        solver.options["FeasibilityTol"] = float(config.feasibility_tolerance)
    if config.optimality_tolerance is not None:
        solver.options["OptimalityTol"] = float(config.optimality_tolerance)
    return solver


def solve_model(
    model: Any,
    *,
    config: SolverConfiguration = SolverConfiguration(),
    tee: bool = False,
) -> SolveOutcome:
    """Solve a generic Pyomo model without masking failures or falling back."""

    # Configuration, version, interface, and license errors are preflight gates,
    # not solve outcomes.  They must stop execution immediately.
    solver = create_solver(config)
    started = perf_counter()
    try:
        result = solver.solve(model, tee=tee, load_solutions=False)
        termination = result.solver.termination_condition
        status = normalize_termination(result.solver.status, termination)
        if status == "optimal":
            model.solutions.load_from(result)
        return SolveOutcome(
            status=status,
            solver=config.interface,
            runtime_seconds=perf_counter() - started,
            termination_condition=str(termination),
        )
    except Exception as exc:
        return SolveOutcome(
            status="solver_error",
            solver=config.interface,
            runtime_seconds=perf_counter() - started,
            termination_condition=type(exc).__name__,
            message=str(exc),
        )
