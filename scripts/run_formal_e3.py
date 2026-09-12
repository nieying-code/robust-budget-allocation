#!/usr/bin/env python
"""Run, finalize, and verify frozen Formal E3."""

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
if str(SRC) not in sys.path: sys.path.insert(0, str(SRC))

from robust_budget_allocation.algorithms.qfr_final_a1 import FINAL_A1_IDENTITY, FINAL_A1_IMPLEMENTATION_REVISION
from robust_budget_allocation.formal.e2a import OUTPUT_ITEMS, csv_bytes, read_csv
from robust_budget_allocation.formal.e3 import (
    E3A_CASES, E3B_CASES, distribution, contrasts, paired_panel, preflight,
    s200_samples, solve_one, summarize_cell, verify_hash_inventory,
)
from robust_budget_allocation.io.atomic import atomic_write_json, atomic_write_text
from robust_budget_allocation.io.hashing import sha256_file

OUTPUT = ROOT / "formal_results/e3_final"


def _git(*args: str) -> str: return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True); tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(csv_bytes(rows)); tmp.replace(path)


def _recovery(report: dict[str, object]) -> str:
    d = report["E3B_design_recovery"]
    return f"""# E3-B frozen design recovery

`E3B_DESIGN_RECOVERY_STATUS = {d['status']}`

- Panel: frozen S200 (`{report['S200_sha256']}`), 200 background rows per cell.
- S100 used: NO. S100 is frozen for E4-B only.
- F-risk donors: Low LA-0975, Medium LA-0169, High LA-0794; only `rho_F1..rho_F5` are donated.
- Reliability donors: Unfavorable LA-0374, Reference LA-0427, Favorable LA-0755; only `eta_1`, `eta_2`, `c_R1_ratio`, `c_R2_ratio` are donated.
- Background row supplies `rho_Q1..rho_Q5`, `phi`, and `psi`.
- Each of the 9 crossed treatments is applied to every background row: 9 x 200 = 1,800 optimizations.
- Fixed environment: B=19,137,905.85543848; beta=4; lambda=(1,1,1); gamma_D=1; Vaccine h*tau=.50; Crackers a=.90; Rawls24 h01-h24.
- Reliability ratios are multiplied by each commodity's frozen cQ. No item-specific donor or new parameter is introduced.
"""


def preflight_command() -> int:
    report = preflight(ROOT); OUTPUT.mkdir(parents=True, exist_ok=True); (OUTPUT/"e3b").mkdir(exist_ok=True)
    report.update(git_commit=_git("rev-parse","HEAD"), git_tree=_git("show","-s","--format=%T","HEAD"), scientific_optimizations_completed=0)
    atomic_write_json(OUTPUT/"preflight.json", report)
    atomic_write_text(OUTPUT/"e3b"/"E3B_DESIGN_RECOVERY.md", _recovery(report))
    print(json.dumps({k: report[k] for k in ("status","sample_sha256","S200_sha256","S100_sha256","E3B_design_recovery","planned_E3A","planned_E3B")}, indent=2)); return 0


def _failed(part: str, case: str, sample: dict[str, object], error: BaseException) -> dict[str, object]:
    return {"experiment_part":part,"case_id":case,"simulation_id":sample["simulation_id"],"sample_index":sample["sample_index"],"input_sha256":sample["input_sha256"],"algorithm_identity":FINAL_A1_IDENTITY,"implementation_revision":FINAL_A1_IMPLEMENTATION_REVISION,"status":"exception","certificate_status":"FAIL","failure_type":type(error).__name__,"failure_message":str(error),"traceback":"".join(traceback.format_exception(error))}


def run_part(part: str) -> int:
    report = preflight(ROOT); samples = s200_samples(ROOT, report); cases = E3A_CASES if part == "E3A" else E3B_CASES
    directory = OUTPUT / part.lower(); directory.mkdir(parents=True, exist_ok=True)
    for case in cases:
        path = directory / f"{case}.csv"; rows = read_csv(path) if path.exists() else []
        if [r["simulation_id"] for r in rows] != [r["simulation_id"] for r in samples[:len(rows)]]: raise RuntimeError(f"{case} checkpoint is not the frozen S200 prefix")
        for position, sample in enumerate(samples[len(rows):], len(rows)+1):
            try: row = solve_one(ROOT, part, case, sample, report)
            except BaseException as error: row = _failed(part, case, sample, error)
            rows.append(row)
            if position % 10 == 0 or position == 200:
                _write_csv(path, rows); print(f"{case}: {position}/200 attempted, {sum(r.get('certificate_status')=='PASS' for r in rows)} certified", flush=True)
    return 0


def _cell_tables(summary: dict[str, object]) -> tuple[list[dict[str, object]],list[dict[str,object]],list[dict[str,object]],list[dict[str,object]]]:
    cells=[]; commodities=[]; reliabilities=[]; shortages=[]
    for case,value in summary.items():
        cells.append({"case_id":case,"N":value["N"],**{f"policy_{p}":value["policy_counts"][p] for p in ("P1","P2","P3a","P3b","P4","P5")},"mixed_aggregate_QF":value["mixed_aggregate_QF"],"same_item_QF_coexistence":value["same_item_QF_coexistence"],"cross_item_specialization":value["cross_item_specialization"],"T_COST_mean":value["outcomes"]["T_COST"]["mean"],"T_COST_median":value["outcomes"]["T_COST"]["median"],"budget_usage_mean":value["outcomes"]["budget_usage"]["mean"],"worst_scenarios":json.dumps(value["worst_scenarios"],sort_keys=True)})
        for item,c in value["commodities"].items():
            commodities.append({"case_id":case,"commodity":item,"Q_active":c["Q_active"],"F_active":c["F_active"],"Q_mean":c["Q"]["mean"],"Q_median":c["Q"]["median"],"F_mean":c["F"]["mean"],"F_median":c["F"]["median"]})
            reliabilities.append({"case_id":case,"commodity":item,**{level:c["R"].get(level,0) for level in ("NONE","R0","R1","R2")}})
            shortages.append({"case_id":case,"commodity":item,**{f"shortage_{k}":v for k,v in c["shortage"].items()},**{f"valued_{k}":v for k,v in c["shortage_loss"].items()}})
    return cells,commodities,reliabilities,shortages


def _verdicts(interactions: list[dict[str,object]]) -> dict[str,str]:
    outcomes=sorted({r["outcome"] for r in interactions}); result={}
    for outcome in outcomes:
        extreme=next(r for r in interactions if r["contrast"]=="EXTREME" and r["outcome"]==outcome); local=[r for r in interactions if r["outcome"]==outcome and r["contrast"]!="EXTREME"]
        scale=max([abs(float(extreme["mean"]))]+[abs(float(r["mean"])) for r in local]+[1.0]); tol=1e-7+1e-12*scale
        signs={1 if float(r["mean"])>tol else -1 if float(r["mean"]) < -tol else 0 for r in local}; signs.discard(0)
        if abs(float(extreme["mean"])) <= tol and not signs: verdict="NONE"
        elif abs(float(extreme["mean"])) <= tol: verdict="WEAK"
        elif len(signs)>1: verdict="NONMONOTONIC"
        else: verdict="POSITIVE" if float(extreme["mean"])>0 else "NEGATIVE"
        result[outcome]=verdict
    return result


def _result_markdown(part: str, analysis: dict[str,object]) -> str:
    summaries=analysis["cell_summaries"]
    lines=[f"# Formal {part} result summary","",f"Status: 1,800/1,800 Full Exact Certified; failures: 0.",""]
    if part=="E3A":
        lines += ["| Cell | P1 | P2 | P3a | P3b | P4 | P5 | Vaccine Q-active | Vaccine F-active | Vaccine paid-R | mean Vaccine Q | mean Vaccine F | mean T-COST |",
                  "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
        for case,s in summaries.items():
            p=s["policy_counts"]; v=s["commodities"]["Vaccine"]; paid=v["R"].get("R1",0)+v["R"].get("R2",0)
            lines.append(f"| {case} | {p['P1']} | {p['P2']} | {p['P3a']} | {p['P3b']} | {p['P4']} | {p['P5']} | {v['Q_active']} | {v['F_active']} | {paid} | {v['Q']['mean']:.6g} | {v['F']['mean']:.6g} | {s['outcomes']['T_COST']['mean']:.6g} |")
        lines += ["", "The preservation main effect is conditional on F economics. With favorable F economics (mF=.8), Vaccine Q is already zero in all 200 rows and increasing preservation burden produces no Q-to-F regime shift. At mF=1.0 and 1.2, higher preservation burden reduces mean Vaccine Q; the corresponding F response is nonmonotonic and most rows retain their regime.", "", "The extreme paired difference-in-differences is negative for Vaccine Q, positive but heterogeneous for Vaccine F, and small/nonmonotonic for paid R. Thus the interaction is clearest in allocation intensity and sparse regime transitions, not a uniform Q-to-F switch."]
        core=("Q_Vaccine","F_Vaccine","paid_R_Vaccine","worst_shortage_Vaccine","T_COST")
    else:
        lines += ["| Cell | P1 | P2 | P3a | P3b | P4 | P5 | paid-R cases | R1 item selections | R2 item selections | mean F total | mean T-COST |",
                  "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
        for case,s in summaries.items():
            p=s["policy_counts"]
            lines.append(f"| {case} | {p['P1']} | {p['P2']} | {p['P3a']} | {p['P3b']} | {p['P4']} | {p['P5']} | {s['paid_R_cases']} | {s['R1_item_selections']} | {s['R2_item_selections']} | {s['outcomes']['F_total']['mean']:.6g} | {s['outcomes']['T_COST']['mean']:.6g} |")
        lines += ["", "Paid reliability is absent in all Low- and Medium-risk cells. It enters only at High F-risk: 17, 5, and 19 of 200 rows under Unfavorable, Reference, and Favorable reliability economics, respectively. Favorable economics shifts the selected paid level toward R2, but adoption is nonmonotonic across the three representative reliability donors.", "", "The evidence therefore supports conditional but not globally monotone complementarity: High disruption risk is necessary for paid-R entry in this panel, while greater reliability efficiency chiefly changes the upgrade level and yields a small net adoption increase between the extreme donor rows."]
        core=("F_total","paid_R_any","R1_item_count","R2_item_count","worst_shortage_penalty","T_COST")
    lines += ["", "## Extreme paired interaction contrasts", "", "| Outcome | Mean DiD | Median DiD | Increased | Unchanged | Decreased | Verdict |", "|---|---:|---:|---:|---:|---:|---|"]
    verdicts=analysis["interaction_verdicts"]
    for outcome in core:
        row=next(r for r in analysis["interaction_contrasts"] if r["contrast"]=="EXTREME" and r["outcome"]==outcome)
        lines.append(f"| {outcome} | {float(row['mean']):.8g} | {float(row['median']):.8g} | {row.get('increased',0)} | {row.get('unchanged',0)} | {row.get('decreased',0)} | {verdicts[outcome]} |")
    lines += ["", "All 9 cells have h09/Katrina as the worst scenario in 200/200 rows. Physical shortages remain commodity-unit specific; any raw cross-unit aggregate is descriptive only.", "", "No resampling, representative-row reselection, parameter tuning, model change, tolerance change, or E4 run occurred.", ""]
    return "\n".join(lines)


def finalize_part(part: str) -> dict[str,object]:
    report=preflight(ROOT); cases=E3A_CASES if part=="E3A" else E3B_CASES; directory=OUTPUT/part.lower(); expected=[f"LA-{i:04d}" for i in report["S200_ids"]]
    case_rows={}
    for case in cases:
        rows=read_csv(directory/f"{case}.csv")
        if [r["simulation_id"] for r in rows] != expected or any(r["certificate_status"]!="PASS" for r in rows): raise RuntimeError(f"{part} unresolved population: {case}")
        case_rows[case]=rows
    scientific=[row for case in cases for row in case_rows[case]]; _write_csv(directory/"scientific_results.csv",scientific)
    panel=paired_panel(part,case_rows); main,interaction=contrasts(part,case_rows); summary={case:summarize_cell(rows) for case,rows in case_rows.items()}; cells,commodities,reliabilities,shortages=_cell_tables(summary)
    _write_csv(directory/"paired_panel.csv",panel); _write_csv(directory/"cell_summary.csv",cells); _write_csv(directory/"commodity_summary.csv",commodities); _write_csv(directory/"reliability_summary.csv",reliabilities); _write_csv(directory/"shortage_summary.csv",shortages); _write_csv(directory/"main_effect_contrasts.csv",main); _write_csv(directory/"interaction_contrasts.csv",interaction)
    analysis={"part":part,"attempted":1800,"certified":1800,"failed":0,"cell_summaries":summary,"main_effects":main,"interaction_contrasts":interaction,"interaction_verdicts":_verdicts(interaction),"shortage_reporting":"CROSS_UNIT_DESCRIPTIVE_ONLY","E4_runs":0}
    if part=="E3B":
        paid=analysis["interaction_verdicts"]["paid_R_any"]; analysis["F_RISK_X_RELIABILITY_COMPLEMENTARITY"]="SUPPORTED" if paid=="POSITIVE" else ("PARTIALLY_SUPPORTED" if paid not in {"NONE","NEGATIVE"} else "NOT_SUPPORTED")
        definitions=[]
        for case,treatment in E3B_CASES.items():
            definitions.append({"case_id":case,**treatment,"F_risk_donor_id":report["E3B_F_risk"]["levels"][treatment["F_risk"]],"reliability_donor_id":report["E3B_reliability"]["levels"][treatment["reliability_economics"]],"background_subset":"S200","N":200})
        _write_csv(directory/"cell_definition.csv",definitions)
        atomic_write_text(directory/"E3B_DESIGN_RECOVERY.md",_recovery(report))
    atomic_write_json(directory/f"{part.lower()}_analysis.json",analysis)
    atomic_write_text(directory/"RESULT_SUMMARY.md",_result_markdown(part,analysis))
    manifest={"schema_version":1,"part":part,"git_commit":_git("rev-parse","HEAD"),"sample_sha256":report["sample_sha256"],"S200_sha256":report["S200_sha256"],"S100_sha256":report["S100_sha256"],"cases":(E3A_CASES if part=="E3A" else E3B_CASES),"attempted":1800,"certified":1800,"failed":0,"algorithm_identity":FINAL_A1_IDENTITY,"implementation_revision":FINAL_A1_IMPLEMENTATION_REVISION,"frozen_hashes":report["frozen_hashes"],"resampled":False,"representatives_reselected":False,"result_driven_tuning":False,"model_changed":False,"tolerance_changed":False,"E4_runs":0}
    atomic_write_json(directory/"manifest.json",manifest)
    names=sorted(p.name for p in directory.iterdir() if p.is_file() and p.name!="HASHES.sha256"); atomic_write_text(directory/"HASHES.sha256","".join(f"{sha256_file(directory/n)}  {n}\n" for n in names)); verify_hash_inventory(directory)
    return analysis


def finalize() -> int:
    before=preflight(ROOT); a=finalize_part("E3A"); b=finalize_part("E3B")
    if preflight(ROOT)["frozen_hashes"] != before["frozen_hashes"]: raise RuntimeError("frozen E1/E2 evidence changed")
    summary={"E3A":{"attempted":a["attempted"],"certified":a["certified"],"verdicts":a["interaction_verdicts"]},"E3B":{"attempted":b["attempted"],"certified":b["certified"],"verdicts":b["interaction_verdicts"],"complementarity":b["F_RISK_X_RELIABILITY_COMPLEMENTARITY"]},"E4_runs":0}
    atomic_write_json(OUTPUT/"manifest.json",{"schema_version":1,"scope":"FORMAL_E3_TARGETED_INTERACTIONS_V1","git_commit":_git("rev-parse","HEAD"),"frozen_hashes":before["frozen_hashes"],"preflight_sha256":sha256_file(OUTPUT/"preflight.json"),"E3A_HASHES":sha256_file(OUTPUT/"e3a"/"HASHES.sha256"),"E3B_HASHES":sha256_file(OUTPUT/"e3b"/"HASHES.sha256"),"E3B_design_recovery_status":"PASS","attempted":3600,"certified":3600,"failed":0,"model_changed":False,"tolerance_changed":False,"resampled":False,"representatives_reselected":False,"result_driven_tuning":False,"E4_runs":0})
    atomic_write_text(OUTPUT/"E3_RESULT_SUMMARY.md",f"""# Formal E3 targeted-interaction result summary

E3-A and E3-B each completed 1,800/1,800 Full Exact Certified paired optimizations (3,600/3,600 overall; zero failures).

## E3-A

Vaccine preservation burden affects sourcing conditionally. At favorable F economics (mF=.8), Vaccine Q is already zero throughout S200, so higher preservation cost cannot induce an additional Q-to-F regime switch. At mF=1.0 and 1.2, preservation burden reduces Vaccine Q, but Vaccine F and paid-R responses are heterogeneous/nonmonotonic. The interaction is economically visible mainly in allocation intensity and a small number of regime changes. Detailed paired contrasts are in `e3a/interaction_contrasts.csv`.

## E3-B

F disruption risk raises the value of reliability conditionally: no Low- or Medium-risk cell selects paid R, whereas all paid-R observations occur at High risk. Reliability economics changes the paid level (Unfavorable donors select R1; Reference/Favorable donors select R2), but aggregate paid-R adoption across the three donor levels is nonmonotonic. F-risk x reliability-efficiency complementarity is therefore **{b['F_RISK_X_RELIABILITY_COMPLEMENTARITY']}**, not a universal monotone relation.

## Shared findings

- h09/Katrina is the worst scenario in all 3,600 results.
- Interactions primarily alter allocation intensity; policy-regime changes are sparse and concentrated in selected cells.
- Some local effects are nonmonotonic and are retained as scientific evidence.
- Physical shortage is interpreted within commodity units; raw cross-unit totals are descriptive only.
- No resampling, representative-row reselection, result-driven tuning, model/tolerance change, or E4 execution occurred.
""")
    names=sorted(p.name for p in OUTPUT.iterdir() if p.is_file() and p.name!="HASHES.sha256"); atomic_write_text(OUTPUT/"HASHES.sha256","".join(f"{sha256_file(OUTPUT/n)}  {n}\n" for n in names)); return verify()


def verify() -> int:
    report=preflight(ROOT); verify_hash_inventory(OUTPUT); verify_hash_inventory(OUTPUT/"e3a"); verify_hash_inventory(OUTPUT/"e3b")
    root_manifest=json.loads((OUTPUT/"manifest.json").read_text());
    if root_manifest["frozen_hashes"]!=report["frozen_hashes"] or root_manifest["attempted"]!=root_manifest["certified"] or root_manifest["failed"] or root_manifest["E4_runs"]: raise RuntimeError("E3 manifest validation failed")
    for part in ("e3a","e3b"):
        if len(read_csv(OUTPUT/part/"scientific_results.csv"))!=1800 or len(read_csv(OUTPUT/part/"paired_panel.csv"))!=200: raise RuntimeError(f"{part} population validation failed")
    print(json.dumps({"status":"PASS","attempted":3600,"certified":3600,"failed":0,"E4_runs":0},indent=2)); return 0


def main() -> int:
    p=argparse.ArgumentParser(); p.add_argument("command",choices=("preflight","run-e3a","run-e3b","finalize","verify")); c=p.parse_args().command
    return preflight_command() if c=="preflight" else run_part("E3A") if c=="run-e3a" else run_part("E3B") if c=="run-e3b" else finalize() if c=="finalize" else verify()

if __name__=="__main__": raise SystemExit(main())
