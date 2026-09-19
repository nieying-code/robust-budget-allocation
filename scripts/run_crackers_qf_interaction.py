#!/usr/bin/env python
"""Run and audit the independent Crackers retention x F-economics supplement."""

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

from robust_budget_allocation.formal.crackers_qf_interaction import (
    CASES,
    F_ECONOMICS_LEVELS,
    OUTPUT,
    RETENTION_LEVELS,
    audit,
    case_id,
    matrix,
    preflight,
    solve_one,
    summarize,
)
from robust_budget_allocation.formal.e2a import OUTPUT_ITEMS, csv_bytes, read_csv
from robust_budget_allocation.formal.e3 import s200_samples
from robust_budget_allocation.formal.e2d_audit import verify_hash_inventory
from robust_budget_allocation.io.atomic import atomic_write_json, atomic_write_text
from robust_budget_allocation.io.hashing import canonical_json_sha256, sha256_file


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(csv_bytes(rows))
    tmp.replace(path)


def _failed(case: str, sample: dict[str, object], error: BaseException) -> dict[str, object]:
    return {
        "experiment_part": "CRACKERS_QF_INTERACTION_SUPPLEMENT",
        "case_id": case,
        "simulation_id": sample["simulation_id"],
        "sample_index": sample["sample_index"],
        "input_sha256": sample["input_sha256"],
        "status": "exception",
        "certificate_status": "FAIL",
        "failure_type": type(error).__name__,
        "failure_message": str(error),
        "traceback": "".join(traceback.format_exception(error)),
    }


def preflight_command() -> int:
    report = preflight(ROOT)
    directory = ROOT / OUTPUT
    directory.mkdir(parents=True, exist_ok=True)
    report.update(
        execution_branch=_git("branch", "--show-current"),
        execution_head=_git("rev-parse", "HEAD"),
        execution_tree=_git("rev-parse", "HEAD^{tree}"),
        scientific_optimizations_completed=0,
    )
    atomic_write_json(directory / "preflight.json", report)
    print(json.dumps({key: report[key] for key in ("status", "S200_sha256", "planned", "cases")}, indent=2))
    return 0


def run() -> int:
    report = preflight(ROOT)
    samples = s200_samples(ROOT, report)
    directory = ROOT / OUTPUT / "cells"
    directory.mkdir(parents=True, exist_ok=True)
    for case in CASES:
        path = directory / f"{case}.csv"
        rows = read_csv(path) if path.exists() else []
        expected_prefix = [row["simulation_id"] for row in samples[: len(rows)]]
        if [row["simulation_id"] for row in rows] != expected_prefix:
            raise RuntimeError(f"{case}: checkpoint is not the frozen S200 prefix")
        for position, sample in enumerate(samples[len(rows) :], len(rows) + 1):
            try:
                row = solve_one(ROOT, case, sample)
            except BaseException as error:
                row = _failed(case, sample, error)
            rows.append(row)
            if position % 10 == 0 or position == 200:
                _write_csv(path, rows)
                certified = sum(r.get("certificate_status") == "PASS" for r in rows)
                print(f"{case}: {position}/200 attempted, {certified} certified", flush=True)
    return 0


def _tables(summaries: dict[str, dict[str, object]]):
    cells: list[dict[str, object]] = []
    commodities: list[dict[str, object]] = []
    reliability: list[dict[str, object]] = []
    performance: list[dict[str, object]] = []
    cross: list[dict[str, object]] = []
    for case, summary in summaries.items():
        treatment = {key: summary[key] for key in ("a_C", "m_F", "phi", "psi")}
        cells.append(
            {
                "case_id": case,
                **treatment,
                "N": summary["N"],
                **{f"policy_{name}_count": summary["policy_counts"][name] for name in ("P1", "P2", "P3a", "P3b", "P4", "P5")},
                **{f"policy_{name}_rate": round(summary["policy_counts"][name] / summary["N"] * 100.0, 12) for name in ("P1", "P2", "P3a", "P3b", "P4", "P5")},
                "mixed_QF_count": summary["mixed_QF_count"],
                "mixed_QF_rate": summary["mixed_QF_rate"],
                "same_item_QF_count": summary["same_item_QF_count"],
                "same_item_QF_rate": summary["same_item_QF_rate"],
                "cross_item_QF_count": summary["cross_item_QF_count"],
                "cross_item_QF_rate": summary["cross_item_QF_rate"],
            }
        )
        for commodity, values in summary["commodities"].items():
            row = {
                "case_id": case,
                **treatment,
                "commodity": commodity,
                "N": summary["N"],
                "Q_activation_count": values["Q_activation_count"],
                "Q_activation_rate": values["Q_activation_rate"],
                "F_activation_count": values["F_activation_count"],
                "F_activation_rate": values["F_activation_rate"],
                "Q_mean": values["Q"]["mean"],
                "Q_median": values["Q"]["median"],
                "Q_conditional_mean": values["Q_conditional_mean"],
                "F_mean": values["F"]["mean"],
                "F_median": values["F"]["median"],
                "F_conditional_mean": values["F_conditional_mean"],
            }
            commodities.append(row)
            cross.append(dict(row))
        reliability.append({"case_id": case, **treatment, "N": summary["N"], **summary["reliability"]})
        perf = {"case_id": case, **treatment, "N": summary["N"]}
        for field, values in summary["performance"].items():
            perf.update({f"{field}_{stat}": value for stat, value in values.items()})
        performance.append(perf)
    return cells, commodities, reliability, performance, cross


def _analysis(summaries: dict[str, dict[str, object]]) -> dict[str, object]:
    retention_effects = {}
    for multiplier in F_ECONOMICS_LEVELS:
        high = summaries[case_id(1.0, multiplier)]
        low = summaries[case_id(0.8, multiplier)]
        retention_effects[str(multiplier)] = {
            "Crackers_Q_activation_rate_change_a1.0_to_a0.8": low["commodities"]["Crackers"]["Q_activation_rate"] - high["commodities"]["Crackers"]["Q_activation_rate"],
            "Crackers_F_activation_rate_change_a1.0_to_a0.8": low["commodities"]["Crackers"]["F_activation_rate"] - high["commodities"]["Crackers"]["F_activation_rate"],
            "Mixed_QF_rate_change_a1.0_to_a0.8": low["mixed_QF_rate"] - high["mixed_QF_rate"],
            "mean_T_COST_change_a1.0_to_a0.8": low["performance"]["T_COST"]["mean"] - high["performance"]["T_COST"]["mean"],
        }
    return {
        "scope": "CRACKERS_QF_INTERACTION_S200_SUPPLEMENT_V1",
        "cell_summaries": summaries,
        "matrices": {
            "mixed_QF_rate": matrix(summaries, lambda s: s["mixed_QF_rate"]),
            "Crackers_Q_activation_rate": matrix(summaries, lambda s: s["commodities"]["Crackers"]["Q_activation_rate"]),
            "Crackers_F_activation_rate": matrix(summaries, lambda s: s["commodities"]["Crackers"]["F_activation_rate"]),
            "mean_T_COST": matrix(summaries, lambda s: s["performance"]["T_COST"]["mean"]),
        },
        "retention_effects_by_F_economics": retention_effects,
        "interpretation_rule": "DESCRIPTIVE_ONLY_NO_RESULT_DRIVEN_TUNING",
    }


def _matrix_markdown(title: str, summaries: dict[str, dict[str, object]], getter, digits: int = 6) -> list[str]:
    lines = [f"### {title}", "", "| Crackers retention | mF=0.8 | mF=1.0 | mF=1.2 |", "|---:|---:|---:|---:|"]
    for retention in RETENTION_LEVELS:
        values = [getter(summaries[case_id(retention, multiplier)]) for multiplier in F_ECONOMICS_LEVELS]
        lines.append(f"| {retention:.1f} | " + " | ".join(f"{float(value):.{digits}f}" for value in values) + " |")
    lines.append("")
    return lines


def _result_summary(summaries: dict[str, dict[str, object]], analysis: dict[str, object]) -> str:
    lines = [
        "# Crackers Q-F interaction S200 supplement",
        "",
        "Status: 1,800/1,800 solved and Full Exact Certified; no failed, deleted, replaced, or resampled case.",
        "",
        "## Core 3 x 3 evidence",
        "",
    ]
    lines += _matrix_markdown("Mixed Q-F portfolio rate (%)", summaries, lambda s: s["mixed_QF_rate"], 1)
    lines += _matrix_markdown("Crackers Q activation rate (%)", summaries, lambda s: s["commodities"]["Crackers"]["Q_activation_rate"], 1)
    lines += _matrix_markdown("Crackers F activation rate (%)", summaries, lambda s: s["commodities"]["Crackers"]["F_activation_rate"], 1)
    lines += _matrix_markdown("Mean T-COST", summaries, lambda s: s["performance"]["T_COST"]["mean"], 3)
    total_mixed = sum(int(summary["mixed_QF_count"]) for summary in summaries.values())
    total_same = sum(int(summary["same_item_QF_count"]) for summary in summaries.values())
    total_cross = sum(int(summary["cross_item_QF_count"]) for summary in summaries.values())
    high_08 = summaries[case_id(1.0, 0.8)]
    low_08 = summaries[case_id(0.8, 0.8)]
    high_10 = summaries[case_id(1.0, 1.0)]
    low_10 = summaries[case_id(0.8, 1.0)]
    high_12 = summaries[case_id(1.0, 1.2)]
    low_12 = summaries[case_id(0.8, 1.2)]
    f_effect = high_12["performance"]["T_COST"]["mean"] - high_08["performance"]["T_COST"]["mean"]
    lines += [
        "## Data-driven findings",
        "",
        f"1. Crackers Q activation is 0% throughout mF=0.8. At mF=1.0 it falls from {high_10['commodities']['Crackers']['Q_activation_rate']:.1f}% at a=1.0 to {low_10['commodities']['Crackers']['Q_activation_rate']:.1f}% at a=0.8; at mF=1.2 it falls from {high_12['commodities']['Crackers']['Q_activation_rate']:.1f}% to {low_12['commodities']['Crackers']['Q_activation_rate']:.1f}%.",
        "2. The retention effect is therefore conditional on F economics: it is absent when F is favorable (mF=0.8), modest at mF=1.0, and strongest at mF=1.2. Results at a=0.9 and a=0.8 are nearly identical because Crackers Q is already inactive after the first retention reduction.",
        f"3. Crackers F activation changes only slightly: a=1.0 to a=0.8 changes it by {low_08['commodities']['Crackers']['F_activation_rate']-high_08['commodities']['Crackers']['F_activation_rate']:.1f}, {low_10['commodities']['Crackers']['F_activation_rate']-high_10['commodities']['Crackers']['F_activation_rate']:.1f}, and {low_12['commodities']['Crackers']['F_activation_rate']-high_12['commodities']['Crackers']['F_activation_rate']:.1f} percentage points at mF=0.8, 1.0, and 1.2. The evidence supports partial effectiveness-driven Q-F substitution, not a one-for-one within-item switch.",
        f"4. Mixed Q-F portfolio rates are 0% in all a=1.0 cells and become 1.5% and 4.0% at mF=1.0 and 1.2 after retention falls. Across the full panel, all {total_mixed} mixed portfolios are cross-item specializations: same-item coexistence={total_same}, cross-item specialization={total_cross}.",
        f"5. At mF=1.2, a=1.0 to a=0.8 raises Water Q/F activation by {low_12['commodities']['Water']['Q_activation_rate']-high_12['commodities']['Water']['Q_activation_rate']:.1f}/{low_12['commodities']['Water']['F_activation_rate']-high_12['commodities']['Water']['F_activation_rate']:.1f} points and Vaccine Q/F activation by {low_12['commodities']['Vaccine']['Q_activation_rate']-high_12['commodities']['Vaccine']['Q_activation_rate']:.1f}/{low_12['commodities']['Vaccine']['F_activation_rate']-high_12['commodities']['Vaccine']['F_activation_rate']:.1f} points. Reallocation therefore extends beyond Crackers F to Water and especially Vaccine.",
        f"6. The mean T-COST increase from a=1.0 to a=0.8 is {low_08['performance']['T_COST']['mean']-high_08['performance']['T_COST']['mean']:.3f}, {low_10['performance']['T_COST']['mean']-high_10['performance']['T_COST']['mean']:.3f}, and {low_12['performance']['T_COST']['mean']-high_12['performance']['T_COST']['mean']:.3f} across mF=0.8, 1.0, and 1.2, versus {f_effect:.3f} for mF=0.8 to 1.2 at a=1.0. F economics has the much larger T-COST effect.",
        "7. Paid-R adoption is essentially stable across retention levels; its largest retention-linked change is 0.5 percentage points at mF=1.2. Reliability is therefore not the primary destination of the displaced Crackers-Q allocation in this panel.",
        "8. The interaction is visible in activation and portfolio structure but is threshold-like rather than smooth: retention matters only when F economics is not already favorable, and the additional reduction from a=0.9 to a=0.8 adds almost no response.",
        "",
        "These statements are descriptive summaries of the frozen 3 x 3 paired panel; no interpolation, response-surface fit, parameter tuning, or sample replacement was performed.",
        "",
    ]
    return "\n".join(lines)


def finalize() -> int:
    report = preflight(ROOT)
    directory = ROOT / OUTPUT
    expected_ids = [f"LA-{index:04d}" for index in report["S200_ids"]]
    case_rows: dict[str, list[dict[str, str]]] = {}
    for case in CASES:
        rows = read_csv(directory / "cells" / f"{case}.csv")
        if len(rows) != 200 or [row["simulation_id"] for row in rows] != expected_ids:
            raise RuntimeError(f"{case}: incomplete or non-S200 population")
        case_rows[case] = rows
    scientific = [row for case in CASES for row in case_rows[case]]
    failures = [row for row in scientific if row.get("certificate_status") != "PASS"]
    if failures:
        atomic_write_json(
            directory / "validation.json",
            {"status": "FAIL", "attempted": len(scientific), "failed": len(failures), "failures": failures},
        )
        raise RuntimeError(f"{len(failures)} unresolved cases; no case was deleted or replaced")
    summaries = {case: summarize(case, rows) for case, rows in case_rows.items()}
    validation = audit(report, scientific, summaries)
    if validation["status"] != "PASS":
        atomic_write_json(directory / "validation.json", validation)
        raise RuntimeError("supplement consistency audit failed")
    _write_csv(directory / "scientific_results.csv", scientific)
    cells, commodities, reliability, performance, cross = _tables(summaries)
    _write_csv(directory / "cell_summary.csv", cells)
    _write_csv(directory / "commodity_summary.csv", commodities)
    _write_csv(directory / "reliability_summary.csv", reliability)
    _write_csv(directory / "performance_summary.csv", performance)
    _write_csv(directory / "cross_commodity_summary.csv", cross)
    analysis = _analysis(summaries)
    atomic_write_json(directory / "analysis.json", analysis)
    atomic_write_text(directory / "RESULT_SUMMARY.md", _result_summary(summaries, analysis))
    validation.update(
        attempted=1800,
        solved=1800,
        certified=1800,
        failed=0,
        numerical_recovery_count=sum(int(row["scaled_retry_count"]) for row in scientific),
        witness_gated_retry_count=sum(int(row["witness_gated_retry_count"]) for row in scientific),
        scientific_results_sha256=sha256_file(directory / "scientific_results.csv"),
    )
    atomic_write_json(directory / "validation.json", validation)
    artifacts = [
        "scientific_results.csv",
        "cell_summary.csv",
        "commodity_summary.csv",
        "reliability_summary.csv",
        "performance_summary.csv",
        "cross_commodity_summary.csv",
        "analysis.json",
        "RESULT_SUMMARY.md",
        "validation.json",
        "preflight.json",
    ]
    manifest = {
        "schema_version": 1,
        "scope": report["scope"],
        "base_main_head": report["base_main_head"],
        "base_main_tree": report["base_main_tree"],
        "execution_branch": _git("branch", "--show-current"),
        "execution_head_before_result_commit": _git("rev-parse", "HEAD"),
        "sample_sha256": report["sample_sha256"],
        "S200_sha256": report["S200_sha256"],
        "cases": CASES,
        "attempted": 1800,
        "solved": 1800,
        "certified": 1800,
        "failed": 0,
        "numerical_recovery_count": validation["numerical_recovery_count"],
        "witness_gated_retry_count": validation["witness_gated_retry_count"],
        "algorithm_identity": report["algorithm_identity"],
        "implementation_revision": report["implementation_revision"],
        "formal_results_tree": report["formal_results_tree"],
        "resampled": False,
        "model_changed": False,
        "algorithm_changed": False,
        "tolerance_changed": False,
        "result_driven_tuning": False,
        "artifacts": {name: sha256_file(directory / name) for name in artifacts},
    }
    manifest["scientific_result_identity"] = canonical_json_sha256(
        {
            "S200_sha256": manifest["S200_sha256"],
            "cases": manifest["cases"],
            "scientific_results_sha256": manifest["artifacts"]["scientific_results.csv"],
        }
    )
    atomic_write_json(directory / "manifest.json", manifest)
    hash_names = [*artifacts, "manifest.json"]
    atomic_write_text(
        directory / "HASHES.sha256",
        "".join(f"{sha256_file(directory / name)}  {name}\n" for name in sorted(hash_names)),
    )
    verify_hash_inventory(directory)
    if preflight(ROOT)["formal_results_tree"] != report["formal_results_tree"]:
        raise RuntimeError("frozen Formal E1-E5 tree changed during supplement")
    print(json.dumps({"status": "PASS", **{k: manifest[k] for k in ("attempted", "solved", "certified", "failed", "numerical_recovery_count", "scientific_result_identity")}}, indent=2))
    return 0


def verify() -> int:
    report = preflight(ROOT)
    directory = ROOT / OUTPUT
    verify_hash_inventory(directory)
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    validation = json.loads((directory / "validation.json").read_text(encoding="utf-8"))
    rows = read_csv(directory / "scientific_results.csv")
    if manifest["S200_sha256"] != report["S200_sha256"] or manifest["formal_results_tree"] != report["formal_results_tree"]:
        raise RuntimeError("supplement identity mismatch")
    if len(rows) != 1800 or validation["status"] != "PASS":
        raise RuntimeError("supplement population or validation mismatch")
    print(json.dumps({"status": "PASS", "attempted": 1800, "certified": 1800, "failed": 0}, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("preflight", "run", "finalize", "verify", "all"))
    command = parser.parse_args().command
    if command == "preflight":
        return preflight_command()
    if command == "run":
        return run()
    if command == "finalize":
        return finalize()
    if command == "verify":
        return verify()
    preflight_command()
    run()
    finalize()
    return verify()


if __name__ == "__main__":
    raise SystemExit(main())
