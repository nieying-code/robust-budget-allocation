"""R4 preregistered EF/A0/A1 correctness suite and evidence construction."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from robust_budget_allocation.data.qfr_data import QFRData
from robust_budget_allocation.io.hashing import canonical_json_sha256, sha256_file
from robust_budget_allocation.reproducibility.git_state import validate_source_state
from robust_budget_allocation.runtime.environment import ensure_preflight_once
from .qfr_a1_verification import validate_r4_evidence, verify_ef_a0_a1
from .qfr_extensive_form import solve_qfr_extensive_form
from .qfr_improved_ccg import R4_PROTOCOL_PATH, R4_PROTOCOL_SHA256, solve_qfr_improved_ccg
from .qfr_protocol import solver_configuration_identity
from .qfr_standard_ccg import solve_qfr_standard_ccg
from .qfr_verification import seal_evidence


R4_SOURCE_PATHS = (
    "docs/R3_CORRECTNESS_PROTOCOL_v2.md",
    R4_PROTOCOL_PATH,
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
    "src/robust_budget_allocation/algorithms/qfr_accounting.py",
    "src/robust_budget_allocation/algorithms/qfr_exact_oracle.py",
    "src/robust_budget_allocation/algorithms/qfr_extensive_form.py",
    "src/robust_budget_allocation/algorithms/qfr_standard_ccg.py",
    "src/robust_budget_allocation/algorithms/qfr_verification.py",
    "src/robust_budget_allocation/algorithms/qfr_a1_memory.py",
    "src/robust_budget_allocation/algorithms/qfr_a1_candidates.py",
    "src/robust_budget_allocation/algorithms/qfr_improved_ccg.py",
    "src/robust_budget_allocation/algorithms/qfr_a1_verification.py",
    "src/robust_budget_allocation/algorithms/qfr_a1_suite.py",
    "scripts/r4_ef_a0_a1_correctness.py",
)


def load_r4_fixture(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload["fixture_scope"] != "CORRECTNESS_FIXTURE_ONLY_NOT_FORMAL_SCIENTIFIC_PARAMETERS":
        raise ValueError("R4 must reuse the reviewed R3 correctness fixture unchanged")
    for row in payload["cases"]:
        QFRData.from_dict(row["data"])
    return payload


def run_r4_correctness_suite(
    repo_root: Path,
    fixture_path: Path,
    *,
    memory_phase_enabled: bool,
) -> dict[str, Any]:
    root = repo_root.resolve()
    fixture = fixture_path.resolve()
    payload = load_r4_fixture(fixture)
    required = [root / value for value in R4_SOURCE_PATHS]
    source_git = validate_source_state(
        root,
        required_tracked_paths=required,
        scientific_roots=("src", "configs", "scripts", "tests/fixtures"),
    )
    cases = []
    for fixture_case in payload["cases"]:
        data = QFRData.from_dict(fixture_case["data"])
        for model_kind in ("M0", "M1", "M2"):
            ef = solve_qfr_extensive_form(data, model_kind)
            a0 = solve_qfr_standard_ccg(data, model_kind)
            a1 = solve_qfr_improved_ccg(
                data, model_kind, memory_phase_enabled=memory_phase_enabled
            )
            certificate = verify_ef_a0_a1(data, ef, a0, a1)
            cases.append(
                {
                    "case_id": fixture_case["case_id"],
                    "model_kind": model_kind,
                    "data_sha256": data.data_sha256,
                    "scenario_sha256": data.scenario_sha256,
                    "ef": ef,
                    "a0": a0,
                    "a1": a1,
                    "certificate": certificate,
                }
            )
    memory_opportunities = sum(row["a1"]["memory_opportunities"] for row in cases)
    memory_hits = sum(row["a1"]["memory_hits"] for row in cases)
    decision = (
        "REMOVE_INDEPENDENT_MEMORY_PHASE"
        if memory_opportunities > 0 and memory_hits == 0
        else "RETAIN_MEMORY_PHASE"
        if memory_hits > 0
        else "MEMORY_VALUE_NOT_IDENTIFIED_NONBLOCKING"
    )
    summary = {
        "status": "PASS",
        "case_count": len(cases),
        "maximum_objective_difference": max(
            row["certificate"]["maximum_objective_difference"] for row in cases
        ),
        "maximum_feasibility_violation": max(
            row["certificate"]["maximum_feasibility_violation"] for row in cases
        ),
        "a0_iterations": sum(row["a0"]["iterations"] for row in cases),
        "a0_full_exact_calls": sum(row["a0"]["exact_oracle_calls"] for row in cases),
        "a0_scenario_evaluations": sum(row["a0"]["scenario_evaluations"] for row in cases),
        "a1_iterations": sum(row["a1"]["iterations"] for row in cases),
        "memory_opportunities": memory_opportunities,
        "memory_hits": memory_hits,
        "candidate_hits": sum(row["a1"]["candidate_hits"] for row in cases),
        "a1_full_exact_certification_calls": sum(
            row["a1"]["full_exact_certification_calls"] for row in cases
        ),
        "a1_scenario_evaluations": sum(
            row["a1"]["scenario_evaluations"] for row in cases
        ),
        "memory_decision": decision,
    }
    evidence = seal_evidence(
        {
            "schema_version": 1,
            "phase": "R4",
            "scope": "CORRECTNESS_ONLY_NOT_PERFORMANCE_OR_SCIENTIFIC_EXPERIMENT",
            "r4_protocol": {
                "path": R4_PROTOCOL_PATH,
                "sha256": R4_PROTOCOL_SHA256,
            },
            "source": {
                "git": source_git,
                "files": [
                    {"path": value, "sha256": sha256_file(root / value)}
                    for value in R4_SOURCE_PATHS
                ],
            },
            "fixture": {
                "path": fixture.relative_to(root).as_posix(),
                "sha256": sha256_file(fixture),
                "payload": payload,
                "config_sha256": canonical_json_sha256(payload),
            },
            "environment": ensure_preflight_once().to_dict(),
            "solver_configuration": solver_configuration_identity(),
            "memory_phase_enabled": memory_phase_enabled,
            "cases": cases,
            "summary": summary,
            "scientific_runs": 0,
            "pilot_runs": 0,
            "formal_experiments": 0,
        }
    )
    validate_r4_evidence(root, evidence)
    return evidence
