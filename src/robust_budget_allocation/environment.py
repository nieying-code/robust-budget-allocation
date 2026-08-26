"""Fail-fast validation for the locked research environment."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import platform
import sys

EXPECTED_PYTHON = (3, 12, 10)
EXPECTED_PYOMO = "6.10.1"
EXPECTED_GUROBIPY = "13.0.2"
EXPECTED_GUROBI = (13, 0, 2)
EXPECTED_INTERFACE = "gurobi_direct"
EXPECTED_THREADS = 1


class EnvironmentPreflightError(RuntimeError):
    """Raised when the locked solver environment is unavailable or mismatched."""


@dataclass(frozen=True)
class EnvironmentReport:
    python: str
    pyomo: str
    gurobipy: str
    gurobi_optimizer: str
    solver_interface: str
    threads: int
    license_available: bool
    platform: str
    status: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _version_string(parts: tuple[int, ...]) -> str:
    return ".".join(str(part) for part in parts)


def run_preflight() -> EnvironmentReport:
    errors: list[str] = []
    actual_python = sys.version_info[:3]
    if actual_python != EXPECTED_PYTHON:
        errors.append(
            f"Python must be {_version_string(EXPECTED_PYTHON)}, got {_version_string(actual_python)}"
        )

    try:
        import pyomo
        from pyomo.environ import ConcreteModel, Objective, SolverFactory, Var, minimize
    except Exception as exc:  # pragma: no cover - exercised in an unprovisioned environment
        raise EnvironmentPreflightError(f"Pyomo import failed: {exc}") from exc

    if pyomo.__version__ != EXPECTED_PYOMO:
        errors.append(f"Pyomo must be {EXPECTED_PYOMO}, got {pyomo.__version__}")

    try:
        import gurobipy as gp
    except Exception as exc:  # pragma: no cover
        raise EnvironmentPreflightError(f"gurobipy import failed: {exc}") from exc

    gp_version = getattr(gp, "__version__", "unknown")
    optimizer_version = tuple(gp.gurobi.version())
    if gp_version != EXPECTED_GUROBIPY:
        errors.append(f"gurobipy must be {EXPECTED_GUROBIPY}, got {gp_version}")
    if optimizer_version != EXPECTED_GUROBI:
        errors.append(
            f"Gurobi Optimizer must be {_version_string(EXPECTED_GUROBI)}, "
            f"got {_version_string(optimizer_version)}"
        )

    solver = SolverFactory(EXPECTED_INTERFACE)
    if solver is None or not solver.available(exception_flag=False):
        errors.append(f"Pyomo solver interface {EXPECTED_INTERFACE!r} is unavailable")
    else:
        solver.options["Threads"] = EXPECTED_THREADS
        if solver.options.get("Threads") != EXPECTED_THREADS:
            errors.append("Gurobi Threads must equal 1")

    if errors:
        raise EnvironmentPreflightError("; ".join(errors))

    license_available = False
    try:
        model = ConcreteModel()
        model.x = Var(bounds=(0, None))
        model.objective = Objective(expr=model.x, sense=minimize)
        result = solver.solve(model, tee=False)
        termination = str(result.solver.termination_condition).lower()
        license_available = termination == "optimal"
        if not license_available:
            raise EnvironmentPreflightError(
                f"Gurobi license/solve check did not return optimal: {termination}"
            )
    except EnvironmentPreflightError:
        raise
    except Exception as exc:
        raise EnvironmentPreflightError(f"Gurobi license/solve check failed: {exc}") from exc

    return EnvironmentReport(
        python=_version_string(actual_python),
        pyomo=pyomo.__version__,
        gurobipy=gp_version,
        gurobi_optimizer=_version_string(optimizer_version),
        solver_interface=EXPECTED_INTERFACE,
        threads=EXPECTED_THREADS,
        license_available=license_available,
        platform=platform.platform(),
        status="PASS",
    )
