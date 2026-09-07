"""Replay the eight retained Layer A A1 failures against production A1/A0/EF."""

from __future__ import annotations

import csv
import gzip
import io
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from robust_budget_allocation.algorithms.qfr_a1_verification import validate_improved_ccg_result  # noqa: E402
from robust_budget_allocation.algorithms.qfr_extensive_form import (  # noqa: E402
    solve_qfr_extensive_form,
    validate_extensive_form_result,
)
from robust_budget_allocation.algorithms.qfr_improved_ccg import solve_qfr_improved_ccg  # noqa: E402
from robust_budget_allocation.algorithms.qfr_standard_ccg import (  # noqa: E402
    solve_qfr_standard_ccg,
    validate_standard_ccg_result,
)
from robust_budget_allocation.algorithms.qfr_verification import verify_ef_a0_pair  # noqa: E402
from robust_budget_allocation.io.hashing import canonical_json_sha256, sha256_file  # noqa: E402
from robust_budget_allocation.runtime.environment import ensure_preflight_once  # noqa: E402
from robust_budget_allocation.simulation.layer_a import (  # noqa: E402
    PARAMETERS,
    data_for_sample,
    generate_samples,
    load_config,
    load_neutral_fixture,
    validate_samples,
)


FAILURE_IDS = (
    "LA-0034", "LA-0098", "LA-0161", "LA-0511",
    "LA-0565", "LA-0591", "LA-0695", "LA-0783",
)
CONFIG = ROOT / "configs/qfr_mechanism_layer_a_v1.json"
LAYER_A = ROOT / "simulation_results/qfr_mechanism_layer_a_n1000"
OUTPUT = ROOT / "simulation_results/qfr_mechanism_layer_a_t1_failures"


def classify_outcomes(a1_status: str, a0_status: str, ef_status: str) -> str:
    a1_pass = a1_status == "certified"
    a0_pass = a0_status == "certified"
    ef_pass = ef_status == "optimal"
    if not a1_pass and a0_pass and ef_pass:
        return "A1_ROBUSTNESS_ISSUE"
    if not a1_pass and not a0_pass and not ef_pass:
        return "MODEL_SOLVER_NUMERICAL_OR_FEASIBILITY_ISSUE"
    return "OTHER_COMBINATION_REVIEW_REQUIRED"


def extract_a1_failure(result: Mapping[str, Any]) -> dict[str, Any]:
    trace = list(result.get("trace") or [])
    row = trace[-1] if trace else {}
    phase_name = "unavailable"
    phase: Mapping[str, Any] = {}
    for name in ("memory", "candidate", "full_exact_certification"):
        value = row.get(name)
        if isinstance(value, Mapping) and value.get("status") not in (None, "complete"):
            phase_name, phase = name, value
            break
    failing = next(
        (
            entry for entry in phase.get("evaluations", phase.get("results", []))
            if (entry.get("solver") or {}).get("status") != "optimal"
        ),
        None,
    )
    solver = {} if failing is None else (failing.get("solver") or {})
    return {
        "status": result.get("status"),
        "diagnostic": result.get("diagnostic"),
        "iteration": row.get("iteration"),
        "phase": phase_name,
        "planned_scenarios": list(phase.get("planned") or []),
        "failing_scenario": None if failing is None else failing.get("scenario_id"),
        "failing_scenario_identity": None if failing is None else failing.get("scenario_identity"),
        "failing_first_stage_sha256": None if failing is None else failing.get("first_stage_sha256"),
        "solver_status": solver.get("status"),
        "solver_termination": solver.get("termination_condition"),
        "solver_message": solver.get("message"),
        "solver_runtime_seconds": solver.get("runtime_seconds"),
        "result_sha256": result.get("result_sha256"),
    }


def _load_samples() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with (LAYER_A / "samples.csv").open("r", encoding="utf-8", newline="") as handle:
        for raw in csv.DictReader(handle):
            row: dict[str, Any] = {
                "simulation_id": raw["simulation_id"],
                "sample_index": int(raw["sample_index"]),
                "simulation_seed": int(raw["simulation_seed"]),
                "input_sha256": raw["input_sha256"],
            }
            row.update({name: float(raw[name]) for name in PARAMETERS})
            rows.append(row)
    return rows


def _load_original_failures() -> dict[str, dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    for path in sorted((LAYER_A / "raw_a1").glob("*.jsonl.gz")):
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            for line in handle:
                record = json.loads(line)
                if record.get("simulation_id") in FAILURE_IDS:
                    found[record["simulation_id"]] = record
    if set(found) != set(FAILURE_IDS):
        raise RuntimeError("the eight original A1 failure records are incomplete")
    return found


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n",
    )


def _write_csv(path: Path, rows: list[Mapping[str, Any]]) -> None:
    fields = list(dict.fromkeys(key for row in rows for key in row))
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    path.write_bytes(stream.getvalue().encode("utf-8"))


def _method_summary(result: Mapping[str, Any], validation: str) -> dict[str, Any]:
    solver = result.get("solver") or {}
    return {
        "status": result.get("status"),
        "objective": result.get("objective"),
        "validation": validation,
        "result_sha256": result.get("result_sha256"),
        "solver_status": solver.get("status", "multiple/trace"),
        "solver_termination": solver.get("termination_condition", "multiple/trace"),
        "runtime_seconds": result.get("runtime_seconds"),
    }


def run() -> int:
    if OUTPUT.exists():
        raise RuntimeError("T1 output already exists; replay is one-shot and non-overwriting")
    config = load_config(CONFIG)
    samples = _load_samples()
    if samples != generate_samples(config):
        raise RuntimeError("stored Layer A inputs do not reproduce exactly")
    validate_samples(samples, config)
    selected = {row["simulation_id"]: row for row in samples if row["simulation_id"] in FAILURE_IDS}
    if tuple(selected) != FAILURE_IDS:
        raise RuntimeError("T1 failure samples are missing or reordered")
    originals = _load_original_failures()
    neutral, fixture = load_neutral_fixture(ROOT, config)
    environment = ensure_preflight_once().to_dict()
    execution_commit = _git("rev-parse", "HEAD")
    execution_tree = _git("rev-parse", "HEAD^{tree}")
    if _git("status", "--porcelain=v1"):
        raise RuntimeError("T1 replay requires a clean committed harness")

    OUTPUT.mkdir(parents=True)
    raw_dir = OUTPUT / "raw"
    raw_dir.mkdir()
    rows: list[dict[str, Any]] = []
    for simulation_id in FAILURE_IDS:
        sample = selected[simulation_id]
        original = originals[simulation_id]
        if original["input"] != sample:
            raise RuntimeError(f"{simulation_id} original input differs from frozen sample table")
        data = data_for_sample(neutral, fixture["metadata"], sample)
        original_a1 = original["a1_result"]
        if original_a1["data_sha256"] != data.data_sha256:
            raise RuntimeError(f"{simulation_id} reconstructed data identity differs from original run")

        a1 = solve_qfr_improved_ccg(data, "M2", memory_phase_enabled=True)
        a1_diag = extract_a1_failure(a1)
        a1_validation = "NOT_APPLICABLE_FAILURE"
        if a1["status"] == "certified":
            validate_improved_ccg_result(data, a1)
            a1_validation = "PASS"

        a0 = solve_qfr_standard_ccg(data, "M2")
        a0_validation = "NOT_APPLICABLE_FAILURE"
        if a0["status"] == "certified":
            validate_standard_ccg_result(data, a0)
            a0_validation = "PASS"

        ef = solve_qfr_extensive_form(data, "M2")
        ef_validation = "NOT_APPLICABLE_FAILURE"
        if ef["status"] == "optimal":
            validate_extensive_form_result(data, ef)
            ef_validation = "PASS"

        pair = None
        if a0["status"] == "certified" and ef["status"] == "optimal":
            pair = verify_ef_a0_pair(data, ef, a0)

        original_diag = extract_a1_failure(original_a1)
        replay_reproduced = all(
            a1_diag[key] == original_diag[key]
            for key in ("status", "diagnostic", "iteration", "phase", "failing_scenario", "solver_status", "solver_termination")
        )
        classification = classify_outcomes(str(a1["status"]), str(a0["status"]), str(ef["status"]))
        record = {
            "schema_version": 1,
            "scope": "LAYER_A_T1_FAILURE_REPLAY",
            "simulation_id": simulation_id,
            "input": sample,
            "input_sha256": sample["input_sha256"],
            "data_sha256": data.data_sha256,
            "scenario_sha256": data.scenario_sha256,
            "execution_git_commit": execution_commit,
            "execution_git_tree": execution_tree,
            "original_a1_failure": original_diag,
            "replay_a1_failure": a1_diag,
            "a1_failure_reproduced": replay_reproduced,
            "A1": a1,
            "A0": a0,
            "EF": ef,
            "EF_A0_certificate": pair,
            "classification": classification,
        }
        raw_path = raw_dir / f"{simulation_id}.json.gz"
        raw_bytes = (json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
        with raw_path.open("wb") as handle, gzip.GzipFile(
            filename="", mode="wb", fileobj=handle, mtime=0
        ) as compressed:
            compressed.write(raw_bytes)

        a0_summary = _method_summary(a0, a0_validation)
        ef_summary = _method_summary(ef, ef_validation)
        rows.append({
            "simulation_id": simulation_id,
            "input_sha256": sample["input_sha256"],
            "data_sha256": data.data_sha256,
            "scenario_sha256": data.scenario_sha256,
            "a1_original_status": original_diag["status"],
            "a1_replay_status": a1_diag["status"],
            "a1_failure_reproduced": replay_reproduced,
            "a1_failure_iteration": a1_diag["iteration"],
            "a1_failure_phase": a1_diag["phase"],
            "a1_diagnostic": a1_diag["diagnostic"],
            "a1_failing_scenario": a1_diag["failing_scenario"],
            "a1_failing_scenario_identity": a1_diag["failing_scenario_identity"],
            "a1_failing_first_stage_sha256": a1_diag["failing_first_stage_sha256"],
            "a1_solver_status": a1_diag["solver_status"],
            "a1_solver_termination": a1_diag["solver_termination"],
            "a1_objective": a1.get("objective"),
            "a1_certificate": a1_validation,
            "a1_result_sha256": a1.get("result_sha256"),
            "a0_status": a0_summary["status"],
            "a0_objective": a0_summary["objective"],
            "a0_certificate": a0_summary["validation"],
            "a0_result_sha256": a0_summary["result_sha256"],
            "ef_status": ef_summary["status"],
            "ef_objective": ef_summary["objective"],
            "ef_certificate": ef_summary["validation"],
            "ef_result_sha256": ef_summary["result_sha256"],
            "ef_a0_pair_certificate": None if pair is None else pair["status"],
            "ef_a0_pair_certificate_sha256": None if pair is None else pair["certificate_sha256"],
            "classification": classification,
        })
        print(
            f"{simulation_id} A1={a1['status']} A0={a0['status']} EF={ef['status']} "
            f"classification={classification}", flush=True
        )

    _write_csv(OUTPUT / "case_results.csv", rows)
    summary = {
        "scope": "LAYER_A_T1_FAILURE_REPLAY",
        "status": "COMPLETE",
        "case_count": len(rows),
        "case_ids": list(FAILURE_IDS),
        "all_original_inputs_unchanged": True,
        "all_a1_failures_reproduced": all(row["a1_failure_reproduced"] for row in rows),
        "classification_counts": {
            label: sum(row["classification"] == label for row in rows)
            for label in sorted({row["classification"] for row in rows})
        },
        "cases": rows,
    }
    summary["summary_sha256"] = canonical_json_sha256(summary)
    _write_json(OUTPUT / "summary.json", summary)
    manifest = {
        "schema_version": 1,
        "scope": "LAYER_A_T1_FAILURE_REPLAY",
        "status": "COMPLETE",
        "execution_order": ["A1_full", "A0", "EF"],
        "execution_git_commit": execution_commit,
        "execution_git_tree": execution_tree,
        "model_kind": "M2",
        "environment": environment,
        "source_sample_table": (LAYER_A / "samples.csv").relative_to(ROOT).as_posix(),
        "source_sample_table_sha256": sha256_file(LAYER_A / "samples.csv"),
        "source_layer_a_manifest_sha256": sha256_file(LAYER_A / "simulation_manifest.json"),
        "config_identity_sha256": canonical_json_sha256(config),
        "neutral_fixture_sha256": fixture["neutral_fixture_sha256"],
        "case_ids": list(FAILURE_IDS),
        "guardrails": {
            "resampled": False,
            "parameters_changed": False,
            "model_changed": False,
            "algorithms_changed": False,
            "solver_policy_changed": False,
            "tolerance_changed": False,
            "environment_changed": False,
            "n1000_rerun": False,
            "t2_t3_executed": False,
            "figures_generated": False,
        },
    }
    manifest["manifest_sha256"] = canonical_json_sha256(manifest)
    _write_json(OUTPUT / "manifest.json", manifest)
    paths = sorted(path for path in OUTPUT.rglob("*") if path.is_file() and path.name != "HASHES.sha256")
    (OUTPUT / "HASHES.sha256").write_text(
        "\n".join(f"{sha256_file(path)}  {path.relative_to(OUTPUT).as_posix()}" for path in paths) + "\n",
        encoding="utf-8", newline="\n",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
