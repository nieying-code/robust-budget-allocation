"""Preregistered licensed R3 v2 correctness suite and evidence construction."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from robust_budget_allocation.data.qfr_data import QFRData
from robust_budget_allocation.io.hashing import canonical_json_sha256, sha256_file
from robust_budget_allocation.reproducibility.git_state import validate_source_state
from robust_budget_allocation.runtime.environment import ensure_preflight_once
from .qfr_extensive_form import solve_qfr_extensive_form
from .qfr_protocol import (
    PROTOCOL_SHA256,
    R3_REQUIRED_SOURCE_PATHS,
    protocol_identity,
    r2_model_identity,
    solver_configuration_identity,
)
from .qfr_standard_ccg import solve_qfr_standard_ccg
from .qfr_verification import seal_evidence, validate_r3_evidence, verify_ef_a0_pair


SOURCE_PATHS = R3_REQUIRED_SOURCE_PATHS


def load_fixture(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if set(payload) != {"fixture_scope", "protocol_sha256", "cases"}:
        raise ValueError("R3 fixture fields are incomplete or unexpected")
    if payload["fixture_scope"] != "CORRECTNESS_FIXTURE_ONLY_NOT_FORMAL_SCIENTIFIC_PARAMETERS":
        raise ValueError("R3 fixture scope marker mismatch")
    if payload["protocol_sha256"] != PROTOCOL_SHA256:
        raise ValueError("R3 fixture is not bound to the frozen protocol")
    if not isinstance(payload["cases"], list) or not payload["cases"]:
        raise ValueError("R3 fixture must contain cases")
    case_ids: set[str] = set()
    for row in payload["cases"]:
        if set(row) != {"case_id", "purpose", "data"}:
            raise ValueError("R3 fixture case fields mismatch")
        case_id = row["case_id"]
        if not isinstance(case_id, str) or not case_id or case_id in case_ids:
            raise ValueError("R3 fixture case IDs must be unique nonempty strings")
        case_ids.add(case_id)
        QFRData.from_dict(row["data"])
    return payload


def run_r3_correctness_suite(repo_root: Path, fixture_path: Path) -> dict[str, Any]:
    """Execute the frozen small licensed matrix; no pilot or scientific experiment."""

    root = repo_root.resolve()
    fixture = fixture_path.resolve()
    payload = load_fixture(fixture)
    required = [root / value for value in SOURCE_PATHS]
    source_git = validate_source_state(
        root,
        required_tracked_paths=required,
        scientific_roots=("src", "configs", "scripts", "tests/fixtures"),
    )
    environment = ensure_preflight_once().to_dict()
    cases: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    for fixture_case in payload["cases"]:
        data = QFRData.from_dict(fixture_case["data"])
        for model_kind in ("M0", "M1", "M2"):
            ef = solve_qfr_extensive_form(data, model_kind)
            a0 = solve_qfr_standard_ccg(data, model_kind)
            certificate = None
            try:
                certificate = verify_ef_a0_pair(data, ef, a0)
            except Exception as exc:
                failures.append(
                    {
                        "case_id": fixture_case["case_id"],
                        "model_kind": model_kind,
                        "type": type(exc).__name__,
                        "message": str(exc),
                    }
                )
            cases.append(
                {
                    "case_id": fixture_case["case_id"],
                    "model_kind": model_kind,
                    "data_sha256": data.data_sha256,
                    "scenario_sha256": data.scenario_sha256,
                    "ef": ef,
                    "a0": a0,
                    "certificate": certificate,
                }
            )
    accepted = [row["certificate"] for row in cases if row["certificate"] is not None]
    summary = {
        "status": "PASS" if not failures else "FAIL",
        "case_count": len(cases),
        "accepted_case_count": len(accepted),
        "failures": failures,
        "maximum_objective_difference": max(
            (float(row["objective_difference"]) for row in accepted), default=0.0
        ),
        "maximum_feasibility_violation": max(
            (float(row["maximum_feasibility_violation"]) for row in accepted), default=0.0
        ),
        "total_a0_iterations": sum(int(row["a0"]["iterations"]) for row in cases),
        "total_exact_oracle_calls": sum(
            int(row["a0"]["exact_oracle_calls"]) for row in cases
        ),
        "total_scenario_evaluations": sum(
            int(row["a0"]["scenario_evaluations"]) for row in cases
        ),
    }
    source_files = [
        {"path": value, "sha256": sha256_file(root / value)} for value in SOURCE_PATHS
    ]
    evidence = seal_evidence(
        {
            "schema_version": 2,
            "phase": "R3",
            "scope": "CORRECTNESS_FIXTURE_ONLY_NOT_FORMAL_SCIENTIFIC_PARAMETERS",
            "protocol": protocol_identity(root),
            "r2_model_base": r2_model_identity(),
            "source": {"git": source_git, "files": source_files},
            "fixture": {
                "path": fixture.relative_to(root).as_posix(),
                "sha256": sha256_file(fixture),
                "payload": payload,
                "config_sha256": canonical_json_sha256(payload),
            },
            "environment": environment,
            "solver_configuration": solver_configuration_identity(),
            "cases": cases,
            "summary": summary,
            "scientific_runs": 0,
            "pilot_runs": 0,
            "formal_experiments": 0,
            "a1_new_implemented": False,
        }
    )
    if not failures:
        validate_r3_evidence(root, evidence)
    return evidence
