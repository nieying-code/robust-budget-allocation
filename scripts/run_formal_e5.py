#!/usr/bin/env python
"""Preflight, execute, finalize, and verify Formal E5-A only."""

from __future__ import annotations

import argparse
import csv
import io
import json
from pathlib import Path
import statistics
import subprocess
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path: sys.path.insert(0, str(SRC))

from robust_budget_allocation.algorithms.qfr_final_a1 import solve_qfr_final_a1
from robust_budget_allocation.algorithms.qfr_standard_ccg import solve_qfr_standard_ccg
from robust_budget_allocation.formal.e5a import (
    E5A, OUTPUT, compare_instance, data_for_sample, diagnostic_summary, distribution,
    execution_order, frozen_hashes, preflight, s200_samples, summarize_runtime, timing_row,
    verify_repetitions,
)
from robust_budget_allocation.io.atomic import atomic_write_json, atomic_write_text
from robust_budget_allocation.io.hashing import sha256_file


def _git(*args: str) -> str: return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def _csv_bytes(rows):
    if not rows: raise ValueError("empty E5-A CSV")
    stream = io.StringIO(newline=""); writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader(); writer.writerows(rows); return stream.getvalue()


def _read(path: Path):
    if not path.exists(): return []
    with path.open(encoding="utf-8", newline="") as handle: return list(csv.DictReader(handle))


def _write(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True); tmp = path.with_suffix(path.suffix+".tmp")
    tmp.write_text(_csv_bytes(rows), encoding="utf-8", newline=""); tmp.replace(path)


def _hash_inventory(directory: Path) -> None:
    names = sorted(path.name for path in directory.iterdir() if path.is_file() and path.name != "HASHES.sha256")
    atomic_write_text(directory/"HASHES.sha256", "".join(f"{sha256_file(directory/name)}  {name}\n" for name in names))


def command_preflight() -> int:
    report = preflight(ROOT)
    if _git("branch", "--show-current") != "r13/formal-e5-algorithm-performance": raise RuntimeError("wrong E5 branch")
    report.update(git_commit=_git("rev-parse","HEAD"), git_tree=_git("show","-s","--format=%T","HEAD"), E5A_completed=0)
    OUTPUT.mkdir(parents=True, exist_ok=True); E5A.mkdir(parents=True, exist_ok=True)
    atomic_write_json(OUTPUT/"preflight.json", report)
    atomic_write_text(OUTPUT/"E5_DESIGN_FREEZE.md", f"""# Formal E5 design freeze — E5-A execution stage

- Dataset: Rawls24; items: Water, Seasonal Influenza Vaccine, Crackers.
- Frozen subset: S200 `{report['S200_sha256']}`.
- Algorithms: production A0 and `A1_FINAL_NO_MEMORY_V1` (`{report['implementation_revision']}`).
- Timing: three repetitions per algorithm-instance; wall clock surrounds only the solver call.
- Order: paired and interleaved; `(S200 position + repetition)` even runs A0 then A1, odd runs A1 then A0.
- Runtime unit: seconds. Per-instance comparison uses the median of three repetitions.
- No post-hoc tie band: strict measured ordering is reported.
- Correctness precedes runtime interpretation. E5-A cannot support a scalability claim.
- E5-B runs: 0. E5-C runs: 0.
""")
    print(json.dumps({k: report[k] for k in ("status","sample_sha256","S200_sha256","A0_identity","A1_identity","implementation_revision","instances","A0_timed_runs","A1_timed_runs","E5B_runs","E5C_runs")}, indent=2)); return 0


def command_run() -> int:
    report = preflight(ROOT); samples = s200_samples(ROOT, report); path = E5A/"raw_timing.csv"; rows = _read(path)
    if len(rows) % 6: raise RuntimeError("checkpoint is not at an instance boundary")
    completed = len(rows)//6
    expected_prefix = [sample["simulation_id"] for sample in samples[:completed]]
    actual_prefix = [rows[index*6]["simulation_id"] for index in range(completed)]
    if actual_prefix != expected_prefix: raise RuntimeError("checkpoint is not frozen S200 prefix")
    sequence = len(rows)
    for position, sample in enumerate(samples[completed:], completed+1):
        data = data_for_sample(ROOT, sample); instance=[]
        for repetition in range(1,4):
            order = execution_order(position, repetition)
            for order_in_pair, algorithm in enumerate(order, 1):
                started=perf_counter()
                result = solve_qfr_standard_ccg(data,"M2") if algorithm=="A0" else solve_qfr_final_a1(data,"M2")
                wall=perf_counter()-started; sequence += 1
                row=timing_row(sample,position,repetition,algorithm,order_in_pair,wall,result); row["execution_sequence"]=sequence
                instance.append(row)
        rows.extend(instance); _write(path,rows)
        print(f"E5-A: {position}/200 instances, {len(rows)}/1200 timed runs",flush=True)
    return 0


def command_finalize() -> int:
    report=preflight(ROOT); before=report["frozen_hashes"]; rows=_read(E5A/"raw_timing.csv"); verify_repetitions(rows)
    by={}
    for row in rows: by.setdefault((row["simulation_id"],row["algorithm"]),[]).append(row)
    instances=[]; comparisons=[]
    for position,index in enumerate(report["S200_ids"],1):
        sid=f"LA-{int(index):04d}"; a0=sorted(by[(sid,"A0")],key=lambda r:int(r["repetition"])); a1=sorted(by[(sid,"A1")],key=lambda r:int(r["repetition"]))
        med0=statistics.median(float(r["wall_clock_seconds"]) for r in a0); med1=statistics.median(float(r["wall_clock_seconds"]) for r in a1)
        instances.append({"simulation_id":sid,"sample_index":index,"S200_position":position,"A0_median_runtime_seconds":med0,"A1_median_runtime_seconds":med1,"speedup_A0_over_A1":med0/med1,"A0_iterations":a0[0]["iterations"],"A1_iterations":a1[0]["iterations"]})
        comparisons.append(compare_instance(a0[0],a1[0]))
    if any(str(row["objective_agreement"]).lower()!="true" for row in comparisons): raise RuntimeError("A0/A1 objective disagreement; runtime conclusions forbidden")
    _write(E5A/"instance_summary.csv",instances); _write(E5A/"correctness_comparison.csv",comparisons)
    runtime=summarize_runtime(instances); diagnostics={"A0":diagnostic_summary(rows,"A0"),"A1":diagnostic_summary(rows,"A1")}
    _write(E5A/"runtime_summary.csv",[{"algorithm":algorithm,**values} for algorithm,values in (("A0",runtime["A0"]),("A1",runtime["A1"]))])
    _write(E5A/"speedup_summary.csv",[{**runtime["speedup_A0_over_A1"],"geometric_mean":runtime["geometric_mean_speedup"],"A1_faster":runtime["A1_faster"],"A0_faster":runtime["A0_faster"],"ties":runtime["exact_wall_clock_ties"],"tie_rule":runtime["tie_rule"]}])
    _write(E5A/"a1_diagnostics.csv",[{"metric":key,**value} for key,value in diagnostics["A1"].items() if isinstance(value,dict)])
    differences=[float(row["absolute_objective_difference"]) for row in comparisons]
    correctness={"instances":200,"objective_agreement":sum(str(r["objective_agreement"]).lower()=="true" for r in comparisons),"objective_difference":distribution(differences),"same_decision":sum(str(r["decision_equivalent"]).lower()=="true" for r in comparisons),"objective_equivalent_decision_different":sum(r["classification"]!="SAME_OBJECTIVE_AND_DECISION" for r in comparisons),"A1_full_exact_certified":sum(str(r["A1_full_exact_certificate"]).lower()=="true" for r in comparisons)}
    analysis={"status":"PASS","execution":{"instances":200,"timing_repetitions":3,"A0_timed_runs":600,"A1_timed_runs":600,"failed":0},"correctness":correctness,"runtime":runtime,"diagnostics":diagnostics,"interpretation_boundary":"RAWLS24_I3_S200_ONLY_NO_SCALABILITY_CLAIM","E5B_runs":0,"E5C_runs":0}
    atomic_write_json(E5A/"analysis.json",analysis)
    atomic_write_text(E5A/"RESULT_SUMMARY.md",f"""# Formal E5-A result summary

All 200 frozen S200 Rawls24 instances completed three timing repetitions with A0 and Final no-memory A1 (1,200/1,200 certified timed runs; zero failures). A0/A1 objective agreement: {correctness['objective_agreement']}/200; maximum absolute objective difference: {correctness['objective_difference']['max']:.12g}. Objective-equivalent decision-different cases: {correctness['objective_equivalent_decision_different']} (consistent with, but not proof of, alternative optima/degeneracy).

Median-of-three runtime: A0 median {runtime['A0']['median']:.6g}s; A1 median {runtime['A1']['median']:.6g}s. Median paired speedup A0/A1: {runtime['speedup_A0_over_A1']['median']:.6g}. A1 faster on {runtime['A1_faster']} instances, A0 faster on {runtime['A0_faster']}, exact measured ties {runtime['exact_wall_clock_ties']}.

This is a Rawls24, I=3 baseline comparison only. It does not establish scalability; E5-B and E5-C were not executed. No model, tolerance, parameter, subset, or algorithm tuning occurred, and Memory is absent.
""")
    manifest={"schema_version":1,"scope":"FORMAL_E5A_RAWLS24_ALGORITHM_COMPARISON_V1","source_commit":json.loads((OUTPUT/"preflight.json").read_text())["git_commit"],"sample_sha256":report["sample_sha256"],"S200_sha256":report["S200_sha256"],"algorithms":[report["A0_identity"],report["A1_identity"]],"implementation_revision":report["implementation_revision"],"timing_boundary":report["timing_boundary"],"execution_order":report["execution_order"],"tie_rule":report["tie_rule"],"instances":200,"timing_repetitions":3,"timed_runs":1200,"certified":1200,"failed":0,"frozen_hashes":before,"model_changed":False,"tolerance_changed":False,"parameter_recalibration":False,"S200_reselected":False,"algorithm_tuned":False,"memory":False,"result_deleted_or_replaced":False,"E5B_runs":0,"E5C_runs":0}
    atomic_write_json(E5A/"manifest.json",manifest); _hash_inventory(E5A)
    if frozen_hashes(ROOT)!=before: raise RuntimeError("frozen E1-E4 evidence changed")
    atomic_write_json(OUTPUT/"manifest.json",{"schema_version":1,"scope":"FORMAL_E5_V1_E5A_ONLY","E5A_manifest_sha256":sha256_file(E5A/"manifest.json"),"E5A_hash_inventory_sha256":sha256_file(E5A/"HASHES.sha256"),"frozen_hashes":before,"E5A_timed_runs":1200,"E5B_runs":0,"E5C_runs":0})
    _hash_inventory(OUTPUT); return command_verify()


def command_verify() -> int:
    from robust_budget_allocation.formal.e2d_audit import verify_hash_inventory
    report=preflight(ROOT); verify_hash_inventory(E5A); verify_hash_inventory(OUTPUT)
    rows=_read(E5A/"raw_timing.csv"); verify_repetitions(rows)
    analysis=json.loads((E5A/"analysis.json").read_text()); manifest=json.loads((E5A/"manifest.json").read_text())
    if analysis["correctness"]["objective_agreement"]!=200 or analysis["execution"]["failed"] or manifest["frozen_hashes"]!=report["frozen_hashes"] or manifest["E5B_runs"] or manifest["E5C_runs"]: raise RuntimeError("E5-A verification failed")
    print(json.dumps({"status":"PASS","instances":200,"timed_runs":1200,"certified":1200,"failed":0,"objective_agreement":200,"E5B_runs":0,"E5C_runs":0},indent=2)); return 0


def main() -> int:
    p=argparse.ArgumentParser(); p.add_argument("command",choices=("preflight","run-e5a","finalize","verify")); c=p.parse_args().command
    return command_preflight() if c=="preflight" else command_run() if c=="run-e5a" else command_finalize() if c=="finalize" else command_verify()

if __name__=="__main__": raise SystemExit(main())
