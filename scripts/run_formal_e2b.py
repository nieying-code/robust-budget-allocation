#!/usr/bin/env python
"""Run and deterministically finalize frozen Formal E2-B."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import subprocess
import sys
import traceback

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from robust_budget_allocation.algorithms.qfr_final_a1 import FINAL_A1_IDENTITY, FINAL_A1_IMPLEMENTATION_REVISION
from robust_budget_allocation.formal.e2a import BASELINE_RELATIVE, SAMPLE_SHA256, csv_bytes, load_samples, read_csv
from robust_budget_allocation.formal.e2b import (
    BASELINE_CASE, B_REF, CASES, baseline_rows, data_for_case_sample, frozen_hashes,
    load_base_fixture, paired_rows, serialize_result, summarize_level, summarize_pairs,
    validate_e2b_design,
)
from robust_budget_allocation.algorithms.qfr_final_a1 import solve_qfr_final_a1
from robust_budget_allocation.io.atomic import atomic_write_json, atomic_write_text
from robust_budget_allocation.io.hashing import sha256_file

OUTPUT = ROOT / "formal_results/e2_final/e2b"


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(csv_bytes(rows))
    temporary.replace(path)


def preflight() -> int:
    report = validate_e2b_design(ROOT)
    report.update(
        schema_version=1,
        frozen_hashes=frozen_hashes(ROOT),
        baseline_path=BASELINE_RELATIVE.as_posix(),
        baseline_sha256=sha256_file(ROOT / BASELINE_RELATIVE),
        git_commit=_git("rev-parse", "HEAD"),
        git_tree=_git("show", "-s", "--format=%T", "HEAD"),
        scientific_optimizations_completed=0,
    )
    OUTPUT.mkdir(parents=True, exist_ok=True)
    atomic_write_json(OUTPUT / "preflight.json", report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


def _failed(case_id: str, sample: dict[str, object], error: BaseException) -> dict[str, object]:
    return {
        "case_id": case_id, "simulation_id": sample["simulation_id"],
        "sample_index": sample["sample_index"], "input_sha256": sample["input_sha256"],
        "model_kind": "M2", "algorithm_identity": FINAL_A1_IDENTITY,
        "implementation_revision": FINAL_A1_IMPLEMENTATION_REVISION,
        "budget_ratio": CASES[case_id]["budget_ratio"], "budget": CASES[case_id]["budget"],
        "status": "exception", "certificate_status": "FAIL",
        "failure_type": type(error).__name__, "failure_message": str(error),
        "traceback": "".join(traceback.format_exception(error)),
    }


def run_case(case_id: str) -> int:
    validate_e2b_design(ROOT)
    samples = load_samples(ROOT)
    payload, metadata = load_base_fixture(ROOT)
    path = OUTPUT / f"{case_id}.csv"
    existing = read_csv(path) if path.exists() else []
    if [row["simulation_id"] for row in existing] != [row["simulation_id"] for row in samples[:len(existing)]]:
        raise RuntimeError(f"{case_id} checkpoint is not an exact frozen-sample prefix")
    rows: list[dict[str, object]] = list(existing)
    for position, sample in enumerate(samples[len(rows):], len(rows) + 1):
        try:
            data = data_for_case_sample(payload, metadata, case_id, sample)
            result = solve_qfr_final_a1(data, "M2")
            row = serialize_result(case_id, sample, data, metadata, result)
        except BaseException as error:
            row = _failed(case_id, sample, error)
        rows.append(row)
        if position % 10 == 0 or position == 1000:
            _write_csv(path, rows)
            certified = sum(row.get("certificate_status") == "PASS" for row in rows)
            print(f"{case_id}: {position}/1000 attempted, {certified} certified", flush=True)
    return 0


def _transition_csv(pairs: list[dict[str, object]], prefix: str) -> list[dict[str, object]]:
    counts: dict[tuple[str, str], int] = {}
    for row in pairs:
        transition = str(row[prefix])
        before, after = transition.split("->", 1)
        counts[(before, after)] = counts.get((before, after), 0) + 1
    return [{"comparison": prefix.removeprefix("policy_transition_"), "from": before, "to": after, "count": count}
            for (before, after), count in sorted(counts.items())]


def finalize() -> int:
    preflight_report = validate_e2b_design(ROOT)
    expected_frozen = json.loads((OUTPUT / "preflight.json").read_text(encoding="utf-8"))["frozen_hashes"]
    if frozen_hashes(ROOT) != expected_frozen:
        raise RuntimeError("frozen E1 or E2-A HASHES identity changed during E2-B")
    low = read_csv(OUTPUT / "E2B_B075.csv")
    high = read_csv(OUTPUT / "E2B_B125.csv")
    for case_id, rows in (("E2B_B075", low), ("E2B_B125", high)):
        if len(rows) != 1000 or [row["simulation_id"] for row in rows] != [f"LA-{i:04d}" for i in range(1, 1001)]:
            raise RuntimeError(f"{case_id} does not contain the exact frozen population")
        if any(row["certificate_status"] != "PASS" for row in rows):
            failures = [row for row in rows if row["certificate_status"] != "PASS"]
            _write_csv(OUTPUT / "retained_failures.csv", failures)
            raise RuntimeError(f"{case_id} contains retained certification failures")
    base = baseline_rows(ROOT)
    levels = {"B075": low, "B100": base, "B125": high}
    pairs = paired_rows(levels)
    summaries = {name: summarize_level(rows) for name, rows in levels.items()}
    paired_summary = summarize_pairs(pairs)
    _write_csv(OUTPUT / "scientific_results.csv", low + high)
    _write_csv(OUTPUT / "paired_budget_results.csv", pairs)
    transitions: list[dict[str, object]] = []
    for prefix in ("policy_transition_B075_B100", "policy_transition_B100_B125", "policy_transition_B075_B125"):
        transitions.extend(_transition_csv(pairs, prefix))
    _write_csv(OUTPUT / "policy_transition.csv", transitions)

    commodity_rows: list[dict[str, object]] = []
    shortage_rows: list[dict[str, object]] = []
    budget_rows: list[dict[str, object]] = []
    worst_rows: list[dict[str, object]] = []
    for level, summary in summaries.items():
        for item, values in summary["commodity"].items():
            commodity_rows.append({"budget_level": level, "commodity": item, **{k: values[k] for k in ("Q_active", "F_active")},
                                   **{f"R_{k}": v for k, v in values["reliability"].items()},
                                   "mean_Q": values["Q_quantity"]["mean"], "median_Q": values["Q_quantity"]["median"],
                                   "mean_F": values["F_quantity"]["mean"], "median_F": values["F_quantity"]["median"]})
            shortage_rows.append({"budget_level": level, "commodity": item, **values["shortage"]})
        budget_rows.append({"budget_level": level, **summary["budget_utilization"],
                            **{f"mean_{k}": v["mean"] for k, v in summary["mechanism_expenditure"].items()},
                            **{f"mean_{k}": v["mean"] for k, v in summary["mechanism_budget_share"].items()}})
        for scenario, count in sorted(summary["worst_scenario_counts"].items()):
            worst_rows.append({"budget_level": level, "scenario_id": scenario, "count": count})
    _write_csv(OUTPUT / "commodity_summary.csv", commodity_rows)
    _write_csv(OUTPUT / "shortage_summary.csv", shortage_rows)
    _write_csv(OUTPUT / "budget_utilization_summary.csv", budget_rows)
    _write_csv(OUTPUT / "worst_scenario_summary.csv", worst_rows)
    reliability_rows: list[dict[str, object]] = []
    for comparison, values in paired_summary.items():
        for item, transitions_by_name in values["reliability_transitions"].items():
            for transition, count in sorted(transitions_by_name.items()):
                before, after = transition.split("->", 1)
                reliability_rows.append({"comparison": comparison, "commodity": item, "from": before, "to": after, "count": count})
    _write_csv(OUTPUT / "reliability_transition.csv", reliability_rows)
    analysis = {
        "schema_version": 1, "scope": "FORMAL_E2B_BUDGET_SENSITIVITY_V1",
        "status": "COMPLETE", "levels": summaries, "paired": paired_summary,
        "scientific_interpretation": "DESCRIPTIVE_PAIRED_PARAMETER_SPACE_SENSITIVITY",
    }
    atomic_write_json(OUTPUT / "e2b_analysis.json", analysis)
    manifest = {
        "schema_version": 1, "scope": "FORMAL_E2B_EXECUTION_MANIFEST_V1", "status": "COMPLETE",
        "git": {"commit": _git("rev-parse", "HEAD"), "tree": _git("show", "-s", "--format=%T", "HEAD"), "branch": _git("branch", "--show-current")},
        "scientific_identity": preflight_report,
        "sample_table": {"path": "formal_results/e1_final/e1_samples.csv", "sha256": SAMPLE_SHA256, "rows": 1000},
        "baseline_reuse": {"path": BASELINE_RELATIVE.as_posix(), "sha256": sha256_file(ROOT / BASELINE_RELATIVE), "rows": 1000, "rerun": False},
        "execution": {"planned": 2000, "attempted": 2000, "certified": 2000, "failed": 0},
        "frozen_evidence_hashes": expected_frozen,
        "guardrails": {"E2_A_frozen": True, "E2_A_rerun": False, "only_B_changed": True, "resampled": False, "dropped": False, "E2_C_runs": 0, "E2_D_runs": 0},
    }
    atomic_write_json(OUTPUT / "manifest.json", manifest)
    files = sorted(path for path in OUTPUT.iterdir() if path.is_file() and path.name != "HASHES.sha256")
    atomic_write_text(OUTPUT / "HASHES.sha256", "".join(f"{sha256_file(path)}  {path.name}\n" for path in files))
    verify()
    print(json.dumps(analysis, indent=2, sort_keys=True))
    return 0


def verify() -> int:
    validate_e2b_design(ROOT)
    manifest = json.loads((OUTPUT / "manifest.json").read_text(encoding="utf-8"))
    if frozen_hashes(ROOT) != manifest["frozen_evidence_hashes"]:
        raise RuntimeError("frozen E1/E2-A identity mismatch")
    hashes: dict[str, str] = {}
    for line in (OUTPUT / "HASHES.sha256").read_text(encoding="utf-8").splitlines():
        digest, name = line.split("  ", 1)
        hashes[name] = digest
    actual = {path.name for path in OUTPUT.iterdir() if path.is_file()} - {"HASHES.sha256"}
    if set(hashes) != actual:
        raise RuntimeError("E2-B hash inventory incomplete")
    for name, digest in hashes.items():
        if sha256_file(OUTPUT / name) != digest:
            raise RuntimeError(f"E2-B hash mismatch: {name}")
    rows = read_csv(OUTPUT / "scientific_results.csv")
    if len(rows) != 2000 or any(row["certificate_status"] != "PASS" for row in rows):
        raise RuntimeError("E2-B scientific population is not 2000/2000 certified")
    if any(row["algorithm_identity"] != FINAL_A1_IDENTITY or row["implementation_revision"] != FINAL_A1_IMPLEMENTATION_REVISION for row in rows):
        raise RuntimeError("E2-B Final A1 identity drift")
    pairs = read_csv(OUTPUT / "paired_budget_results.csv")
    if len(pairs) != 1000 or len({row["simulation_id"] for row in pairs}) != 1000:
        raise RuntimeError("E2-B paired triplets incomplete")
    if manifest["baseline_reuse"]["rerun"] or manifest["guardrails"]["E2_A_rerun"]:
        raise RuntimeError("a frozen baseline was rerun")
    print("E2-B deterministic verification PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("preflight", "run-case", "finalize", "verify"))
    parser.add_argument("--case", choices=tuple(CASES))
    args = parser.parse_args()
    if args.command == "preflight": return preflight()
    if args.command == "run-case":
        if args.case is None: parser.error("run-case requires --case")
        return run_case(args.case)
    if args.command == "finalize": return finalize()
    return verify()


if __name__ == "__main__":
    raise SystemExit(main())
