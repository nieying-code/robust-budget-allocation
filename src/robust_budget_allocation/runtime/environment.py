"""Fail-fast validation for the locked new-project runtime.

Selected validation structure was adapted from the frozen legacy environment
and solver-runtime checks. Phase-specific names, hardware gates, legacy lock
files, and all scientific assumptions were removed.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from importlib import metadata
import platform
import sys
from threading import Lock


@dataclass(frozen=True)
class RuntimeRequirements:
    python: tuple[int, int, int] = (3, 12, 10)
    python_implementation: str = "CPython"
    pyomo: str = "6.10.1"
    gurobipy: str = "13.0.2"
    gurobi_optimizer: tuple[int, int, int] = (13, 0, 2)
    solver_interface: str = "gurobi_direct"
    threads: int = 1


LOCKED_RUNTIME = RuntimeRequirements()


@dataclass(frozen=True)
class EnvironmentFacts:
    python: tuple[int, int, int]
    python_implementation: str
    pyomo: str
    gurobipy: str
    gurobi_optimizer: tuple[int, ...]
    solver_interface: str
    threads: int
    solver_available: bool
    license_available: bool
    platform: str
    license_error: str | None = None


@dataclass(frozen=True)
class EnvironmentReport:
    python: str
    python_implementation: str
    pyomo: str
    gurobipy: str
    gurobi_optimizer: str
    solver_interface: str
    threads: int
    solver_available: bool
    license_available: bool
    platform: str
    status: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class EnvironmentPreflightError(RuntimeError):
    """The runtime does not match the locked, licensed environment."""


_PREFLIGHT_LOCK = Lock()
_PREFLIGHT_REPORT: EnvironmentReport | None = None


def _dotted(parts: tuple[int, ...]) -> str:
    return ".".join(str(value) for value in parts)


def validate_environment_facts(
    facts: EnvironmentFacts,
    requirements: RuntimeRequirements = LOCKED_RUNTIME,
) -> None:
    """Validate supplied facts, enabling solver-free mismatch tests."""

    errors: list[str] = []
    checks = (
        (facts.python, requirements.python, "Python"),
        (
            facts.python_implementation,
            requirements.python_implementation,
            "Python implementation",
        ),
        (facts.pyomo, requirements.pyomo, "Pyomo"),
        (facts.gurobipy, requirements.gurobipy, "gurobipy"),
        (
            facts.gurobi_optimizer,
            requirements.gurobi_optimizer,
            "Gurobi Optimizer",
        ),
        (facts.solver_interface, requirements.solver_interface, "solver interface"),
        (facts.threads, requirements.threads, "Gurobi Threads"),
    )
    for actual, expected, name in checks:
        if actual != expected:
            errors.append(f"{name} must be {expected!r}, got {actual!r}")
    if not facts.solver_available:
        errors.append(f"solver interface {requirements.solver_interface!r} is unavailable")
    if not facts.license_available:
        detail = f": {facts.license_error}" if facts.license_error else ""
        errors.append(f"Gurobi license is unavailable{detail}")
    if errors:
        raise EnvironmentPreflightError("; ".join(errors))


def detect_environment_facts(
    *,
    solver_interface: str = "gurobi_direct",
    threads: int = 1,
) -> EnvironmentFacts:
    """Inspect versions and perform a real licensed solve."""

    try:
        import gurobipy as gp
        import pyomo
        from pyomo.environ import ConcreteModel, Objective, SolverFactory, Var, minimize
    except Exception as exc:  # pragma: no cover - depends on host provisioning
        raise EnvironmentPreflightError(f"runtime import failed: {exc}") from exc

    try:
        gp_version = metadata.version("gurobipy")
    except metadata.PackageNotFoundError:
        gp_version = "not-installed"

    solver = SolverFactory(solver_interface)
    available = bool(solver is not None and solver.available(exception_flag=False))
    license_available = False
    license_error: str | None = None
    if available:
        try:
            solver.options["Threads"] = threads
            model = ConcreteModel()
            model.x = Var(bounds=(0, None))
            model.objective = Objective(expr=model.x, sense=minimize)
            result = solver.solve(model, tee=False)
            license_available = str(result.solver.termination_condition).lower() == "optimal"
            if not license_available:
                license_error = str(result.solver.termination_condition)
        except Exception as exc:  # pragma: no cover - license-host dependent
            license_error = f"{type(exc).__name__}: {exc}"

    return EnvironmentFacts(
        python=tuple(sys.version_info[:3]),
        python_implementation=platform.python_implementation(),
        pyomo=pyomo.__version__,
        gurobipy=gp_version,
        gurobi_optimizer=tuple(int(value) for value in gp.gurobi.version()),
        solver_interface=solver_interface,
        threads=threads,
        solver_available=available,
        license_available=license_available,
        license_error=license_error,
        platform=platform.platform(),
    )


def run_preflight() -> EnvironmentReport:
    facts = detect_environment_facts(
        solver_interface=LOCKED_RUNTIME.solver_interface,
        threads=LOCKED_RUNTIME.threads,
    )
    validate_environment_facts(facts)
    return EnvironmentReport(
        python=_dotted(facts.python),
        python_implementation=facts.python_implementation,
        pyomo=facts.pyomo,
        gurobipy=facts.gurobipy,
        gurobi_optimizer=_dotted(facts.gurobi_optimizer),
        solver_interface=facts.solver_interface,
        threads=facts.threads,
        solver_available=facts.solver_available,
        license_available=facts.license_available,
        platform=facts.platform,
        status="PASS",
    )


def ensure_preflight_once() -> EnvironmentReport:
    """Run the licensed preflight at most once after a successful process start."""

    global _PREFLIGHT_REPORT
    if _PREFLIGHT_REPORT is None:
        with _PREFLIGHT_LOCK:
            if _PREFLIGHT_REPORT is None:
                _PREFLIGHT_REPORT = run_preflight()
    return _PREFLIGHT_REPORT


def _reset_preflight_cache_for_tests() -> None:
    global _PREFLIGHT_REPORT
    with _PREFLIGHT_LOCK:
        _PREFLIGHT_REPORT = None
