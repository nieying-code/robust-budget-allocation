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


def command_preflight_e5b() -> int:
    from robust_budget_allocation.formal.e5b import E5B, preflight as e5b_preflight
    report=e5b_preflight(ROOT); E5B.mkdir(parents=True,exist_ok=True)
    report.update(git_commit=_git("rev-parse","HEAD"),git_tree=_git("show","-s","--format=%T","HEAD"),E5B_completed=0)
    atomic_write_json(E5B/"design_identity.json",report)
    _write(E5B/"replicate_selection.csv",[{"replicate_id":f"E5B-R{i:02d}","seed":row["seed"],"selected_E1_row_id":row["parameter_row_id"],"selection_rule":"FIRST_PCG64_DRAW_UNIFORM_INTEGER_1_1000"} for i,row in enumerate(report["replicates"],1)])
    _write(E5B/"scenario_pool_manifest.csv",[{"replicate_id":f"E5B-R{i:02d}","seed":row["seed"],"master_500_sha256":row["master_500_sha256"],**{f"Omega{size}_sha256":row["prefix_sha256"][str(size)] for size in (50,100,200,500)},"nesting":"GENERATION_ORDER_PREFIXES_NO_SORTING"} for i,row in enumerate(report["replicates"],1)])
    _write(E5B/"budget_manifest.csv",[{"replicate_id":f"E5B-R{i:02d}","seed":row["seed"],"B_ref_full500":row["B_r_bench"],"B_used_50":row["B_r_bench"],"B_used_100":row["B_r_bench"],"B_used_200":row["B_r_bench"],"B_used_500":row["B_r_bench"],"B_ref_sha256":row["B_r_bench_sha256"]} for i,row in enumerate(report["replicates"],1)])
    print(json.dumps({k:report[k] for k in ("status","generator_identity","generator_sha256","seeds","parameter_row_ids","nested_prefixes_verified","unique_instances","A0_timed_runs","A1_timed_runs","E5C_runs")},indent=2)); return 0


def command_run_e5b() -> int:
    from robust_budget_allocation.formal.e5a import execution_order, timing_row
    from robust_budget_allocation.formal.e5b import E5B, data_for_instance, generated_replicate, preflight as e5b_preflight, recovery_counts, sample_by_id
    report=e5b_preflight(ROOT); path=ROOT/E5B/"raw_timing.csv"; rows=_read(path)
    if len(rows)%6: raise RuntimeError("E5-B checkpoint is not at an instance boundary")
    completed=len(rows)//6; instances=[(i+1,row,size) for i,row in enumerate(report["replicates"]) for size in (50,100,200,500)]
    for position,(replicate_number,identity,size) in enumerate(instances[completed:],completed+1):
        seed=int(identity["seed"]); generated=generated_replicate(ROOT,seed); sample=sample_by_id(ROOT,int(identity["parameter_row_id"])); data=data_for_instance(ROOT,generated,sample,size,float(identity["B_r_bench"])); batch=[]
        for repetition in range(1,4):
            for order_in_pair,algorithm in enumerate(execution_order(position,repetition),1):
                started=perf_counter(); result=solve_qfr_standard_ccg(data,"M2") if algorithm=="A0" else solve_qfr_final_a1(data,"M2"); wall=perf_counter()-started
                row=timing_row(sample,position,repetition,algorithm,order_in_pair,wall,result); row.update(replicate_id=f"E5B-R{replicate_number:02d}",seed=seed,scenario_size=size,benchmark_instance_id=f"E5B-R{replicate_number:02d}-O{size}",B_ref_full500=identity["B_r_bench"],prefix_sha256=identity["prefix_sha256"][str(size)],**recovery_counts(result)); row["execution_sequence"]=len(rows)+len(batch)+1; batch.append(row)
        rows.extend(batch); _write(path,rows); print(f"E5-B: {position}/120 instances, {len(rows)}/720 timed runs",flush=True)
    return 0


def command_finalize_e5b() -> int:
    from robust_budget_allocation.formal.e5a import compare_instance, diagnostic_summary, distribution, summarize_runtime
    from robust_budget_allocation.formal.e5b import E5B, SIZES, growth_distribution, preflight as e5b_preflight, verify_timing_population
    report=e5b_preflight(ROOT); before=report["frozen_hashes"]; e5a_hash=report["E5A_hash_inventory_sha256"]; directory=ROOT/E5B; rows=_read(directory/"raw_timing.csv"); verify_timing_population(rows)
    by={}
    for row in rows: by.setdefault((row["benchmark_instance_id"],row["algorithm"]),[]).append(row)
    instances=[]; comparisons=[]
    for replicate in range(1,31):
        for size in SIZES:
            key=f"E5B-R{replicate:02d}-O{size}"; a0=sorted(by[(key,"A0")],key=lambda r:int(r["repetition"])); a1=sorted(by[(key,"A1")],key=lambda r:int(r["repetition"])); med0=statistics.median(float(r["wall_clock_seconds"]) for r in a0); med1=statistics.median(float(r["wall_clock_seconds"]) for r in a1)
            instances.append({"benchmark_instance_id":key,"replicate_id":f"E5B-R{replicate:02d}","seed":a0[0]["seed"],"selected_E1_row_id":a0[0]["sample_index"],"scenario_size":size,"B_ref_full500":a0[0]["B_ref_full500"],"A0_median_runtime_seconds":med0,"A1_median_runtime_seconds":med1,"speedup_A0_over_A1":med0/med1,"A0_iterations":a0[0]["iterations"],"A1_iterations":a1[0]["iterations"]})
            compared=compare_instance(a0[0],a1[0]); compared.update(benchmark_instance_id=key,replicate_id=f"E5B-R{replicate:02d}",scenario_size=size); comparisons.append(compared)
    if any(not row["objective_agreement"] for row in comparisons): raise RuntimeError("E5-B A0/A1 objective disagreement")
    _write(directory/"instance_summary.csv",instances); _write(directory/"correctness_comparison.csv",comparisons)
    runtime_rows=[]; speed_rows=[]; size_analysis={}; diagnostic_rows=[]
    for size in SIZES:
        subset=[r for r in instances if r["scenario_size"]==size]; runtime=summarize_runtime(subset); size_analysis[str(size)]=runtime
        for algorithm in ("A0","A1"): runtime_rows.append({"scenario_size":size,"algorithm":algorithm,**runtime[algorithm]})
        speed_rows.append({"scenario_size":size,**runtime["speedup_A0_over_A1"],"geometric_mean":runtime["geometric_mean_speedup"],"A1_faster":runtime["A1_faster"],"A0_faster":runtime["A0_faster"],"ties":runtime["exact_wall_clock_ties"]})
        for algorithm in ("A0","A1"):
            diag=diagnostic_summary([r for r in rows if int(r["scenario_size"])==size],algorithm)
            for metric,value in diag.items():
                if isinstance(value,dict): diagnostic_rows.append({"scenario_size":size,"algorithm":algorithm,"metric":metric,**value})
    _write(directory/"runtime_by_size.csv",runtime_rows); _write(directory/"speedup_by_size.csv",speed_rows); _write(directory/"a1_diagnostics.csv",[r for r in diagnostic_rows if r["algorithm"]=="A1"])
    growth=[]; growth_summary={}; transitions=((50,100),(100,200),(200,500),(50,500))
    indexed={(r["replicate_id"],r["scenario_size"]):r for r in instances}
    for start,end in transitions:
        block=[]
        for replicate in range(1,31):
            rid=f"E5B-R{replicate:02d}"; left,right=indexed[(rid,start)],indexed[(rid,end)]; g0=float(right["A0_median_runtime_seconds"])/float(left["A0_median_runtime_seconds"]); g1=float(right["A1_median_runtime_seconds"])/float(left["A1_median_runtime_seconds"]); row={"replicate_id":rid,"transition":f"{start}_to_{end}","A0_growth":g0,"A1_growth":g1,"A0_over_A1_growth_ratio":g0/g1}; growth.append(row); block.append(row)
        growth_summary[f"{start}_to_{end}"]={"A0":growth_distribution([r["A0_growth"] for r in block]),"A1":growth_distribution([r["A1_growth"] for r in block]),"A0_over_A1":growth_distribution([r["A0_over_A1_growth_ratio"] for r in block])}
    _write(directory/"scaling_growth.csv",growth)
    recoveries=[{"benchmark_instance_id":r["benchmark_instance_id"],"algorithm":r["algorithm"],"repetition":r["repetition"],"scaled_retry_count":r["scaled_retry_count"],"witness_gated_retry_count":r["witness_gated_retry_count"]} for r in rows if int(r["scaled_retry_count"]) or int(r["witness_gated_retry_count"])]
    _write(directory/"numerical_recovery_audit.csv",recoveries or [{"benchmark_instance_id":"NONE","algorithm":"NONE","repetition":"","scaled_retry_count":0,"witness_gated_retry_count":0}])
    medians=[float(size_analysis[str(size)]["speedup_A0_over_A1"]["median"]) for size in SIZES]; majorities=[int(size_analysis[str(size)]["A1_faster"])>15 for size in SIZES]
    crossover="NO_CLEAR_CROSSOVER_OBSERVED"
    for at in range(1,len(SIZES)):
        if medians[at-1]<=1 and all(medians[j]>1 and majorities[j] for j in range(at,len(SIZES))): crossover=f"OBSERVED_CROSSOVER_AT_OR_BEFORE_OMEGA_{SIZES[at]}"; break
    diffs=[float(r["absolute_objective_difference"]) for r in comparisons]; correctness={"agreement":120,"objective_difference":distribution(diffs),"decision_different_objective_equivalent":sum(not r["decision_equivalent"] for r in comparisons),"worst_loss_agreement":sum(r["worst_loss_agreement"] for r in comparisons),"worst_scenario_agreement":sum(r["worst_scenario_equal"] for r in comparisons)}
    analysis={"status":"PASS","execution":{"instances":120,"timed_runs":720,"A0":360,"A1":360,"certified":720,"failed":0},"correctness":correctness,"runtime_by_size":size_analysis,"growth":growth_summary,"crossover":crossover,"numerical_recovery":{"scaled_retry_evaluations":sum(int(r["scaled_retry_count"]) for r in rows),"witness_gated_retry_evaluations":sum(int(r["witness_gated_retry_count"]) for r in rows),"runs_with_recovery":len(recoveries)},"interpretation_boundary":"SCENARIO_COUNT_SCALABILITY_ONLY_I_EQUALS_3_COMPUTATIONAL_BENCHMARK_NOT_EMPIRICAL_DISTRIBUTION","E5C_runs":0}
    atomic_write_json(directory/"analysis.json",analysis)
    atomic_write_text(directory/"RESULT_SUMMARY.md",f"# Formal E5-B result summary\n\nAll 120 nested scenario-count instances completed 720/720 certified timed runs with 120/120 A0/A1 objective agreement.\n\nObserved crossover verdict: **{crossover}**. This evidence concerns uncertainty-set size at I=3 only; E5-C was not executed. The synthetic generator is a computational benchmark, not an empirical disaster distribution.\n")
    manifest={"schema_version":1,"scope":"FORMAL_E5B_SCENARIO_SCALABILITY_V1","source_commit":json.loads((directory/"design_identity.json").read_text())["git_commit"],"generator_identity":report["generator_identity"],"generator_sha256":report["generator_sha256"],"seeds":report["seeds"],"parameter_row_ids":report["parameter_row_ids"],"scenario_sizes":list(SIZES),"instances":120,"timing_repetitions":3,"timed_runs":720,"certified":720,"failed":0,"budget_rule":report["budget_rule"],"timing_boundary":report["timing_boundary"],"execution_order":report["execution_order"],"A0_identity":report["A0_identity"],"A1_identity":report["A1_identity"],"implementation_revision":report["implementation_revision"],"E5A_hash_inventory_sha256":e5a_hash,"frozen_hashes":before,"model_changed":False,"tolerance_changed":False,"parameter_recalibration":False,"result_driven_selection":False,"resampled":False,"algorithm_tuned":False,"memory":False,"E5A_rerun":False,"E5C_runs":0}
    atomic_write_json(directory/"manifest.json",manifest); _hash_inventory(directory)
    if report["E5A_hash_inventory_sha256"]!=sha256_file(ROOT/"formal_results/e5_final/e5a/HASHES.sha256") or before!=__import__("robust_budget_allocation.formal.e5a",fromlist=["frozen_hashes"]).frozen_hashes(ROOT): raise RuntimeError("frozen evidence changed")
    root_manifest=json.loads((OUTPUT/"manifest.json").read_text()); root_manifest.update(E5B_manifest_sha256=sha256_file(directory/"manifest.json"),E5B_hash_inventory_sha256=sha256_file(directory/"HASHES.sha256"),E5B_runs=720,E5B_timed_runs=720,E5C_runs=0); atomic_write_json(OUTPUT/"manifest.json",root_manifest); _hash_inventory(OUTPUT); return command_verify_e5b()


def command_verify_e5b() -> int:
    from robust_budget_allocation.formal.e2d_audit import verify_hash_inventory
    from robust_budget_allocation.formal.e5b import E5B, preflight as e5b_preflight, verify_timing_population
    report=e5b_preflight(ROOT); directory=ROOT/E5B; verify_hash_inventory(directory); verify_hash_inventory(OUTPUT); rows=_read(directory/"raw_timing.csv"); verify_timing_population(rows); analysis=json.loads((directory/"analysis.json").read_text());
    if analysis["correctness"]["agreement"]!=120 or analysis["execution"]["failed"] or analysis["E5C_runs"]: raise RuntimeError("E5-B verification failed")
    print(json.dumps({"status":"PASS","instances":120,"timed_runs":720,"certified":720,"failed":0,"objective_agreement":120,"E5A_unchanged":True,"E5C_runs":0},indent=2)); return 0


def main() -> int:
    p=argparse.ArgumentParser(); p.add_argument("command",choices=("preflight","run-e5a","finalize","verify","preflight-e5b","run-e5b","finalize-e5b","verify-e5b")); c=p.parse_args().command
    if c=="preflight": return command_preflight()
    if c=="run-e5a": return command_run()
    if c=="finalize": return command_finalize()
    if c=="verify": return command_verify()
    if c=="preflight-e5b": return command_preflight_e5b()
    if c=="run-e5b": return command_run_e5b()
    if c=="finalize-e5b": return command_finalize_e5b()
    return command_verify_e5b()

if __name__=="__main__": raise SystemExit(main())
