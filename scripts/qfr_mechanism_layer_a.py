"""Prepare or run the Q-F-R Layer A N=1000 production-A1 simulation."""

from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import math
from pathlib import Path
import subprocess
import sys
import traceback
from typing import Any, Mapping, Sequence

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from robust_budget_allocation.algorithms.qfr_a1_verification import validate_improved_ccg_result  # noqa: E402
from robust_budget_allocation.algorithms.qfr_improved_ccg import solve_qfr_improved_ccg  # noqa: E402
from robust_budget_allocation.io.hashing import canonical_json_sha256, sha256_bytes, sha256_file  # noqa: E402
from robust_budget_allocation.runtime.environment import ensure_preflight_once  # noqa: E402
from robust_budget_allocation.simulation.layer_a import (  # noqa: E402
    ITEMS, PARAMETERS, POLICY_LABELS, classify_policy, data_for_sample,
    generate_samples, load_config, load_neutral_fixture, samples_csv_bytes,
    validate_output_traceability, validate_samples,
)


CONFIG_PATH = ROOT / "configs/qfr_mechanism_layer_a_v1.json"
OUTPUT = ROOT / "simulation_results/qfr_mechanism_layer_a_n1000"


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def _read_samples(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
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


def prepare() -> int:
    config = load_config(CONFIG_PATH)
    rows = generate_samples(config)
    validation = validate_samples(rows, config)
    if rows != generate_samples(config):
        raise RuntimeError("same-seed sample reproduction failed")
    OUTPUT.mkdir(parents=True, exist_ok=False)
    (OUTPUT / "samples.csv").write_bytes(samples_csv_bytes(rows))
    _write_json(OUTPUT / "sampler_validation.json", validation)
    neutral, fixture = load_neutral_fixture(ROOT, config)
    pre_manifest = {
        "scope": config["scope"],
        "status": "PREPARED_VALIDATED_NOT_YET_EXECUTED",
        "config_file": CONFIG_PATH.relative_to(ROOT).as_posix(),
        "config_file_sha256": sha256_file(CONFIG_PATH),
        "config_identity_sha256": canonical_json_sha256(config),
        "sample_table_sha256": sha256_file(OUTPUT / "samples.csv"),
        "sampler_validation_sha256": validation["validation_sha256"],
        "fixture": fixture,
        "neutral_qfr_data_sha256": canonical_json_sha256(neutral),
        "requested_draws": len(rows),
    }
    pre_manifest["manifest_sha256"] = canonical_json_sha256(pre_manifest)
    _write_json(OUTPUT / "pre_run_manifest.json", pre_manifest)
    print(json.dumps({"status": "PASS", "samples": len(rows), "sample_table_sha256": pre_manifest["sample_table_sha256"]}, indent=2))
    return 0


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()


def _active_level(first: Mapping[str, Any], item: str, tolerance: float) -> str:
    active = [int(level) for level, value in first["f"][item].items() if float(value) > tolerance]
    return "NONE" if not active else f"R{max(active)}"


def _sum_solver_runtime(result: Mapping[str, Any]) -> float:
    total = 0.0
    for row in result.get("trace", []):
        master = row.get("master") or {}
        total += float((master.get("solver") or {}).get("runtime_seconds") or 0.0)
        for phase_name in ("memory", "candidate"):
            phase = row.get(phase_name) or {}
            for evaluation in phase.get("evaluations", []):
                total += float((evaluation.get("solver") or {}).get("runtime_seconds") or 0.0)
        oracle = row.get("full_exact_certification") or {}
        for evaluation in oracle.get("results", []):
            total += float((evaluation.get("solver") or {}).get("runtime_seconds") or 0.0)
    return total


def _success_rows(
    sample: Mapping[str, Any], data, result: Mapping[str, Any], common: Mapping[str, Any],
    scenario_metadata: Mapping[str, Any], tolerance: float,
) -> tuple[dict[str, Any], dict[str, Any]]:
    validate_improved_ccg_result(data, result)
    incumbent = result["incumbent"]
    first, oracle = incumbent["first_stage"], incumbent["oracle"]
    worst_id = str(oracle["worst_scenario"])
    worst = next(row for row in oracle["results"] if row["scenario_id"] == worst_id)
    q = {item: float(first["q"][item]) for item in ITEMS}
    f_by_level = {
        item: {int(level): float(value) for level, value in first["f"][item].items()}
        for item in ITEMS
    }
    f = {item: sum(f_by_level[item].values()) for item in ITEMS}
    r_level = {item: _active_level(first, item, tolerance) for item in ITEMS}
    c_q = sum((data.q_unit_cost[item] + data.storage_cost[item] * data.tau) * q[item] for item in ITEMS)
    c_f = sum(data.reservation_cost[item] * f[item] for item in ITEMS)
    c_r = sum(data.reliability_cost[item][level] * value for item in ITEMS for level, value in f_by_level[item].items())
    worst_exercise = {item: float(worst["exercise"][item]) for item in ITEMS}
    worst_shortage = {item: float(worst["shortage"][item]) for item in ITEMS}
    scientific: dict[str, Any] = {
        **common, **sample, "status": "SUCCESS", "failure_type": "", "failure_message": "",
        "data_sha256": data.data_sha256, "scenario_sha256": data.scenario_sha256,
        "objective_T_COST": float(result["objective"]), "policy_label": classify_policy(first, tolerance),
        **{f"Q_{item}": q[item] for item in ITEMS},
        **{f"F_{item}": f[item] for item in ITEMS},
        **{f"R_{item}": r_level[item] for item in ITEMS},
        "C_Q": c_q, "C_F": c_f, "C_R": c_r, "first_stage_cost": c_q + c_f + c_r,
        "worst_scenario": worst_id, "worst_category": scenario_metadata[worst_id]["category"],
        "worst_exercise_cost": float(worst["exercise_cost"]),
        "worst_shortage_penalty": float(worst["shortage_loss"]),
        "worst_total_shortage": sum(worst_shortage.values()),
        "worst_total_F_exercise": sum(worst_exercise.values()),
        "budget_usage": (c_q + c_f + c_r + float(worst["exercise_cost"])) / data.budget,
        **{f"worst_exercise_{item}": worst_exercise[item] for item in ITEMS},
        **{f"worst_shortage_{item}": worst_shortage[item] for item in ITEMS},
        "convergence_status": result["status"], "certificate_status": "PASS",
        "a1_result_sha256": result["result_sha256"], "first_stage_sha256": incumbent["first_stage_sha256"],
        "oracle_sha256": oracle["oracle_sha256"],
    }
    final_trace = result["trace"][-1]
    computational = {
        "simulation_id": sample["simulation_id"], "sample_index": sample["sample_index"],
        "status": "SUCCESS", "failure_type": "", "failure_message": "",
        "total_runtime_seconds": float(result["runtime_seconds"]),
        "solver_runtime_seconds": _sum_solver_runtime(result),
        "iterations": int(result["iterations"]),
        "memory_opportunities": int(result["memory_opportunities"]),
        "memory_hits": int(result["memory_hits"]),
        "candidate_hits": int(result["candidate_hits"]),
        "candidate_scenarios_planned": sum(len((row.get("candidate") or {}).get("planned", [])) for row in result["trace"]),
        "active_scenario_count": len(result["additions"]),
        "full_exact_certification_calls": int(result["full_exact_certification_calls"]),
        "complete_full_exact_certification_calls": int(result["complete_full_exact_certification_calls"]),
        "scenario_evaluations": int(result["scenario_evaluations"]),
        "final_LB": float(result["LB"]), "final_UB": float(result["UB"]),
        "final_gap": max(0.0, float(result["UB"]) - float(result["LB"])),
        "convergence_status": result["status"], "certificate_status": "PASS",
        "worst_scenario": worst_id, "numerical_status": "PASS",
        "timeout_status": "unavailable", "incumbent_first_stage_sha256": incumbent["first_stage_sha256"],
        "full_exact_oracle_sha256": oracle["oracle_sha256"],
        "final_convergence_owned_by_full_exact": final_trace["full_exact_certification"] is not None and final_trace["convergence"] is True,
    }
    return scientific, computational


def _failure_rows(sample: Mapping[str, Any], common: Mapping[str, Any], failure_type: str, message: str) -> tuple[dict[str, Any], dict[str, Any]]:
    scientific = {**common, **sample, "status": "FAILED", "failure_type": failure_type, "failure_message": message}
    computational = {
        "simulation_id": sample["simulation_id"], "sample_index": sample["sample_index"],
        "status": "FAILED", "failure_type": failure_type, "failure_message": message,
        "total_runtime_seconds": "unavailable", "solver_runtime_seconds": "unavailable",
        "iterations": "unavailable", "memory_opportunities": "unavailable", "memory_hits": "unavailable",
        "candidate_hits": "unavailable", "candidate_scenarios_planned": "unavailable",
        "active_scenario_count": "unavailable", "full_exact_certification_calls": "unavailable",
        "complete_full_exact_certification_calls": "unavailable", "scenario_evaluations": "unavailable",
        "final_LB": "unavailable", "final_UB": "unavailable", "final_gap": "unavailable",
        "convergence_status": "FAILED", "certificate_status": "FAILED", "worst_scenario": "unavailable",
        "numerical_status": "unavailable", "timeout_status": "unavailable",
        "incumbent_first_stage_sha256": "unavailable", "full_exact_oracle_sha256": "unavailable",
        "final_convergence_owned_by_full_exact": False,
    }
    return scientific, computational


def _csv_bytes(rows: Sequence[Mapping[str, Any]]) -> bytes:
    fields = list(dict.fromkeys(key for row in rows for key in row))
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def _distribution(values: Sequence[float], *, p99: bool = False) -> dict[str, float]:
    array = np.asarray(values, dtype=float)
    result = {
        "min": float(np.min(array)), "median": float(np.median(array)),
        "mean": float(np.mean(array)), "P90": float(np.quantile(array, 0.90)),
        "P95": float(np.quantile(array, 0.95)), "max": float(np.max(array)),
    }
    if p99:
        result["P99"] = float(np.quantile(array, 0.99))
    return result


def run() -> int:
    config = load_config(CONFIG_PATH)
    sample_path = OUTPUT / "samples.csv"
    if not sample_path.exists() or (OUTPUT / "simulation_manifest.json").exists():
        raise RuntimeError("prepared sample table missing or simulation already finalized")
    raw_dir = OUTPUT / "raw_a1"
    raw_dir.mkdir(exist_ok=False)
    samples = _read_samples(sample_path)
    generated = generate_samples(config)
    if samples != generated or validate_samples(samples, config)["status"] != "PASS":
        raise RuntimeError("stored sample table does not reproduce exactly")
    neutral_payload, fixture = load_neutral_fixture(ROOT, config)
    environment = ensure_preflight_once().to_dict()
    execution_commit, execution_tree = _git("rev-parse", "HEAD"), _git("rev-parse", "HEAD^{tree}")
    if _git("status", "--porcelain=v1"):
        raise RuntimeError("simulation execution requires a clean committed implementation")
    common = {
        "model_kind": "M2", "algorithm_kind": "A1_full", "budget": fixture["budget"],
        "shortage_beta": config["fixed_environment"]["shortage_beta"],
        "demand_scale_gamma_D": config["fixed_environment"]["demand_scale_gamma_D"],
        "demand_scale": json.dumps(fixture["demand_scale"], sort_keys=True),
        "h": 0.0, "a": 1.0,
        "simulation_config_sha256": canonical_json_sha256(config),
        "sample_table_sha256": sha256_file(sample_path),
        "execution_git_commit": execution_commit, "execution_git_tree": execution_tree,
    }
    scientific_rows, computational_rows = [], []
    shard_size = int(config["raw_result_shard_size"])
    raw_buffer: list[dict[str, Any]] = []
    shard_index = 0
    for index, sample in enumerate(samples, 1):
        raw_record: dict[str, Any] = {"simulation_id": sample["simulation_id"], "input": sample}
        try:
            data = data_for_sample(neutral_payload, fixture["metadata"], sample)
            result = solve_qfr_improved_ccg(data, "M2", memory_phase_enabled=True)
            raw_record["a1_result"] = result
            if result["status"] != "certified":
                sci, comp = _failure_rows(sample, common, str(result["status"]), str(result["diagnostic"]))
            else:
                sci, comp = _success_rows(
                    sample, data, result, common, fixture["metadata"],
                    float(config["policy_tolerance"]),
                )
        except Exception as exc:  # every original draw is retained; never resampled
            raw_record.update(exception_type=type(exc).__name__, exception_message=str(exc), traceback=traceback.format_exc())
            sci, comp = _failure_rows(sample, common, type(exc).__name__, str(exc))
        raw_record["scientific_row_status"] = sci["status"]
        raw_buffer.append(raw_record)
        scientific_rows.append(sci)
        computational_rows.append(comp)
        if len(raw_buffer) == shard_size or index == len(samples):
            shard_index += 1
            path = raw_dir / f"a1_results_{shard_index:03d}.jsonl.gz"
            raw_bytes = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in raw_buffer).encode("utf-8")
            with path.open("wb") as handle, gzip.GzipFile(filename="", mode="wb", fileobj=handle, mtime=0) as compressed:
                compressed.write(raw_bytes)
            raw_buffer.clear()
        if index % 25 == 0:
            print(f"progress {index}/1000 success={sum(r['status']=='SUCCESS' for r in scientific_rows)} failed={sum(r['status']=='FAILED' for r in scientific_rows)}", flush=True)
    validate_output_traceability(samples, scientific_rows, computational_rows)
    successes = [row for row in scientific_rows if row["status"] == "SUCCESS"]
    failures = [row for row in scientific_rows if row["status"] == "FAILED"]
    diagnostics_ok = [row for row in computational_rows if row["status"] == "SUCCESS"]
    policy_counts = {label: sum(row["policy_label"] == label for row in successes) for label in POLICY_LABELS}
    summary = {
        "simulation": {"requested": 1000, "attempted": len(scientific_rows), "successful": len(successes), "failed": len(failures), "certified": sum(row.get("certificate_status") == "PASS" for row in successes)},
        "policy_counts": policy_counts,
        "scientific": ({
            "objective": _distribution([row["objective_T_COST"] for row in successes]),
            "worst_total_shortage": _distribution([row["worst_total_shortage"] for row in successes]),
            "budget_usage": _distribution([row["budget_usage"] for row in successes]),
            "worst_total_F_exercise": _distribution([row["worst_total_F_exercise"] for row in successes]),
            "R_level_item_counts": {level: sum(row[f"R_{item}"] == level for row in successes for item in ITEMS) for level in ("NONE", "R0", "R1", "R2")},
        } if successes else "unavailable"),
        "computational": ({
            "runtime_seconds": _distribution([row["total_runtime_seconds"] for row in diagnostics_ok], p99=True),
            "solver_runtime_seconds": _distribution([row["solver_runtime_seconds"] for row in diagnostics_ok], p99=True),
            "iterations": _distribution([row["iterations"] for row in diagnostics_ok], p99=True),
            "certification_success_rate": len(successes) / len(scientific_rows),
            "memory_opportunities_total": sum(row["memory_opportunities"] for row in diagnostics_ok),
            "memory_hits_total": sum(row["memory_hits"] for row in diagnostics_ok),
            "candidate_hits_total": sum(row["candidate_hits"] for row in diagnostics_ok),
            "candidate_scenarios_planned_total": sum(row["candidate_scenarios_planned"] for row in diagnostics_ok),
            "full_exact_certification_calls_total": sum(row["full_exact_certification_calls"] for row in diagnostics_ok),
            "complete_full_exact_certification_calls_total": sum(row["complete_full_exact_certification_calls"] for row in diagnostics_ok),
            "scenario_evaluations_total": sum(row["scenario_evaluations"] for row in diagnostics_ok),
            "failure_types": {kind: sum(row["failure_type"] == kind for row in failures) for kind in sorted({row["failure_type"] for row in failures})},
        } if diagnostics_ok else "unavailable"),
        "interpretation_boundary": "DESCRIPTIVE_A1_BEHAVIOR_ONLY_NO_A0_COMPARATOR_NO_CAUSAL_SPEEDUP_CLAIM",
    }
    summary["summary_sha256"] = canonical_json_sha256(summary)
    scientific_bytes, computational_bytes = _csv_bytes(scientific_rows), _csv_bytes(computational_rows)
    (OUTPUT / "scientific_results.csv").write_bytes(scientific_bytes)
    (OUTPUT / "a1_computational_diagnostics.csv").write_bytes(computational_bytes)
    _write_json(OUTPUT / "summary.json", summary)
    manifest = {
        "schema_version": 1, "scope": config["scope"], "status": "COMPLETE",
        "execution_git_commit": execution_commit, "execution_git_tree": execution_tree,
        "environment": environment, "config_identity_sha256": canonical_json_sha256(config),
        "sample_table_sha256": sha256_file(sample_path), "fixture": fixture,
        "requested_draws": 1000, "attempted_draws": len(scientific_rows),
        "successful_draws": len(successes), "failed_draws": len(failures),
        "raw_result_shards": shard_index, "policy_tolerance": config["policy_tolerance"],
        "model_kind": "M2", "algorithm_kind": "A1_full",
        "guardrails": {
            "model_changed": False, "algorithm_changed": False, "solver_policy_changed": False,
            "environment_changed": False, "formal_data_changed": False, "parameter_tuning": False,
            "layer_b_executed": False, "layer_c_executed": False, "formal_e1_e5_executed": False,
            "figures_generated": False,
        },
    }
    manifest["manifest_sha256"] = canonical_json_sha256(manifest)
    _write_json(OUTPUT / "simulation_manifest.json", manifest)
    output_paths = sorted(path for path in OUTPUT.rglob("*") if path.is_file() and path.name != "HASHES.sha256")
    (OUTPUT / "HASHES.sha256").write_text(
        "\n".join(f"{sha256_file(path)}  {path.relative_to(OUTPUT).as_posix()}" for path in output_paths) + "\n",
        encoding="utf-8", newline="\n",
    )
    print(json.dumps(summary, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("prepare", "run"))
    args = parser.parse_args()
    return prepare() if args.command == "prepare" else run()


if __name__ == "__main__":
    raise SystemExit(main())
