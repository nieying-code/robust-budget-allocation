"""Minimal EF/A0/A1 correctness regression for the Q-F-R availability revision."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from robust_budget_allocation.data.qfr_data import QFRData
from robust_budget_allocation.io.hashing import (
    canonical_json_sha256,
    sha256_bytes,
    sha256_file,
)
from robust_budget_allocation.reproducibility.git_state import validate_source_state
from robust_budget_allocation.runtime.environment import ensure_preflight_once
from .qfr_a1_verification import (
    _anchored_file,
    _anchored_tree,
    validate_three_certificate,
    verify_ef_a0_a1,
)
from .qfr_extensive_form import solve_qfr_extensive_form
from .qfr_protocol import solver_configuration_identity
from .qfr_standard_ccg import solve_qfr_standard_ccg
from .qfr_improved_ccg import solve_qfr_improved_ccg
from .qfr_verification import seal_evidence


PROTOCOL_PATH = "docs/QFR_AVAILABILITY_CORRECTNESS_PROTOCOL_v2_1.md"
PROTOCOL_SHA256 = "2ff46393109fab00710e6dfebc5a3ef17ad3376bcdf4528a3db068ebe05f800"
PROTOCOL_FREEZE_COMMIT = "b5a44908d992ab2b1267ff0067eb78a1ff439c73"
PROTOCOL_FREEZE_TREE = "e129d20c4d43e72f38bdd60a349ac5ad90481329"
FIXTURE_SCOPE = "CORRECTNESS_FIXTURE_ONLY_NOT_PILOT_OR_FORMAL_PARAMETERS"

SOURCE_PATHS = (
    PROTOCOL_PATH,
    "docs/QFR_AVAILABILITY_MODEL_SPEC_v2_1.md",
    "tests/fixtures/qfr_availability_correctness_v2_1.json",
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
    "src/robust_budget_allocation/algorithms/qfr_revision_suite.py",
    "scripts/qfr_availability_correctness.py",
)


def load_revision_fixture(path: Path) -> dict[str, Any]:
    payload = json.loads(path.resolve().read_text(encoding="utf-8"))
    if set(payload) != {"fixture_scope", "protocol_sha256", "cases"}:
        raise ValueError("revision correctness fixture fields mismatch")
    if payload["fixture_scope"] != FIXTURE_SCOPE:
        raise ValueError("revision correctness fixture scope mismatch")
    if payload["protocol_sha256"] != PROTOCOL_SHA256:
        raise ValueError("revision correctness fixture protocol mismatch")
    if not isinstance(payload["cases"], list) or not payload["cases"]:
        raise ValueError("revision correctness fixture must contain cases")
    seen: set[str] = set()
    for row in payload["cases"]:
        if set(row) != {"case_id", "purpose", "data"}:
            raise ValueError("revision correctness case fields mismatch")
        if not isinstance(row["case_id"], str) or not row["case_id"] or row["case_id"] in seen:
            raise ValueError("revision correctness case IDs must be unique")
        seen.add(row["case_id"])
        data = QFRData.from_dict(row["data"])
        if data.schema_version != 3:
            raise ValueError("revision correctness requires QFR schema_version 3")
    return payload


def _summary(certificates: list[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "status": "PASS",
        "case_count": len(certificates),
        "maximum_objective_difference": max(
            float(row["maximum_objective_difference"]) for row in certificates
        ),
        "maximum_feasibility_violation": max(
            float(row["maximum_feasibility_violation"]) for row in certificates
        ),
        "a0_iterations": sum(int(row["a0_iterations"]) for row in certificates),
        "a0_full_exact_calls": sum(int(row["a0_full_exact_calls"]) for row in certificates),
        "a0_scenario_evaluations": sum(
            int(row["a0_scenario_evaluations"]) for row in certificates
        ),
        "a1_iterations": sum(int(row["a1_iterations"]) for row in certificates),
        "memory_opportunities": sum(
            int(row["a1_memory_opportunities"]) for row in certificates
        ),
        "memory_hits": sum(int(row["a1_memory_hits"]) for row in certificates),
        "candidate_hits": sum(int(row["a1_candidate_hits"]) for row in certificates),
        "a1_full_exact_certification_calls": sum(
            int(row["a1_full_exact_certification_calls"]) for row in certificates
        ),
        "a1_scenario_evaluations": sum(
            int(row["a1_scenario_evaluations"]) for row in certificates
        ),
    }


def run_revision_correctness_suite(repo_root: Path, fixture_path: Path) -> dict[str, Any]:
    """Run exactly the revised small correctness matrix; never a pilot."""

    root = repo_root.resolve()
    fixture = fixture_path.resolve()
    payload = load_revision_fixture(fixture)
    source_git = validate_source_state(
        root,
        required_tracked_paths=[root / path for path in SOURCE_PATHS],
        scientific_roots=("src", "configs", "scripts", "tests/fixtures"),
    )
    cases: list[dict[str, Any]] = []
    certificates: list[dict[str, Any]] = []
    for fixture_case in payload["cases"]:
        data = QFRData.from_dict(fixture_case["data"])
        for model_kind in ("M0", "M1", "M2"):
            ef = solve_qfr_extensive_form(data, model_kind)
            a0 = solve_qfr_standard_ccg(data, model_kind)
            a1 = solve_qfr_improved_ccg(data, model_kind, memory_phase_enabled=True)
            certificate = verify_ef_a0_a1(data, ef, a0, a1)
            certificates.append(certificate)
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
    evidence = seal_evidence(
        {
            "schema_version": 1,
            "phase": "QFR_AVAILABILITY_CORRECTNESS_REVISION",
            "scope": FIXTURE_SCOPE,
            "protocol": {
                "path": PROTOCOL_PATH,
                "sha256": PROTOCOL_SHA256,
                "freeze_commit": PROTOCOL_FREEZE_COMMIT,
                "freeze_tree": PROTOCOL_FREEZE_TREE,
            },
            "source": {
                "git": source_git,
                "files": [
                    {"path": path, "sha256": sha256_file(root / path)}
                    for path in SOURCE_PATHS
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
            "cases": cases,
            "summary": _summary(certificates),
            "scientific_runs": 0,
            "pilot_runs": 0,
            "formal_experiments": 0,
            "oos_runs": 0,
        }
    )
    validate_revision_evidence(root, evidence)
    return evidence


def validate_revision_evidence(repo_root: Path, evidence: Mapping[str, Any]) -> dict[str, Any]:
    """Replay revised numerical correctness using the existing identity/certificate logic."""

    required = {
        "schema_version",
        "phase",
        "scope",
        "protocol",
        "source",
        "fixture",
        "environment",
        "solver_configuration",
        "cases",
        "summary",
        "scientific_runs",
        "pilot_runs",
        "formal_experiments",
        "oos_runs",
        "evidence_sha256",
    }
    if set(evidence) != required:
        raise ValueError("revision evidence fields mismatch")
    bare = dict(evidence)
    seal = bare.pop("evidence_sha256")
    if seal != canonical_json_sha256(bare):
        raise ValueError("revision evidence seal mismatch")
    if (
        evidence["schema_version"] != 1
        or evidence["phase"] != "QFR_AVAILABILITY_CORRECTNESS_REVISION"
        or evidence["scope"] != FIXTURE_SCOPE
    ):
        raise ValueError("not Q-F-R availability correctness evidence")
    protocol = evidence["protocol"]
    expected_protocol = {
        "path": PROTOCOL_PATH,
        "sha256": PROTOCOL_SHA256,
        "freeze_commit": PROTOCOL_FREEZE_COMMIT,
        "freeze_tree": PROTOCOL_FREEZE_TREE,
    }
    if protocol != expected_protocol or sha256_file(repo_root / PROTOCOL_PATH) != PROTOCOL_SHA256:
        raise ValueError("revision protocol identity mismatch")
    source = evidence["source"]
    git = source["git"]
    if git["tracked_dirty"] is not False or git["untracked_paths"] or git["untracked_scientific_paths"]:
        raise ValueError("revision correctness source was not clean")
    commit = str(git["commit_sha"])
    if _anchored_tree(repo_root, commit) != git["tree_sha"]:
        raise ValueError("revision execution commit/tree mismatch")
    paths = [row["path"] for row in source["files"]]
    if paths != list(SOURCE_PATHS) or git["tracked_input_paths"] != paths:
        raise ValueError("revision source inventory mismatch")
    for row in source["files"]:
        if set(row) != {"path", "sha256"} or sha256_bytes(
            _anchored_file(repo_root, commit, row["path"])
        ) != row["sha256"]:
            raise ValueError("revision anchored source mismatch")
    fixture = evidence["fixture"]
    payload = load_revision_fixture(repo_root / fixture["path"])
    if (
        fixture["payload"] != payload
        or fixture["sha256"] != sha256_file(repo_root / fixture["path"])
        or fixture["config_sha256"] != canonical_json_sha256(payload)
    ):
        raise ValueError("revision fixture identity mismatch")
    if evidence["solver_configuration"] != solver_configuration_identity():
        raise ValueError("revision solver configuration mismatch")
    locked_environment = {
        "python": "3.12.10",
        "python_implementation": "CPython",
        "pyomo": "6.10.1",
        "gurobipy": "13.0.2",
        "gurobi_optimizer": "13.0.2",
        "solver_interface": "gurobi_direct",
        "threads": 1,
        "solver_available": True,
        "license_available": True,
        "status": "PASS",
    }
    if any(
        evidence["environment"].get(key) != value
        for key, value in locked_environment.items()
    ):
        raise ValueError("revision locked licensed environment mismatch")
    fixture_cases = {row["case_id"]: row for row in payload["cases"]}
    expected = {(case_id, kind) for case_id in fixture_cases for kind in ("M0", "M1", "M2")}
    seen: set[tuple[str, str]] = set()
    certificates: list[dict[str, Any]] = []
    for row in evidence["cases"]:
        key = (row["case_id"], row["model_kind"])
        if key in seen or key not in expected:
            raise ValueError("revision case coverage mismatch")
        seen.add(key)
        data = QFRData.from_dict(fixture_cases[row["case_id"]]["data"])
        if row["data_sha256"] != data.data_sha256 or row["scenario_sha256"] != data.scenario_sha256:
            raise ValueError("revision case data identity mismatch")
        validate_three_certificate(
            data,
            row["ef"],
            row["a0"],
            row["a1"],
            row["certificate"],
            expected_model_kind=row["model_kind"],
        )
        certificates.append(verify_ef_a0_a1(data, row["ef"], row["a0"], row["a1"]))
    if seen != expected or evidence["summary"] != _summary(certificates):
        raise ValueError("revision correctness summary mismatch")
    if any(evidence[key] != 0 for key in ("scientific_runs", "pilot_runs", "formal_experiments", "oos_runs")):
        raise ValueError("revision correctness scope count mismatch")
    return {"status": "PASS", "case_count": len(seen), "evidence_sha256": seal}
