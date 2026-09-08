"""Post-fix replay gates for the Rawls24 Layer A numerical repair."""

from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from robust_budget_allocation.algorithms.qfr_a1_verification import validate_improved_ccg_result  # noqa: E402
from robust_budget_allocation.algorithms.qfr_extensive_form import solve_qfr_extensive_form  # noqa: E402
from robust_budget_allocation.algorithms.qfr_improved_ccg import solve_qfr_improved_ccg  # noqa: E402
from robust_budget_allocation.algorithms.qfr_protocol import tolerance  # noqa: E402
from robust_budget_allocation.algorithms.qfr_standard_ccg import solve_qfr_standard_ccg  # noqa: E402
from robust_budget_allocation.io.hashing import canonical_json_sha256, sha256_file  # noqa: E402
from robust_budget_allocation.simulation.layer_a import (  # noqa: E402
    classify_policy,
    data_for_sample,
    load_config,
    load_rawls24_neutral_fixture,
)
from qfr_mechanism_layer_a import ITEMS, _active_level, _read_samples  # noqa: E402


CONFIG = ROOT / "configs/qfr_mechanism_layer_a_rawls24_v1.json"
SOURCE = ROOT / "simulation_results/qfr_mechanism_layer_a_rawls24_n1000"
FAILURE_OUTPUT = ROOT / "simulation_results/qfr_mechanism_layer_a_rawls24_121_replay_post_fix"
SUCCESS_OUTPUT = ROOT / "simulation_results/qfr_mechanism_layer_a_rawls24_879_nonregression_post_fix"


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def _write_csv(path: Path, rows: list[Mapping[str, Any]]) -> None:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    path.write_bytes(stream.getvalue().encode("utf-8"))


def _write_raw(path: Path, payload: Mapping[str, Any]) -> None:
    raw = (json.dumps(payload, sort_keys=True) + "\n").encode("utf-8")
    with path.open("wb") as handle, gzip.GzipFile(filename="", mode="wb", fileobj=handle, mtime=0) as compressed:
        compressed.write(raw)


def _load_old_raw() -> dict[str, dict[str, Any]]:
    result = {}
    for shard in sorted((SOURCE / "raw_a1").glob("*.jsonl.gz")):
        with gzip.open(shard, "rt", encoding="utf-8") as handle:
            for line in handle:
                row = json.loads(line)
                result[row["simulation_id"]] = row
    if len(result) != 1000:
        raise RuntimeError("old Rawls24 raw result identity is not exactly N=1000")
    return result


def _first_stage_values(first: Mapping[str, Any]) -> dict[str, float]:
    values = {f"Q::{item}": float(first["q"][item]) for item in ITEMS}
    for item in ITEMS:
        for level, value in first["f"][item].items():
            values[f"F::{item}::{level}"] = float(value)
        for level, value in first["z"][item].items():
            values[f"z::{item}::{level}"] = float(value)
    return values


def _common():
    config = load_config(CONFIG)
    samples = {row["simulation_id"]: row for row in _read_samples(SOURCE / "samples.csv")}
    neutral, fixture = load_rawls24_neutral_fixture(ROOT, config)
    old_raw = _load_old_raw()
    with (SOURCE / "scientific_results.csv").open("r", encoding="utf-8", newline="") as handle:
        old_scientific = {row["simulation_id"]: row for row in csv.DictReader(handle)}
    if set(samples) != set(old_raw) or set(samples) != set(old_scientific):
        raise RuntimeError("sample/result traceability mismatch")
    return config, samples, neutral, fixture, old_raw, old_scientific


def _manifest(scope: str, ids: list[str], fixture: Mapping[str, Any]) -> dict[str, Any]:
    payload = {
        "scope": scope,
        "execution_git_commit": _git("rev-parse", "HEAD"),
        "execution_git_tree": _git("rev-parse", "HEAD^{tree}"),
        "sample_table_sha256": sha256_file(SOURCE / "samples.csv"),
        "source_manifest_sha256": sha256_file(SOURCE / "simulation_manifest.json"),
        "neutral_fixture_sha256": fixture["neutral_fixture_sha256"],
        "case_ids": ids,
        "model_kind": "M2",
        "algorithm_kind": "A1_full",
        "guardrails": {
            "input_changed": False,
            "scientific_model_changed": False,
            "scientific_parameters_changed": False,
            "a1_search_changed": False,
            "stopping_or_certification_changed": False,
            "solver_policy_changed": False,
            "resampling": False,
        },
    }
    payload["manifest_sha256"] = canonical_json_sha256(payload)
    return payload


def _finish(output: Path, rows: list[dict[str, Any]], summary: dict[str, Any], manifest: dict[str, Any]) -> None:
    _write_csv(output / "case_results.csv", rows)
    summary["summary_sha256"] = canonical_json_sha256(summary)
    _write_json(output / "summary.json", summary)
    _write_json(output / "manifest.json", manifest)
    paths = sorted(path for path in output.rglob("*") if path.is_file() and path.name != "HASHES.sha256")
    (output / "HASHES.sha256").write_text(
        "\n".join(f"{sha256_file(path)}  {path.relative_to(output).as_posix()}" for path in paths) + "\n",
        encoding="utf-8", newline="\n",
    )


def replay_failures() -> int:
    if FAILURE_OUTPUT.exists():
        raise RuntimeError("non-overwrite 121-case replay output already exists")
    _, samples, neutral, fixture, old_raw, old_scientific = _common()
    ids = sorted(key for key, row in old_scientific.items() if row["status"] == "FAILED")
    if len(ids) != 121:
        raise RuntimeError("pre-fix failure set is not exactly 121")
    FAILURE_OUTPUT.mkdir(parents=True)
    raw_dir = FAILURE_OUTPUT / "raw"
    raw_dir.mkdir()
    rows = []
    remaining = []
    for index, simulation_id in enumerate(ids, start=1):
        sample = samples[simulation_id]
        if sample["input_sha256"] != old_raw[simulation_id]["input"]["input_sha256"]:
            raise RuntimeError(f"input hash changed for {simulation_id}")
        data = data_for_sample(neutral, fixture["metadata"], sample)
        try:
            result = solve_qfr_improved_ccg(data, "M2", memory_phase_enabled=True)
            if result["status"] == "certified":
                validate_improved_ccg_result(data, result)
            a1_status, diagnostic = result["status"], result["diagnostic"]
        except Exception as exc:
            result = None
            a1_status, diagnostic = "exception", f"{type(exc).__name__}: {exc}"
        a0 = ef = None
        if a1_status != "certified":
            remaining.append(simulation_id)
            a0 = solve_qfr_standard_ccg(data, "M2")
            ef = solve_qfr_extensive_form(data, "M2")
        rows.append({
            "simulation_id": simulation_id,
            "input_sha256": sample["input_sha256"],
            "pre_fix_status": old_scientific[simulation_id]["failure_type"],
            "pre_fix_diagnostic": old_scientific[simulation_id]["failure_message"],
            "post_fix_A1_status": a1_status,
            "post_fix_A1_diagnostic": diagnostic or "",
            "post_fix_A1_objective": "" if result is None or result["objective"] is None else result["objective"],
            "post_fix_A1_certificate": "PASS" if a1_status == "certified" else "FAIL",
            "post_fix_worst_scenario": "" if a1_status != "certified" else result["incumbent"]["oracle"]["worst_scenario"],
            "post_fix_iterations": "" if result is None else result["iterations"],
            "A0_status_if_needed": "not_needed" if a0 is None else a0["status"],
            "A0_objective_if_needed": "" if a0 is None else a0["objective"],
            "EF_status_if_needed": "not_needed" if ef is None else ef["status"],
            "EF_objective_if_needed": "" if ef is None else ef["objective"],
        })
        _write_raw(raw_dir / f"{simulation_id}.json.gz", {
            "simulation_id": simulation_id, "input": sample, "data_sha256": data.data_sha256,
            "pre_fix": old_scientific[simulation_id], "post_fix_A1": result,
            "A0_if_needed": a0, "EF_if_needed": ef,
        })
        if index % 20 == 0:
            print(f"121-case replay {index}/121 certified={index-len(remaining)} failed={len(remaining)}", flush=True)
    summary = {
        "scope": "RAWLS24_LAYER_A_121_FAILURE_REPLAY_POST_FIX",
        "requested": 121, "attempted": 121,
        "certified": sum(row["post_fix_A1_status"] == "certified" for row in rows),
        "failed": len(remaining), "remaining_failure_ids": remaining,
        "input_hashes_unchanged": True,
        "status": "PASS" if not remaining else "FAIL_REMAINING_CASES_REQUIRE_A0_EF_REVIEW",
    }
    _finish(FAILURE_OUTPUT, rows, summary, _manifest(summary["scope"], ids, fixture))
    print(json.dumps(summary, indent=2))
    return 0 if not remaining else 1


def replay_successes() -> int:
    if SUCCESS_OUTPUT.exists():
        raise RuntimeError("non-overwrite 879-case non-regression output already exists")
    _, samples, neutral, fixture, old_raw, old_scientific = _common()
    ids = sorted(key for key, row in old_scientific.items() if row["status"] == "SUCCESS")
    if len(ids) != 879:
        raise RuntimeError("pre-fix successful set is not exactly 879")
    SUCCESS_OUTPUT.mkdir(parents=True)
    rows = []
    failures = []
    max_objective_difference = 0.0
    max_first_stage_difference = 0.0
    for index, simulation_id in enumerate(ids, start=1):
        sample = samples[simulation_id]
        old_result = old_raw[simulation_id]["a1_result"]
        old_first = old_result["incumbent"]["first_stage"]
        data = data_for_sample(neutral, fixture["metadata"], sample)
        result = solve_qfr_improved_ccg(data, "M2", memory_phase_enabled=True)
        passed = result["status"] == "certified"
        reason = []
        if passed:
            validate_improved_ccg_result(data, result)
            new_first = result["incumbent"]["first_stage"]
            objective_difference = abs(float(result["objective"]) - float(old_result["objective"]))
            objective_threshold = tolerance(float(result["objective"]), float(old_result["objective"]))
            max_objective_difference = max(max_objective_difference, objective_difference)
            if objective_difference > objective_threshold:
                passed = False; reason.append("objective")
            old_values, new_values = _first_stage_values(old_first), _first_stage_values(new_first)
            decision_difference = max(abs(new_values[key] - old_values[key]) for key in old_values)
            decision_ok = all(abs(new_values[key] - old_values[key]) <= tolerance(new_values[key], old_values[key]) for key in old_values)
            max_first_stage_difference = max(max_first_stage_difference, decision_difference)
            if not decision_ok:
                passed = False; reason.append("first_stage")
            new_policy = classify_policy(new_first, 1e-7)
            old_policy = old_scientific[simulation_id]["policy_label"]
            if new_policy != old_policy:
                passed = False; reason.append("policy")
            new_levels = {item: _active_level(new_first, item, 1e-7) for item in ITEMS}
            old_levels = {item: old_scientific[simulation_id][f"R_{item}"] for item in ITEMS}
            if new_levels != old_levels:
                passed = False; reason.append("R_level")
            new_worst = result["incumbent"]["oracle"]["worst_scenario"]
            old_worst = old_scientific[simulation_id]["worst_scenario"]
            if new_worst != old_worst:
                passed = False; reason.append("worst_scenario")
        else:
            objective_difference = decision_difference = objective_threshold = float("nan")
            new_policy = new_worst = "unavailable"
            new_levels = dict.fromkeys(ITEMS, "unavailable")
            reason.append(result["status"])
        if not passed:
            failures.append(simulation_id)
        rows.append({
            "simulation_id": simulation_id,
            "input_sha256": sample["input_sha256"],
            "post_fix_certified": result["status"] == "certified",
            "non_regression_pass": passed,
            "difference_reason": ";".join(reason),
            "old_objective": old_result["objective"],
            "new_objective": result["objective"],
            "objective_absolute_difference": objective_difference,
            "objective_tolerance": objective_threshold,
            "max_first_stage_absolute_difference": decision_difference,
            "old_policy": old_scientific[simulation_id]["policy_label"],
            "new_policy": new_policy,
            "old_worst_scenario": old_scientific[simulation_id]["worst_scenario"],
            "new_worst_scenario": new_worst,
            **{f"old_R_{item}": old_scientific[simulation_id][f"R_{item}"] for item in ITEMS},
            **{f"new_R_{item}": new_levels[item] for item in ITEMS},
            "new_result_sha256": result["result_sha256"],
        })
        if index % 50 == 0:
            print(f"879-case non-regression {index}/879 pass={index-len(failures)} fail={len(failures)}", flush=True)
    summary = {
        "scope": "RAWLS24_LAYER_A_879_SUCCESS_NON_REGRESSION_POST_FIX",
        "requested": 879, "attempted": 879,
        "certified": sum(row["post_fix_certified"] for row in rows),
        "non_regression_pass": sum(row["non_regression_pass"] for row in rows),
        "failed": len(failures), "failure_ids": failures,
        "max_objective_absolute_difference": max_objective_difference,
        "max_first_stage_absolute_difference": max_first_stage_difference,
        "status": "PASS" if not failures else "FAIL_SCIENTIFIC_DRIFT",
    }
    _finish(SUCCESS_OUTPUT, rows, summary, _manifest(summary["scope"], ids, fixture))
    print(json.dumps(summary, indent=2))
    return 0 if not failures else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("failures", "successes"))
    args = parser.parse_args()
    return replay_failures() if args.command == "failures" else replay_successes()


if __name__ == "__main__":
    raise SystemExit(main())
