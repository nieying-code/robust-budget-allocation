#!/usr/bin/env python
"""Preflight, run, and finalize the frozen Formal E2-A experiment."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import traceback

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from robust_budget_allocation.algorithms.qfr_final_a1 import (  # noqa: E402
    FINAL_A1_IDENTITY,
    solve_qfr_final_a1,
)
from robust_budget_allocation.formal.e2a import (  # noqa: E402
    BASELINE_RELATIVE,
    CASES,
    DESIGN_RELATIVE,
    SAMPLE_SHA256,
    SAMPLES_RELATIVE,
    baseline_identity_preflight,
    csv_bytes,
    data_for_case_sample,
    load_base_fixture,
    load_baseline,
    load_samples,
    paired_rows,
    read_csv,
    serialize_result,
    summarize_case,
    summarize_paired,
)
from robust_budget_allocation.io.atomic import (  # noqa: E402
    atomic_write_json,
    atomic_write_text,
)
from robust_budget_allocation.io.hashing import sha256_file  # noqa: E402


OUTPUT = ROOT / "formal_results/e2_final/e2a"


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(csv_bytes(rows))
    temporary.replace(path)


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def preflight() -> int:
    report = baseline_identity_preflight(ROOT)
    report.update(
        schema_version=1,
        scope="FORMAL_E2A_PREFLIGHT_V1",
        design_path=DESIGN_RELATIVE.as_posix(),
        design_sha256=sha256_file(ROOT / DESIGN_RELATIVE),
        samples_path=SAMPLES_RELATIVE.as_posix(),
        baseline_path=BASELINE_RELATIVE.as_posix(),
        baseline_sha256=sha256_file(ROOT / BASELINE_RELATIVE),
        git_commit=_git("rev-parse", "HEAD"),
        git_tree=_git("rev-parse", "HEAD^{tree}"),
        scientific_optimizations_completed=0,
    )
    OUTPUT.mkdir(parents=True, exist_ok=True)
    atomic_write_json(OUTPUT / "preflight.json", report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


def _failed_row(case_id: str, sample: dict[str, object], error: BaseException) -> dict[str, object]:
    row: dict[str, object] = {
        "case_id": case_id,
        "simulation_id": sample["simulation_id"],
        "sample_index": sample["sample_index"],
        "input_sha256": sample["input_sha256"],
        "model_kind": "M2",
        "algorithm_identity": FINAL_A1_IDENTITY,
        "status": "exception",
        "certificate_status": "FAIL",
        "failure_type": type(error).__name__,
        "failure_message": str(error),
        "traceback": "".join(traceback.format_exception(error)),
    }
    return row


def run_case(case_id: str) -> int:
    if case_id not in CASES:
        raise ValueError(f"unknown case {case_id}")
    baseline_identity_preflight(ROOT)
    samples = load_samples(ROOT)
    payload, metadata = load_base_fixture(ROOT)
    path = OUTPUT / f"{case_id}.csv"
    existing = read_csv(path) if path.exists() else []
    if [row["simulation_id"] for row in existing] != [row["simulation_id"] for row in samples[:len(existing)]]:
        raise RuntimeError(f"{case_id} checkpoint is not an exact sample prefix")
    rows: list[dict[str, object]] = list(existing)
    for position, sample in enumerate(samples[len(rows):], len(rows) + 1):
        try:
            data = data_for_case_sample(payload, metadata, case_id, sample)
            solved = solve_qfr_final_a1(data, "M2")
            row = serialize_result(case_id, sample, data, metadata, solved)
        except BaseException as error:  # retain every failed scientific draw
            row = _failed_row(case_id, sample, error)
        rows.append(row)
        if position % 10 == 0 or position == 1000:
            _write_csv(path, rows)
            certified = sum(value.get("certificate_status") == "PASS" for value in rows)
            print(f"{case_id}: {position}/1000 attempted, {certified} certified", flush=True)
    return 0


def finalize() -> int:
    preflight_report = baseline_identity_preflight(ROOT)
    baseline = load_baseline(ROOT)
    all_rows: list[dict[str, object]] = []
    all_pairs: list[dict[str, object]] = []
    case_summaries: dict[str, object] = {}
    paired_summaries: dict[str, object] = {}
    for case_id in CASES:
        path = OUTPUT / f"{case_id}.csv"
        rows = read_csv(path)
        if len(rows) != 1000 or [row["simulation_id"] for row in rows] != [f"LA-{index:04d}" for index in range(1, 1001)]:
            raise RuntimeError(f"{case_id} does not contain the exact 1000 frozen rows")
        pairs = paired_rows(rows, baseline)
        all_rows.extend(rows)
        all_pairs.extend(pairs)
        case_summaries[case_id] = summarize_case(rows)
        paired_summaries[case_id] = summarize_paired(pairs)
    _write_csv(OUTPUT / "e2a_scientific_results.csv", all_rows)
    _write_csv(OUTPUT / "e2a_paired_baseline_comparison.csv", all_pairs)
    failures = [row for row in all_rows if row["certificate_status"] != "PASS"]
    if failures:
        _write_csv(OUTPUT / "e2a_retained_failures.csv", failures)
    summary = {
        "schema_version": 1,
        "scope": "FORMAL_E2A_COMMODITY_HETEROGENEITY_MECHANISM_TEST_V1",
        "requested_new_scientific_optimizations": 4000,
        "attempted_new_scientific_optimizations": len(all_rows),
        "certified": sum(row["certificate_status"] == "PASS" for row in all_rows),
        "failed": sum(row["certificate_status"] != "PASS" for row in all_rows),
        "baseline_reused": 1000,
        "baseline_rerun": False,
        "sample_sha256": SAMPLE_SHA256,
        "algorithm_identity": FINAL_A1_IDENTITY,
        "cases": case_summaries,
        "paired": paired_summaries,
        "E2_B_runs": 0,
        "E2_C_runs": 0,
        "E2_D_runs": 0,
    }
    atomic_write_json(OUTPUT / "e2a_summary.json", summary)
    atomic_write_json(
        OUTPUT / "e2a_policy_summary.json",
        {case_id: value["policy_counts"] for case_id, value in case_summaries.items()},
    )
    atomic_write_json(
        OUTPUT / "e2a_commodity_summary.json",
        {case_id: value["commodity"] for case_id, value in case_summaries.items()},
    )
    atomic_write_json(
        OUTPUT / "e2a_certification_summary.json",
        {
            "attempted": len(all_rows),
            "certified": summary["certified"],
            "failed": summary["failed"],
            "by_case": {
                case_id: {
                    "requested": value["requested"],
                    "certified": value["certified"],
                    "failed": value["failed"],
                    "failure_types": value["failure_types"],
                }
                for case_id, value in case_summaries.items()
            },
            "failures_retained": True,
            "resampled_or_replaced": False,
        },
    )
    manifest = {
        "schema_version": 1,
        "scope": "FORMAL_E2A_EXECUTION_MANIFEST_V1",
        "status": "COMPLETE" if summary["failed"] == 0 else "COMPLETE_WITH_RETAINED_FAILURES",
        "git": {"commit": _git("rev-parse", "HEAD"), "tree": _git("rev-parse", "HEAD^{tree}"), "branch": _git("branch", "--show-current")},
        "scientific_identity": preflight_report,
        "cases": CASES,
        "baseline_reuse": {"path": BASELINE_RELATIVE.as_posix(), "sha256": sha256_file(ROOT / BASELINE_RELATIVE), "rows": 1000, "rerun": False},
        "sample_table": {"path": SAMPLES_RELATIVE.as_posix(), "sha256": SAMPLE_SHA256, "rows": 1000},
        "execution": {"planned": 4000, "attempted": 4000, "certified": summary["certified"], "failed": summary["failed"]},
        "guardrails": {"OFAT": True, "fixed_absolute_budget": True, "resampled": False, "dropped": False, "parameter_tuning": False, "E2_B_runs": 0, "E2_C_runs": 0, "E2_D_runs": 0},
    }
    atomic_write_json(OUTPUT / "e2a_manifest.json", manifest)
    files = sorted(path for path in OUTPUT.iterdir() if path.is_file() and path.name != "HASHES.sha256")
    atomic_write_text(OUTPUT / "HASHES.sha256", "".join(f"{sha256_file(path)}  {path.name}\n" for path in files))
    verify()
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def verify() -> int:
    report = baseline_identity_preflight(ROOT)
    if report["planned_new_runs"] != 4000:
        raise RuntimeError("preflight run count changed")
    hashes = {}
    for line in (OUTPUT / "HASHES.sha256").read_text(encoding="utf-8").splitlines():
        digest, name = line.split("  ", 1)
        hashes[name] = digest
    actual_files = {path.name for path in OUTPUT.iterdir() if path.is_file()} - {"HASHES.sha256"}
    if set(hashes) != actual_files:
        raise RuntimeError("E2-A hash inventory is incomplete")
    for name, digest in hashes.items():
        if sha256_file(OUTPUT / name) != digest:
            raise RuntimeError(f"E2-A artifact hash mismatch: {name}")
    rows = read_csv(OUTPUT / "e2a_scientific_results.csv")
    if len(rows) != 4000 or any(row["algorithm_identity"] != FINAL_A1_IDENTITY for row in rows):
        raise RuntimeError("E2-A result population/algorithm identity mismatch")
    if any(float(row["budget"]) != report["budget"] for row in rows if row["certificate_status"] == "PASS"):
        raise RuntimeError("E2-A absolute budget drift")
    manifest = json.loads((OUTPUT / "e2a_manifest.json").read_text(encoding="utf-8"))
    if any(manifest["guardrails"][key] != 0 for key in ("E2_B_runs", "E2_C_runs", "E2_D_runs")):
        raise RuntimeError("a forbidden E2 component was executed")
    print("E2-A deterministic verification PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("preflight", "run-case", "finalize", "verify"))
    parser.add_argument("--case", choices=tuple(CASES))
    args = parser.parse_args()
    if args.command == "preflight":
        return preflight()
    if args.command == "run-case":
        if args.case is None:
            parser.error("run-case requires --case")
        return run_case(args.case)
    if args.command == "finalize":
        return finalize()
    return verify()


if __name__ == "__main__":
    raise SystemExit(main())
