"""Verify the minimal exact-recourse numerical fix on the eight frozen T1 inputs."""

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
from robust_budget_allocation.algorithms.qfr_improved_ccg import solve_qfr_improved_ccg  # noqa: E402
from robust_budget_allocation.algorithms.qfr_protocol import require_close  # noqa: E402
from robust_budget_allocation.io.hashing import canonical_json_sha256, sha256_file  # noqa: E402
from robust_budget_allocation.runtime.environment import ensure_preflight_once  # noqa: E402
from robust_budget_allocation.simulation.layer_a import (  # noqa: E402
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
T1 = ROOT / "simulation_results/qfr_mechanism_layer_a_t1_failures"
OUTPUT = ROOT / "simulation_results/qfr_mechanism_layer_a_t2_a1_regression"


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
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    path.write_bytes(stream.getvalue().encode("utf-8"))


def run() -> int:
    if OUTPUT.exists():
        raise RuntimeError("T2 regression output already exists")
    config = load_config(CONFIG)
    samples = generate_samples(config)
    validate_samples(samples, config)
    selected = {row["simulation_id"]: row for row in samples if row["simulation_id"] in FAILURE_IDS}
    if tuple(selected) != FAILURE_IDS:
        raise RuntimeError("the eight frozen T1 inputs are incomplete or reordered")
    with (T1 / "case_results.csv").open("r", encoding="utf-8", newline="") as handle:
        baseline = {row["simulation_id"]: row for row in csv.DictReader(handle)}
    if set(baseline) != set(FAILURE_IDS):
        raise RuntimeError("T1 baseline result set differs from the frozen eight cases")
    neutral, fixture = load_neutral_fixture(ROOT, config)
    environment = ensure_preflight_once().to_dict()
    commit, tree = _git("rev-parse", "HEAD"), _git("rev-parse", "HEAD^{tree}")
    if _git("status", "--porcelain=v1"):
        raise RuntimeError("T2 regression requires a clean committed numerical fix")

    OUTPUT.mkdir(parents=True)
    raw_dir = OUTPUT / "raw"
    raw_dir.mkdir()
    rows: list[dict[str, Any]] = []
    for simulation_id in FAILURE_IDS:
        sample = selected[simulation_id]
        expected = baseline[simulation_id]
        if sample["input_sha256"] != expected["input_sha256"]:
            raise RuntimeError(f"{simulation_id} input hash changed")
        data = data_for_sample(neutral, fixture["metadata"], sample)
        if data.data_sha256 != expected["data_sha256"]:
            raise RuntimeError(f"{simulation_id} data identity changed")
        result = solve_qfr_improved_ccg(data, "M2", memory_phase_enabled=True)
        if result["status"] != "certified":
            raise RuntimeError(f"{simulation_id} remains unresolved: {result['status']} {result['diagnostic']}")
        validate_improved_ccg_result(data, result)
        a1_objective = float(result["objective"])
        a0_objective = float(expected["a0_objective"])
        ef_objective = float(expected["ef_objective"])
        require_close(a1_objective, a0_objective, f"{simulation_id} repaired A1/A0 objective")
        require_close(a1_objective, ef_objective, f"{simulation_id} repaired A1/EF objective")
        raw = {
            "schema_version": 1,
            "scope": "LAYER_A_T2_A1_NUMERICAL_REGRESSION",
            "simulation_id": simulation_id,
            "input": sample,
            "data_sha256": data.data_sha256,
            "scenario_sha256": data.scenario_sha256,
            "execution_git_commit": commit,
            "execution_git_tree": tree,
            "A1": result,
            "T1_A0_objective": a0_objective,
            "T1_EF_objective": ef_objective,
        }
        path = raw_dir / f"{simulation_id}.json.gz"
        raw_bytes = (json.dumps(raw, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
        with path.open("wb") as handle, gzip.GzipFile(
            filename="", mode="wb", fileobj=handle, mtime=0
        ) as compressed:
            compressed.write(raw_bytes)
        rows.append({
            "simulation_id": simulation_id,
            "input_sha256": sample["input_sha256"],
            "data_sha256": data.data_sha256,
            "scenario_sha256": data.scenario_sha256,
            "a1_status": result["status"],
            "a1_objective": a1_objective,
            "a1_certificate": "PASS",
            "a1_result_sha256": result["result_sha256"],
            "a0_objective": a0_objective,
            "ef_objective": ef_objective,
            "a1_a0_absolute_difference": abs(a1_objective - a0_objective),
            "a1_ef_absolute_difference": abs(a1_objective - ef_objective),
            "objective_tolerance": 1e-7 + 1e-9 * max(1.0, abs(a1_objective), abs(a0_objective), abs(ef_objective)),
            "iterations": result["iterations"],
            "worst_scenario": result["incumbent"]["oracle"]["worst_scenario"],
        })
        print(f"{simulation_id} A1=certified objective={a1_objective:.12g}", flush=True)

    _write_csv(OUTPUT / "case_results.csv", rows)
    summary = {
        "scope": "LAYER_A_T2_A1_NUMERICAL_REGRESSION",
        "status": "PASS",
        "case_count": len(rows),
        "case_ids": list(FAILURE_IDS),
        "input_hashes_unchanged": all(row["input_sha256"] == baseline[row["simulation_id"]]["input_sha256"] for row in rows),
        "a1_certified": sum(row["a1_status"] == "certified" for row in rows),
        "a1_a0_objectives_within_frozen_tolerance": True,
        "a1_ef_objectives_within_frozen_tolerance": True,
        "cases": rows,
    }
    summary["summary_sha256"] = canonical_json_sha256(summary)
    _write_json(OUTPUT / "summary.json", summary)
    manifest = {
        "schema_version": 1,
        "scope": "LAYER_A_T2_A1_NUMERICAL_REGRESSION",
        "status": "PASS",
        "execution_git_commit": commit,
        "execution_git_tree": tree,
        "environment": environment,
        "model_kind": "M2",
        "algorithm_kind": "A1_full",
        "source_sample_table_sha256": sha256_file(ROOT / "simulation_results/qfr_mechanism_layer_a_n1000/samples.csv"),
        "source_t1_case_results_sha256": sha256_file(T1 / "case_results.csv"),
        "case_ids": list(FAILURE_IDS),
        "guardrails": {
            "input_changed": False,
            "model_formula_changed": False,
            "scientific_parameters_changed": False,
            "a1_search_changed": False,
            "stopping_or_certification_changed": False,
            "solver_policy_changed": False,
            "global_tolerance_changed": False,
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
