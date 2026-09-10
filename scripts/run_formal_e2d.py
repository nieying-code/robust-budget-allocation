#!/usr/bin/env python
"""Run, summarize, and verify frozen Formal E2-D."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import subprocess
import sys
import traceback

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from robust_budget_allocation.algorithms.qfr_final_a1 import FINAL_A1_IDENTITY, FINAL_A1_IMPLEMENTATION_REVISION, solve_qfr_final_a1
from robust_budget_allocation.formal.e2a import OUTPUT_ITEMS, SAMPLE_SHA256, csv_bytes, load_base_fixture, load_samples, read_csv
from robust_budget_allocation.formal.e2d import (
    BUDGET, CASES, LEVEL_NAMES, baseline_rows, data_for_case_sample, frozen_hashes,
    paired_rows, serialize_result, summarize_all, validate_e2d_design,
)
from robust_budget_allocation.io.atomic import atomic_write_json, atomic_write_text
from robust_budget_allocation.io.hashing import sha256_file
from robust_budget_allocation.io.hashing import canonical_json_sha256

OUTPUT = ROOT / "formal_results/e2_final/e2d"


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(csv_bytes(rows))
    temporary.replace(path)


def preflight() -> int:
    report = validate_e2d_design(ROOT)
    report.update(schema_version=1, git_commit=_git("rev-parse", "HEAD"),
                  git_tree=_git("show", "-s", "--format=%T", "HEAD"),
                  scientific_optimizations_completed=0)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    atomic_write_json(OUTPUT / "preflight.json", report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


def _failed(case_id: str, sample: dict[str, object], error: BaseException) -> dict[str, object]:
    t = CASES[case_id]
    return {
        "experiment_part": t["part"], "case_id": case_id,
        "simulation_id": sample["simulation_id"], "sample_index": sample["sample_index"],
        "input_sha256": sample["input_sha256"], "model_kind": "M2",
        "algorithm_identity": FINAL_A1_IDENTITY, "implementation_revision": FINAL_A1_IMPLEMENTATION_REVISION,
        "budget": BUDGET, "beta": t["beta"], "lambda_Water": t["lambda"][0],
        "lambda_Vaccine": t["lambda"][1], "lambda_Crackers": t["lambda"][2],
        "status": "exception", "certificate_status": "FAIL", "failure_type": type(error).__name__,
        "failure_message": str(error), "traceback": "".join(traceback.format_exception(error)),
    }


def run_case(case_id: str) -> int:
    validate_e2d_design(ROOT)
    samples = load_samples(ROOT)
    payload, metadata = load_base_fixture(ROOT)
    path = OUTPUT / f"{case_id}.csv"
    existing = read_csv(path) if path.exists() else []
    if [r["simulation_id"] for r in existing] != [r["simulation_id"] for r in samples[:len(existing)]]:
        raise RuntimeError(f"{case_id} checkpoint is not an exact frozen-sample prefix")
    rows: list[dict[str, object]] = list(existing)
    for position, sample in enumerate(samples[len(rows):], len(rows) + 1):
        try:
            data = data_for_case_sample(payload, metadata, case_id, sample)
            row = serialize_result(case_id, sample, data, metadata, solve_qfr_final_a1(data, "M2"))
        except BaseException as error:
            row = _failed(case_id, sample, error)
        rows.append(row)
        if position % 10 == 0 or position == 1000:
            _write_csv(path, rows)
            print(f"{case_id}: {position}/1000 attempted, {sum(r.get('certificate_status') == 'PASS' for r in rows)} certified", flush=True)
    return 0


def _transition_rows(beta_pairs: list[dict[str, object]], priority_pairs: list[dict[str, object]]) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    beta = []
    for comparison in ("BETA2_BETA4", "BETA4_BETA6"):
        counts = Counter(str(r[f"policy_transition_{comparison}"]) for r in beta_pairs)
        beta.extend({"comparison": comparison, "from": key.split("->")[0], "to": key.split("->")[1], "count": value} for key, value in sorted(counts.items()))
    priority = []
    for case in CASES:
        if CASES[case]["part"] != "D2": continue
        counts = Counter(str(r["policy_transition"]) for r in priority_pairs if r["case_id"] == case)
        priority.extend({"case_id": case, "from": key.split("->")[0], "to": key.split("->")[1], "count": value} for key, value in sorted(counts.items()))
    reliability = []
    for comparison in ("BETA2_BETA4", "BETA4_BETA6"):
        for label in OUTPUT_ITEMS.values():
            counts = Counter(str(r[f"R_transition_{label}_{comparison}"]) for r in beta_pairs)
            reliability.extend({"part": "D1", "comparison": comparison, "commodity": label, "from": k.split("->")[0], "to": k.split("->")[1], "count": v} for k, v in sorted(counts.items()))
    for case in CASES:
        if CASES[case]["part"] != "D2": continue
        for label in OUTPUT_ITEMS.values():
            counts = Counter(f"{r[f'baseline_R_{label}']}->{r[f'case_R_{label}']}" for r in priority_pairs if r["case_id"] == case)
            reliability.extend({"part": "D2", "comparison": case, "commodity": label, "from": k.split("->")[0], "to": k.split("->")[1], "count": v} for k, v in sorted(counts.items()))
    return beta, priority, reliability


def finalize() -> int:
    design = validate_e2d_design(ROOT)
    preflight_data = json.loads((OUTPUT / "preflight.json").read_text(encoding="utf-8"))
    if frozen_hashes(ROOT) != preflight_data["frozen_hashes"]:
        raise RuntimeError("frozen E1/E2-A/E2-B/E2-C evidence changed during E2-D")
    expected_ids = [f"LA-{i:04d}" for i in range(1, 1001)]
    case_rows: dict[str, list[dict[str, object]]] = {}
    failures: list[dict[str, object]] = []
    for case in CASES:
        rows = read_csv(OUTPUT / f"{case}.csv")
        if len(rows) != 1000 or [r["simulation_id"] for r in rows] != expected_ids:
            raise RuntimeError(f"{case} does not contain exact frozen population")
        for row in rows:
            row["normalized_shortage_value"] = float(row["worst_shortage_penalty"]) / float(row["beta"])
            row["row_sha256"] = canonical_json_sha256({k: v for k, v in row.items() if k != "row_sha256"})
        case_rows[case] = rows
        failures.extend(r for r in rows if r["certificate_status"] != "PASS")
    if failures:
        _write_csv(OUTPUT / "retained_failures.csv", failures)
        raise RuntimeError(f"E2-D contains {len(failures)} retained certification failures")
    baseline = baseline_rows(ROOT)
    beta_pairs, priority_pairs = paired_rows(case_rows, baseline)
    analysis_core = summarize_all(case_rows, baseline, beta_pairs, priority_pairs)

    _write_csv(OUTPUT / "scientific_results.csv", [r for case in CASES for r in case_rows[case]])
    _write_csv(OUTPUT / "paired_beta_results.csv", beta_pairs)
    _write_csv(OUTPUT / "paired_priority_results.csv", priority_pairs)
    beta_transition, priority_transition, reliability = _transition_rows(beta_pairs, priority_pairs)
    _write_csv(OUTPUT / "beta_policy_transition.csv", beta_transition)
    _write_csv(OUTPUT / "priority_policy_transition.csv", priority_transition)
    _write_csv(OUTPUT / "reliability_summary.csv", reliability)

    commodity_rows = []; shortage_rows = []; budget_rows = []; worst_rows = []
    for level, summary in analysis_core["levels"].items():
        for commodity, values in summary["commodity"].items():
            commodity_rows.append({"level": level, "commodity": commodity, "Q_active": values["Q_active"], "F_active": values["F_active"],
                                  **{f"R_{k}": v for k, v in values["reliability"].items()},
                                  "mean_Q": values["Q_quantity"]["mean"], "median_Q": values["Q_quantity"]["median"],
                                  "mean_F": values["F_quantity"]["mean"], "median_F": values["F_quantity"]["median"]})
            shortage_rows.append({"level": level, "commodity": commodity, **values["shortage"]})
        shortage_rows.append({
            "level": level, "commodity": "AGGREGATE_PHYSICAL_UNITS",
            **summary["aggregate_shortage"],
            "weighted_loss_mean": summary["weighted_shortage_loss"]["mean"],
            "weighted_loss_median": summary["weighted_shortage_loss"]["median"],
            "weighted_loss_Q25": summary["weighted_shortage_loss"]["Q25"],
            "weighted_loss_Q75": summary["weighted_shortage_loss"]["Q75"],
            "normalized_value_mean": summary["normalized_shortage_value"]["mean"],
            "normalized_value_median": summary["normalized_shortage_value"]["median"],
        })
        budget_rows.append({"level": level, **summary["budget_utilization"],
                            **{f"mean_{k}": v["mean"] for k, v in summary["mechanism_expenditure"].items()}})
        worst_rows.extend({"level": level, "scenario_id": scenario, "count": count} for scenario, count in sorted(summary["worst_scenario_counts"].items()))
    _write_csv(OUTPUT / "commodity_allocation_summary.csv", commodity_rows)
    _write_csv(OUTPUT / "beta_shortage_summary.csv", [r for r in shortage_rows if r["level"] in {"BETA2", "BETA4_BASELINE", "BETA6"}])
    _write_csv(OUTPUT / "priority_shortage_summary.csv", [r for r in shortage_rows if r["level"] not in {"BETA2", "BETA6"}])
    _write_csv(OUTPUT / "budget_utilization_summary.csv", budget_rows)
    _write_csv(OUTPUT / "worst_scenario_summary.csv", worst_rows)
    _write_csv(OUTPUT / "commodity_priority_tradeoff.csv", analysis_core["commodity_priority_tradeoff"])

    analysis = {"schema_version": 1, "scope": "FORMAL_E2D_SHORTAGE_VALUATION_AND_PRIORITY_V1", "status": "COMPLETE",
                **analysis_core, "scientific_interpretation": "DESCRIPTIVE_PAIRED_PARAMETER_SPACE_SENSITIVITY"}
    atomic_write_json(OUTPUT / "e2d_analysis.json", analysis)
    manifest = {
        "schema_version": 1, "scope": "FORMAL_E2D_EXECUTION_MANIFEST_V1", "status": "COMPLETE",
        "git": {"commit": _git("rev-parse", "HEAD"), "tree": _git("show", "-s", "--format=%T", "HEAD"), "branch": _git("branch", "--show-current")},
        "scientific_identity": design,
        "sample_table": {"path": "formal_results/e1_final/e1_samples.csv", "sha256": SAMPLE_SHA256, "rows": 1000},
        "baseline_reuse": {"path": "formal_results/e1_final/e1_scientific_results.csv", "sha256": sha256_file(ROOT / "formal_results/e1_final/e1_scientific_results.csv"), "rows": 1000, "rerun": False},
        "execution": {"planned": 5000, "attempted": 5000, "certified": 5000, "failed": 0},
        "frozen_evidence_hashes": preflight_data["frozen_hashes"],
        "guardrails": {"E1_frozen": True, "E2A_frozen": True, "E2B_frozen": True, "E2C_frozen": True,
                       "only_beta_or_lambda_changed": True, "resampled": False, "baseline_rerun": False, "E3_runs": 0},
    }
    atomic_write_json(OUTPUT / "manifest.json", manifest)
    files = sorted(p for p in OUTPUT.iterdir() if p.is_file() and p.name != "HASHES.sha256")
    atomic_write_text(OUTPUT / "HASHES.sha256", "".join(f"{sha256_file(p)}  {p.name}\n" for p in files))
    verify()
    print(json.dumps(analysis, indent=2, sort_keys=True))
    return 0


def verify() -> int:
    validate_e2d_design(ROOT)
    manifest = json.loads((OUTPUT / "manifest.json").read_text(encoding="utf-8"))
    if frozen_hashes(ROOT) != manifest["frozen_evidence_hashes"]:
        raise RuntimeError("frozen evidence identity mismatch")
    hashes = {}
    for line in (OUTPUT / "HASHES.sha256").read_text(encoding="utf-8").splitlines():
        digest, name = line.split("  ", 1); hashes[name] = digest
    actual = {p.name for p in OUTPUT.iterdir() if p.is_file()} - {"HASHES.sha256"}
    if set(hashes) != actual:
        raise RuntimeError("E2-D hash inventory incomplete")
    for name, digest in hashes.items():
        if sha256_file(OUTPUT / name) != digest: raise RuntimeError(f"E2-D hash mismatch: {name}")
    rows = read_csv(OUTPUT / "scientific_results.csv")
    if len(rows) != 5000 or any(r["certificate_status"] != "PASS" for r in rows):
        raise RuntimeError("E2-D population is not 5000/5000 certified")
    if any(r["algorithm_identity"] != FINAL_A1_IDENTITY or r["implementation_revision"] != FINAL_A1_IMPLEMENTATION_REVISION for r in rows):
        raise RuntimeError("Final A1 identity drift")
    if len(read_csv(OUTPUT / "paired_beta_results.csv")) != 1000 or len(read_csv(OUTPUT / "paired_priority_results.csv")) != 3000:
        raise RuntimeError("paired E2-D population incomplete")
    if manifest["baseline_reuse"]["rerun"] or manifest["guardrails"]["E3_runs"]:
        raise RuntimeError("baseline rerun or E3 execution recorded")
    print("E2-D deterministic verification PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("preflight", "run-case", "finalize", "verify"))
    parser.add_argument("--case", choices=tuple(CASES))
    args = parser.parse_args()
    if args.command == "preflight": return preflight()
    if args.command == "run-case":
        if not args.case: parser.error("run-case requires --case")
        return run_case(args.case)
    if args.command == "finalize": return finalize()
    return verify()


if __name__ == "__main__":
    raise SystemExit(main())
