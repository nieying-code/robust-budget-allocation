"""Extensive-form benchmark for all heterogeneous-material Q-F-R v2 models."""

from __future__ import annotations

from time import perf_counter
from typing import Any, Mapping

import pyomo.environ as pyo

from robust_budget_allocation.data.qfr_data import QFRData
from robust_budget_allocation.io.hashing import canonical_json_sha256
from robust_budget_allocation.models.qfr_support import validate_qfr_solution
from .qfr_accounting import validate_accounting_payload
from .qfr_builders import build_qfr_extensive_form
from .qfr_exact_oracle import exact_oracle, validate_oracle
from .qfr_protocol import accepted_outcome, require_close, solve_exact
from .qfr_state import QFRFirstStage, extract_first_stage, first_stage_cost, validate_first_stage


def solve_qfr_extensive_form(data: QFRData, model_kind: str) -> dict[str, Any]:
    """Solve the complete finite-scenario R2 model and independently certify recourse."""

    data.validate()
    started = perf_counter()
    model = build_qfr_extensive_form(data, model_kind)
    outcome = solve_exact(model)
    result: dict[str, Any] = {
        "schema_version": 1,
        "method": "R3_V2_EF",
        "model_kind": model_kind,
        "status": "failed",
        "data_sha256": data.data_sha256,
        "scenario_sha256": data.scenario_sha256,
        "solver": outcome.to_dict(),
        "objective": None,
        "solver_bound": None,
        "first_stage": None,
        "first_stage_sha256": None,
        "accounting": None,
        "oracle": None,
        "runtime_seconds": None,
    }
    if outcome.status != "optimal":
        result["runtime_seconds"] = perf_counter() - started
        result["result_sha256"] = canonical_json_sha256(result)
        return result
    accounting = validate_qfr_solution(data, model, tolerance=1e-7)
    decision = extract_first_stage(data, model)
    theta = float(pyo.value(model.theta))
    oracle = exact_oracle(data, decision, theta)
    if oracle["status"] != "complete":
        result["runtime_seconds"] = perf_counter() - started
        result["first_stage"] = decision.to_dict()
        result["first_stage_sha256"] = decision.sha256
        result["accounting"] = accounting.to_dict()
        result["oracle"] = oracle
        result["result_sha256"] = canonical_json_sha256(result)
        return result
    objective = float(outcome.objective)
    require_close(
        objective,
        first_stage_cost(data, decision) + float(oracle["worst_loss"]),
        "EF objective and independently optimized worst recourse",
    )
    result.update(
        status="optimal",
        objective=objective,
        solver_bound=float(outcome.lower_bound),
        first_stage=decision.to_dict(),
        first_stage_sha256=decision.sha256,
        accounting=accounting.to_dict(),
        oracle=oracle,
        runtime_seconds=perf_counter() - started,
    )
    result["result_sha256"] = canonical_json_sha256(result)
    validate_extensive_form_result(data, result)
    return result


def validate_extensive_form_result(data: QFRData, result: Mapping[str, Any]) -> None:
    required = {
        "schema_version",
        "method",
        "model_kind",
        "status",
        "data_sha256",
        "scenario_sha256",
        "solver",
        "objective",
        "solver_bound",
        "first_stage",
        "first_stage_sha256",
        "accounting",
        "oracle",
        "runtime_seconds",
        "result_sha256",
    }
    if set(result) != required:
        raise ValueError("EF result fields are incomplete or unexpected")
    bare = dict(result)
    sealed = bare.pop("result_sha256")
    if sealed != canonical_json_sha256(bare):
        raise ValueError("EF result seal mismatch")
    if result["schema_version"] != 1 or result["method"] != "R3_V2_EF":
        raise ValueError("not an R3 v2 EF result")
    if result["status"] != "optimal":
        raise ValueError("EF result is not accepted optimal")
    if result["data_sha256"] != data.data_sha256 or result["scenario_sha256"] != data.scenario_sha256:
        raise ValueError("EF Q-F-R data identity mismatch")
    accepted_outcome(result["solver"])
    decision = QFRFirstStage.from_dict(result["first_stage"])
    validate_first_stage(data, decision)
    if decision.model_kind != result["model_kind"] or decision.sha256 != result["first_stage_sha256"]:
        raise ValueError("EF first-stage identity mismatch")
    accounting = result["accounting"]
    validate_accounting_payload(
        data,
        data,
        decision,
        accounting,
        expected_objective=float(result["objective"]),
        expected_theta=float(accounting["theta"]),
    )
    validate_oracle(data, decision, result["oracle"])
    objective = first_stage_cost(data, decision) + float(result["oracle"]["worst_loss"])
    require_close(float(result["objective"]), objective, "EF certified objective")
    require_close(float(result["solver"]["objective"]), objective, "EF solver objective")
    require_close(float(result["solver_bound"]), objective, "EF solver bound")
