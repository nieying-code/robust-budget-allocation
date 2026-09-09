#!/usr/bin/env python
"""Engineering-only replay of the pinned PR31 numerical regression population.

The script reads its E2-A identities and adapter from the immutable reference
commit with ``git show``.  It writes only aggregate engineering evidence; it does
not import, rewrite, or promote E2-A scientific result artifacts.
"""

from __future__ import annotations

from collections import Counter
import csv
import io
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from robust_budget_allocation.algorithms.qfr_final_a1 import (  # noqa: E402
    FINAL_A1_IDENTITY,
    FINAL_A1_IMPLEMENTATION_REVISION,
    solve_qfr_final_a1,
)
from robust_budget_allocation.algorithms.qfr_protocol import close  # noqa: E402
from robust_budget_allocation.io.atomic import atomic_write_json  # noqa: E402
from robust_budget_allocation.io.hashing import sha256_file  # noqa: E402


REFERENCE_HEAD = "db9626f6bd7bc3a2f23cd0bcbe19f66900bbf5d4"
REFERENCE_PR = 31
E2A_MODULE = "src/robust_budget_allocation/formal/e2a.py"
FAILURES = "formal_results/e2_final/e2a/e2a_retained_failures.csv"
FIRST_STAGES = (
    "formal_results/e2_final/e2a/diagnostics/"
    "e2a_205_first_stage_evidence.csv"
)
SCIENTIFIC_RESULTS = "formal_results/e2_final/e2a/e2a_scientific_results.csv"
TAXONOMY = (
    "formal_results/e2_final/e2a/diagnostics/e2a_205_failure_taxonomy.json"
)
OUTPUT = ROOT / "docs/evidence/FINAL_A1_SPURIOUS_INFEASIBILITY_HOTFIX_REPLAY_v1.json"
MARKER = (
    "WITNESS_GATED_INFEASIBLE_SCALED_RETRY_MAPPED_BACK_FOR_"
    "ORIGINAL_SEMANTIC_VALIDATION"
)
REPRESENTATIVES_PER_CASE = 2


def git_show(path: str) -> str:
    return subprocess.check_output(
        ["git", "show", f"{REFERENCE_HEAD}:{path}"],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
    )


def rows_at(path: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(git_show(path))))


def load_reference_adapter() -> dict[str, Any]:
    namespace: dict[str, Any] = {
        "__name__": "_pinned_pr31_e2a_engineering_adapter",
        "__file__": f"{REFERENCE_HEAD}:{E2A_MODULE}",
    }
    exec(compile(git_show(E2A_MODULE), namespace["__file__"], "exec"), namespace)
    return namespace


def oracle_rows(result: dict[str, Any]):
    for trace in result["trace"]:
        candidate = trace.get("candidate")
        if candidate:
            for row in candidate.get("evaluations", []):
                yield "candidate", row
        certification = trace.get("full_exact_certification")
        if certification:
            for row in certification.get("results", []):
                yield "full_exact_certification", row


def main() -> None:
    if FINAL_A1_IDENTITY != "A1_FINAL_NO_MEMORY_V1":
        raise RuntimeError("Final A1 identity changed")
    adapter = load_reference_adapter()
    failures = rows_at(FAILURES)
    if len(failures) != 205:
        raise RuntimeError(f"expected 205 frozen failures, found {len(failures)}")
    taxonomy = json.loads(git_show(TAXONOMY))
    if taxonomy["production_infeasible"] != 284:
        raise RuntimeError("pinned diagnostic taxonomy is not the authorized 284-event audit")
    first_stage_rows = rows_at(FIRST_STAGES)
    expected_first = {
        (row["case_id"], row["simulation_id"]): row["first_stage_sha256"]
        for row in first_stage_rows
    }
    samples = {row["simulation_id"]: row for row in adapter["load_samples"](ROOT)}
    payload, metadata = adapter["load_base_fixture"](ROOT)

    certified = 0
    first_stage_invariant = 0
    full_retry_count = 0
    candidate_retry_count = 0
    retry_scenarios: Counter[str] = Counter()
    statuses: Counter[str] = Counter()
    for index, source in enumerate(failures, 1):
        key = (source["case_id"], source["simulation_id"])
        sample = samples[source["simulation_id"]]
        if sample["input_sha256"] != source["input_sha256"]:
            raise RuntimeError(f"input identity mismatch for {key}")
        data = adapter["data_for_case_sample"](
            payload, metadata, source["case_id"], sample
        )
        result = solve_qfr_final_a1(data, "M2")
        statuses[result["status"]] += 1
        if result["status"] == "certified":
            certified += 1
            if result["incumbent"]["first_stage_sha256"] == expected_first[key]:
                first_stage_invariant += 1
        for stage, row in oracle_rows(result):
            if row["solver"].get("message") == MARKER:
                if stage == "full_exact_certification":
                    full_retry_count += 1
                else:
                    candidate_retry_count += 1
                retry_scenarios[row["scenario_id"]] += 1
        if index % 10 == 0 or index == len(failures):
            print(f"hotfix engineering replay {index}/{len(failures)}", flush=True)

    scientific = rows_at(SCIENTIFIC_RESULTS)
    failure_keys = {
        (row["case_id"], row["simulation_id"]) for row in failures
    }
    representatives: list[dict[str, str]] = []
    per_case: Counter[str] = Counter()
    for row in scientific:
        key = (row["case_id"], row["simulation_id"])
        if (
            row["certificate_status"] == "PASS"
            and key not in failure_keys
            and per_case[row["case_id"]] < REPRESENTATIVES_PER_CASE
        ):
            representatives.append(row)
            per_case[row["case_id"]] += 1
    if len(representatives) != 8:
        raise RuntimeError("could not select eight deterministic certified controls")
    regression = {
        "tested": 0,
        "certified": 0,
        "q_f_r_invariant": 0,
        "objective_invariant": 0,
        "worst_scenario_invariant": 0,
    }
    decision_fields = [
        f"{prefix}_{item}"
        for item in ("Water", "Vaccine", "Crackers")
        for prefix in ("Q", "F", "R")
    ]
    for source in representatives:
        sample = samples[source["simulation_id"]]
        data = adapter["data_for_case_sample"](
            payload, metadata, source["case_id"], sample
        )
        result = solve_qfr_final_a1(data, "M2")
        current = adapter["serialize_result"](
            source["case_id"], sample, data, metadata, result
        )
        regression["tested"] += 1
        regression["certified"] += current["certificate_status"] == "PASS"
        decisions_match = all(
            current[field] == source[field]
            if field.startswith("R_")
            else close(float(current[field]), float(source[field]))
            for field in decision_fields
        )
        regression["q_f_r_invariant"] += decisions_match
        regression["objective_invariant"] += close(
            float(current["T_COST"]), float(source["T_COST"])
        )
        regression["worst_scenario_invariant"] += (
            current["worst_scenario"] == source["worst_scenario"]
        )

    if certified != 205 or first_stage_invariant != 205:
        raise RuntimeError("hotfix replay did not preserve and certify all 205 cases")
    if full_retry_count != 284:
        raise RuntimeError(
            f"expected 284 witness-gated full-certificate retries, got {full_retry_count}"
        )
    if any(value != 8 for value in regression.values()):
        raise RuntimeError("previously-certified control regression changed")
    evidence = {
        "schema_version": 1,
        "scope": "FINAL_A1_SPURIOUS_INFEASIBILITY_HOTFIX_ENGINEERING_REPLAY",
        "reference": {
            "pull_request": REFERENCE_PR,
            "head": REFERENCE_HEAD,
            "role": "READ_ONLY_ENGINEERING_REGRESSION_SOURCE",
            "source_artifacts": {
                path: subprocess.check_output(
                    ["git", "rev-parse", f"{REFERENCE_HEAD}:{path}"],
                    cwd=ROOT,
                    text=True,
                ).strip()
                for path in (FAILURES, FIRST_STAGES, SCIENTIFIC_RESULTS, TAXONOMY)
            },
        },
        "algorithm_identity": FINAL_A1_IDENTITY,
        "implementation_revision": FINAL_A1_IMPLEMENTATION_REVISION,
        "failure_population": {
            "tested": 205,
            "certified": certified,
            "first_stage_identity_invariant": first_stage_invariant,
            "status_counts": dict(statuses),
        },
        "numerical_fallback": {
            "authorized_diagnostic_production_infeasible": 284,
            "witness_triggered_full_certificate_retries": full_retry_count,
            "witness_triggered_candidate_retries": candidate_retry_count,
            "scaled_retry_optimal": full_retry_count + candidate_retry_count,
            "mapped_back_original_validation_pass": (
                full_retry_count + candidate_retry_count
            ),
            "full_exact_certification_pass": certified,
            "scenario_counts_all_retry_stages": dict(sorted(retry_scenarios.items())),
        },
        "previously_certified_controls": regression,
        "guardrails": {
            "scientific_optimization_runs": 0,
            "engineering_regression_only": True,
            "formal_E2A_recertification": False,
            "scientific_results_promoted_or_modified": False,
            "tolerance_changed": False,
            "model_changed": False,
            "scientific_parameters_changed": False,
            "scientific_design_changed": False,
            "memory_reintroduced": False,
            "E2_B_runs": 0,
            "E2_C_runs": 0,
            "E2_D_runs": 0,
        },
        "implementation_sha256": {
            "qfr_exact_oracle.py": sha256_file(
                ROOT / "src/robust_budget_allocation/algorithms/qfr_exact_oracle.py"
            ),
            "qfr_final_a1.py": sha256_file(
                ROOT / "src/robust_budget_allocation/algorithms/qfr_final_a1.py"
            ),
        },
    }
    atomic_write_json(OUTPUT, evidence)
    print(json.dumps(evidence, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
