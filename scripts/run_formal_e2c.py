#!/usr/bin/env python
"""Build and verify solver-free Formal E2-C reliability-boundary evidence."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from robust_budget_allocation.formal.e2a import csv_bytes
from robust_budget_allocation.formal.e2c import (
    OUTPUT, bin_summary, boundary_rows, class_summary, commodity_summary,
    frozen_hashes, interaction_map, observations, statistical_support,
    validate_preflight,
)
from robust_budget_allocation.io.atomic import atomic_write_json, atomic_write_text
from robust_budget_allocation.io.hashing import sha256_file

OUT = ROOT / OUTPUT


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(csv_bytes(rows))


def build() -> int:
    preflight = validate_preflight(ROOT)
    OUT.mkdir(parents=True, exist_ok=True)
    atomic_write_json(OUT / "preflight.json", {**preflight, "git_commit": git("rev-parse", "HEAD"), "git_tree": git("show", "-s", "--format=%T", "HEAD")})
    rows, population = observations(ROOT)
    active = [row for row in rows if row["F_active_item"]]
    if len(active) != 1160:
        raise RuntimeError(f"active item-observation count changed: {len(active)}")
    classes = class_summary(active)
    ar1_bins, ar1_edges = bin_summary(active, "A_R1")
    ar2_bins, ar2_edges = bin_summary(active, "A_R2")
    ar1_map = interaction_map(active, "A_R1")
    ar2_map = interaction_map(active, "A_R2")
    commodity = commodity_summary(active)
    boundary = boundary_rows(active)
    statistics = statistical_support(active)
    e2b = json.loads((ROOT / "formal_results/e2_final/e2b/e2b_analysis.json").read_text(encoding="utf-8"))
    e2b_paid = {
        level: int(values["aggregate_reliability"]["R1"]) + int(values["aggregate_reliability"]["R2"])
        for level, values in e2b["levels"].items()
    }
    write_csv(OUT / "reliability_observations.csv", rows)
    write_csv(OUT / "reliability_class_summary.csv", classes)
    write_csv(OUT / "ar1_bin_summary.csv", ar1_bins)
    write_csv(OUT / "ar2_bin_summary.csv", ar2_bins)
    write_csv(OUT / "ar1_fexposure_map.csv", ar1_map)
    write_csv(OUT / "ar2_fexposure_map.csv", ar2_map)
    write_csv(OUT / "commodity_reliability_summary.csv", commodity)
    write_csv(OUT / "boundary_analysis.csv", boundary)
    write_csv(OUT / "statistical_support.csv", statistics)
    analysis = {
        "schema_version": 1, "scope": "FORMAL_E2C_RELIABILITY_BOUNDARY_ANALYSIS_V1",
        "status": "COMPLETE_SOLVER_FREE", "population": population,
        "active_item_observations": len(active),
        "item_reliability_counts": {level: sum(row["reliability_level"] == level for row in rows) for level in ("NONE", "R0", "R1", "R2")},
        "efficiency_quintile_edges": {"A_R1": ar1_edges, "A_R2": ar2_edges},
        "class_summaries": classes, "boundary_evidence": boundary,
        "statistical_support": statistics, "commodity_summary": commodity,
        "E2B_supplementary_paid_R_total": e2b_paid,
        "interpretation_guardrails": {
            "thresholds": "EMPIRICAL_DECISION_BOUNDARIES_NOT_STRUCTURAL_THEOREMS",
            "p_values_primary": False, "complex_ML": False,
            "E2B_role": "SUPPLEMENTARY_FROZEN_EVIDENCE_NOT_E2C_TRANSITION_EXPERIMENT",
        },
    }
    atomic_write_json(OUT / "e2c_analysis.json", analysis)
    manifest = {
        "schema_version": 1, "scope": "FORMAL_E2C_EXECUTION_MANIFEST_V1", "status": "COMPLETE",
        "git": {"commit": git("rev-parse", "HEAD"), "tree": git("show", "-s", "--format=%T", "HEAD"), "branch": git("branch", "--show-current")},
        "scientific_identity": preflight, "frozen_artifact_hashes": frozen_hashes(ROOT),
        "inputs": {"sample_sha256": preflight["sample_sha256"], "e1_results_sha256": preflight["e1_results_sha256"]},
        "analysis": {"observations": 3000, "active_item_observations": len(active), "optimization_runs": 0},
        "guardrails": {"E1_frozen": True, "E2A_frozen": True, "E2B_frozen": True, "resampled": False, "model_changed": False, "tolerance_changed": False, "scientific_parameters_changed": False, "E2_C_new_scientific_optimization_runs": 0, "E2_D_runs": 0},
    }
    atomic_write_json(OUT / "manifest.json", manifest)
    files = sorted(path for path in OUT.iterdir() if path.is_file() and path.name != "HASHES.sha256")
    atomic_write_text(OUT / "HASHES.sha256", "".join(f"{sha256_file(path)}  {path.name}\n" for path in files))
    verify()
    print(json.dumps(analysis, indent=2, sort_keys=True))
    return 0


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def verify() -> int:
    preflight = validate_preflight(ROOT)
    manifest = json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))
    if frozen_hashes(ROOT) != manifest["frozen_artifact_hashes"]:
        raise RuntimeError("frozen E1/E2-A/E2-B hashes changed")
    inventory = {}
    for line in (OUT / "HASHES.sha256").read_text(encoding="utf-8").splitlines():
        digest, name = line.split("  ", 1); inventory[name] = digest
    actual = {path.name for path in OUT.iterdir() if path.is_file()} - {"HASHES.sha256"}
    if set(inventory) != actual:
        raise RuntimeError("E2-C hash inventory incomplete")
    for name, digest in inventory.items():
        if sha256_file(OUT / name) != digest: raise RuntimeError(f"E2-C hash mismatch: {name}")
    observations_rows = read_rows(OUT / "reliability_observations.csv")
    if len(observations_rows) != 3000 or sum(row["F_active_item"] == "True" for row in observations_rows) != 1160:
        raise RuntimeError("E2-C observation population mismatch")
    if any(row["reliability_level"] in {"R1", "R2"} and row["F_active_item"] != "True" for row in observations_rows):
        raise RuntimeError("paid R without F")
    analysis = json.loads((OUT / "e2c_analysis.json").read_text(encoding="utf-8"))
    if analysis["population"]["F_active_rows"] != 792:
        raise RuntimeError("aggregate F-active population mismatch")
    if manifest["analysis"]["optimization_runs"] != 0 or manifest["guardrails"]["E2_D_runs"] != 0:
        raise RuntimeError("forbidden scientific optimization recorded")
    if preflight["frozen_hashes"] != manifest["frozen_artifact_hashes"]:
        raise RuntimeError("preflight/manifest frozen hashes differ")
    print("E2-C deterministic solver-free verification PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("command", choices=("build", "verify")); args = parser.parse_args()
    return build() if args.command == "build" else verify()


if __name__ == "__main__":
    raise SystemExit(main())
