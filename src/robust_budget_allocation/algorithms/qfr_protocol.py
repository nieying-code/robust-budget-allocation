"""Frozen numerical, identity, and solver rules for R3 Q-F-R v2 correctness."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from pathlib import Path
from time import perf_counter
from typing import Any, Mapping

import pyomo.environ as pyo
from pyomo.opt import SolverStatus, TerminationCondition

from robust_budget_allocation.data.qfr_data import QFRData
from robust_budget_allocation.io.hashing import canonical_json_sha256, sha256_file
from robust_budget_allocation.runtime.environment import ensure_preflight_once


PROTOCOL_RELATIVE_PATH = Path("docs/R3_CORRECTNESS_PROTOCOL_v2.md")
PROTOCOL_SHA256 = "cd0e02603cd307876b3270e2c694127541394211d7034325dabdee2f28b7bf0b"
PROTOCOL_FREEZE_COMMIT = "c29a67c1369f44c4afb424c0ba2a8b0d43a0b923"
PROTOCOL_FREEZE_TREE = "ba4c8d3855b6f027509a5bbd85af88d7bb48f9b5"
R2_MODEL_BASE_COMMIT = "d5484adff21040bdaa0aaa3e727c9d341b342e47"
R2_MODEL_BASE_TREE = "30d3e0ed261b794de8420bd9bd1c0d9873ee4e29"

R3_REQUIRED_SOURCE_PATHS = (
    "docs/R3_CORRECTNESS_PROTOCOL_v2.md",
    "tests/fixtures/r3_correctness_v2.json",
    "src/robust_budget_allocation/data/qfr_data.py",
    "src/robust_budget_allocation/models/qfr_common.py",
    "src/robust_budget_allocation/models/qfr_m0.py",
    "src/robust_budget_allocation/models/qfr_m1.py",
    "src/robust_budget_allocation/models/qfr_m2.py",
    "src/robust_budget_allocation/models/qfr_support.py",
    "src/robust_budget_allocation/algorithms/qfr_protocol.py",
    "src/robust_budget_allocation/algorithms/qfr_state.py",
    "src/robust_budget_allocation/algorithms/qfr_builders.py",
    "src/robust_budget_allocation/algorithms/qfr_exact_oracle.py",
    "src/robust_budget_allocation/algorithms/qfr_accounting.py",
    "src/robust_budget_allocation/algorithms/qfr_extensive_form.py",
    "src/robust_budget_allocation/algorithms/qfr_standard_ccg.py",
    "src/robust_budget_allocation/algorithms/qfr_verification.py",
    "src/robust_budget_allocation/algorithms/qfr_correctness_suite.py",
    "src/robust_budget_allocation/io/hashing.py",
    "src/robust_budget_allocation/reproducibility/git_state.py",
    "src/robust_budget_allocation/runtime/environment.py",
    "scripts/r3_ef_a0_correctness.py",
)

ABSOLUTE_TOLERANCE = 1e-7
RELATIVE_TOLERANCE = 1e-9
SOLVER_OPTIONS: dict[str, int | float] = {
    "Threads": 1,
    "MIPGap": 0,
    "MIPGapAbs": 0,
    "FeasibilityTol": 1e-9,
    "OptimalityTol": 1e-9,
    "IntFeasTol": 1e-9,
}
ACCEPTED_TERMINATIONS = frozenset(
    {TerminationCondition.optimal, TerminationCondition.globallyOptimal}
)


def tolerance(a: float, b: float) -> float:
    """Return the user-frozen R3 v2 numerical comparison threshold."""

    left, right = float(a), float(b)
    if not math.isfinite(left) or not math.isfinite(right):
        raise ValueError("R3 numerical comparison requires finite values")
    return ABSOLUTE_TOLERANCE + RELATIVE_TOLERANCE * max(
        1.0, abs(left), abs(right)
    )


def close(a: float, b: float) -> bool:
    return abs(float(a) - float(b)) <= tolerance(float(a), float(b))


def require_close(a: float, b: float, label: str) -> None:
    if not close(a, b):
        raise ValueError(f"{label} differs beyond frozen R3 tolerance: {a!r} != {b!r}")


def canonical_scenarios(data: QFRData) -> tuple[str, ...]:
    data.validate()
    return tuple(sorted(data.scenarios))


def static_data_payload(data: QFRData) -> dict[str, Any]:
    payload = data.to_dict()
    return {
        key: value
        for key, value in payload.items()
        if key not in {"scenarios", "demand", "q_availability", "disruption"}
    }


def static_data_sha256(data: QFRData) -> str:
    return canonical_json_sha256(static_data_payload(data))


def scenario_identity(data: QFRData, scenario: str) -> str:
    if scenario not in data.scenarios:
        raise ValueError(f"unknown scenario: {scenario!r}")
    payload = {
            "schema_version": data.schema_version,
            "model_family": "heterogeneous_material_qfr",
            "static_data_sha256": static_data_sha256(data),
            "ordered_items": list(data.items),
            "demand": dict(data.demand[scenario]),
            **(
                {"q_availability": dict(data.q_availability[scenario])}
                if data.schema_version == 3
                else {}
            ),
            "disruption": dict(data.disruption[scenario]),
        }
    return canonical_json_sha256(payload)


def scenario_identities(data: QFRData) -> dict[str, str]:
    return {scenario: scenario_identity(data, scenario) for scenario in data.scenarios}


def subset_data(data: QFRData, scenarios: tuple[str, ...] | list[str]) -> QFRData:
    """Create a deterministic restricted-master input without changing static science."""

    selected = tuple(scenarios)
    if not selected or len(set(selected)) != len(selected):
        raise ValueError("scenario subset must be nonempty and unique")
    if any(value not in data.scenarios for value in selected):
        raise ValueError("scenario subset contains an unknown ID")
    payload = data.to_dict()
    payload["scenarios"] = list(selected)
    payload["demand"] = {value: dict(data.demand[value]) for value in selected}
    if data.schema_version == 3:
        payload["q_availability"] = {
            value: dict(data.q_availability[value]) for value in selected
        }
    payload["disruption"] = {value: dict(data.disruption[value]) for value in selected}
    result = QFRData.from_dict(payload)
    if static_data_sha256(result) != static_data_sha256(data):
        raise ValueError("restricted data changed static Q-F-R scientific identity")
    return result


def protocol_identity(repo_root: Path) -> dict[str, str]:
    path = repo_root.resolve() / PROTOCOL_RELATIVE_PATH
    actual = sha256_file(path)
    if actual != PROTOCOL_SHA256:
        raise RuntimeError("R3 v2 correctness protocol hash mismatch")
    return {
        "path": PROTOCOL_RELATIVE_PATH.as_posix(),
        "sha256": actual,
        "freeze_commit": PROTOCOL_FREEZE_COMMIT,
        "freeze_tree": PROTOCOL_FREEZE_TREE,
        "authority": "EXPLICITLY_RE_REGISTERED_FOR_R3_V2_CORRECTNESS",
    }


def solver_configuration_identity() -> dict[str, Any]:
    """Return the complete frozen solver policy embedded in R3 evidence."""

    payload: dict[str, Any] = {
        "solver_interface": "gurobi_direct",
        "threads": 1,
        "no_fallback": True,
        "options": dict(SOLVER_OPTIONS),
        "accepted_solver_status": ["ok"],
        "accepted_terminations": ["globallyOptimal", "optimal"],
    }
    payload["configuration_sha256"] = canonical_json_sha256(payload)
    return payload


def r2_model_identity() -> dict[str, Any]:
    return {
        "merge_commit": R2_MODEL_BASE_COMMIT,
        "merge_tree": R2_MODEL_BASE_TREE,
        "scientific_source_paths": [
            path
            for path in R3_REQUIRED_SOURCE_PATHS
            if path.startswith("src/robust_budget_allocation/data/qfr_")
            or path.startswith("src/robust_budget_allocation/models/qfr_")
        ],
    }


@dataclass(frozen=True)
class ExactSolveOutcome:
    status: str
    solver_status: str
    termination: str
    objective: float | None
    lower_bound: float | None
    runtime_seconds: float
    solver_interface: str = "gurobi_direct"
    message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def accepted_outcome(outcome: Mapping[str, Any]) -> None:
    required = {
        "status",
        "solver_status",
        "termination",
        "objective",
        "lower_bound",
        "runtime_seconds",
        "solver_interface",
        "message",
    }
    if set(outcome) != required:
        raise ValueError("solver outcome fields are incomplete or unexpected")
    if (
        outcome["status"] != "optimal"
        or outcome["solver_status"] != "ok"
        or outcome["termination"] not in {"optimal", "globallyOptimal"}
        or outcome["solver_interface"] != "gurobi_direct"
    ):
        raise ValueError("solver outcome is not an accepted exact R3 optimum")
    objective = float(outcome["objective"])
    lower_bound = float(outcome["lower_bound"])
    require_close(objective, lower_bound, "solver primal/lower bound")
    runtime = float(outcome["runtime_seconds"])
    if not math.isfinite(runtime) or runtime < 0:
        raise ValueError("solver runtime must be finite and nonnegative")


def solve_exact(model: pyo.ConcreteModel, *, tee: bool = False) -> ExactSolveOutcome:
    """Solve using the user-frozen R3 Gurobi configuration and fail closed."""

    ensure_preflight_once()
    solver = pyo.SolverFactory("gurobi_direct")
    if solver is None or not solver.available(exception_flag=False):
        raise RuntimeError("solver interface 'gurobi_direct' is unavailable")
    for name, value in SOLVER_OPTIONS.items():
        solver.options[name] = value
    started = perf_counter()
    try:
        result = solver.solve(model, tee=tee, load_solutions=False)
        solver_status = result.solver.status
        termination = result.solver.termination_condition
        accepted = solver_status == SolverStatus.ok and termination in ACCEPTED_TERMINATIONS
        if accepted:
            model.solutions.load_from(result)
            objective = float(pyo.value(model.total_cost))
            lower_bound = float(result.problem.lower_bound)
            if not math.isfinite(objective) or not math.isfinite(lower_bound):
                accepted = False
        else:
            objective = None
            lower_bound = None
        outcome = ExactSolveOutcome(
            status="optimal" if accepted else "failed",
            solver_status=str(solver_status),
            termination=str(termination),
            objective=objective,
            lower_bound=lower_bound,
            runtime_seconds=perf_counter() - started,
        )
        if accepted:
            accepted_outcome(outcome.to_dict())
        return outcome
    except Exception as exc:
        return ExactSolveOutcome(
            status="solver_error",
            solver_status="error",
            termination=type(exc).__name__,
            objective=None,
            lower_bound=None,
            runtime_seconds=perf_counter() - started,
            message=str(exc),
        )
