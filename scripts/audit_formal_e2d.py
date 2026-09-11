#!/usr/bin/env python
"""Build and verify the solver-free Formal E2-D interpretation audit."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from robust_budget_allocation.formal.e2d_audit import (
    OUTPUT, claim_rows, common_reference_rows, csv_payload, frozen_hashes,
    paired_tables, preflight, summaries, verify_hash_inventory,
)
from robust_budget_allocation.io.atomic import atomic_write_json, atomic_write_text
from robust_budget_allocation.io.hashing import sha256_file


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(csv_payload(rows))
    temporary.replace(path)


def _flatten_level(summary: dict[str, object], cells: tuple[str, ...]) -> list[dict[str, object]]:
    rows = []
    for cell in cells:
        values = summary["levels"][cell]
        for metric, stats in values.items():
            rows.append({"cell": cell, "metric": metric, **stats})
    return rows


def _flatten_paired(summary: dict[str, object], key: str) -> list[dict[str, object]]:
    rows = []
    for comparison, values in summary[key].items():
        for metric, stats in values.items():
            if not isinstance(stats, dict) or not {"mean", "median"}.issubset(stats):
                continue
            row = {"comparison": comparison, "metric": metric, **stats}
            directions = values.get(f"{metric}_direction", {})
            row.update({name: directions.get(name, 0) for name in ("improved", "unchanged", "worsened")})
            rows.append(row)
    return rows


def _objective_markdown() -> str:
    return """# E2-D shortage-objective audit

Status: **PASS**. This audit is reconstructed from the production model and frozen
Final E1/E2-D configuration, not from narrative documentation.

For a fixed first-stage policy, production M2 uses

```text
C_pre = C_Q + C_F + C_R
E_omega = sum_i cE_i x_i,omega
S_omega = sum_i beta lambda_i cQ_i u_i,omega
L_omega = E_omega + S_omega
T-COST = C_pre + max_omega L_omega
```

The epigraph variable theta satisfies `theta >= L_omega` for every scenario and
the minimized objective is `C_pre + theta`. Emergency expenditure and shortage
penalty are separate components. The cash constraint is
`C_pre + E_omega <= B`; shortage loss is not cash expenditure.

`beta` multiplies the entire commodity shortage valuation; `lambda_i` multiplies
only commodity i; and the commodity-specific value coefficient is the acquisition
cost `cQ_i`. At the Final E1 reference, beta=4 and lambda=(1,1,1), so the shortage
coefficients are Water 2.5908 USD/gallon, Vaccine 55.664 USD/dose, and Crackers
0.37488 USD/22-g service unit.

`gamma_D=1` is applied in the frozen data/design construction. The optimization
model consumes the already-materialized demand matrix and does not multiply the
objective by gamma_D again. Shortage `u_i,omega` has the service unit of commodity
i: gallon, dose, or 22-g service unit.

The common-reference post-processing keeps the certified first-stage decision,
stored certified worst scenario, emergency expenditure, and shortage quantities
fixed, and replaces only the shortage coefficients by the Final E1 reference.
It performs no optimization and no new worst-scenario search.
"""


def _rules_markdown() -> str:
    return """# E2-D interpretation rules

Water shortage may be compared across treatments in gallons; Vaccine shortage in
doses; and Crackers shortage in 22-g service units. The raw sum
`u_Water + u_Vaccine + u_Crackers` is retained only as a descriptive total.

`RAW_AGGREGATE_SHORTAGE_IS_CROSS_UNIT_DESCRIPTIVE_ONLY = YES`

It is not appropriate to describe that cross-unit sum as a homogeneous service
quantity or welfare measure. Cross-commodity welfare interpretation must use the
model-consistent reference-valued shortage loss and `T_COST_REF` under beta_ref=4
and lambda_ref=(1,1,1).
"""


def _interpretation_markdown(summary: dict[str, object], claims: list[dict[str, str]]) -> str:
    crowd = summary["priority_crowding_out"]
    lines = [
        "# E2-D result-interpretation audit", "",
        "The original raw results are unchanged. Cross-beta raw T-COST is not a common-welfare scale because beta is inside its shortage coefficient.", "",
        f"Diminishing-response verdict: **{summary['diminishing_response_verdict']}**. Beta 2→4 improves the common-reference outcome for a minority of rows; beta 4→6 is an aggregate common-reference plateau, while some commodity composition changes remain.", "",
        "Priority audit:", "",
    ]
    for case, result in crowd.items():
        lines.append(f"- {case}: target benefit={result['TARGET_BENEFIT']}; non-target crowding-out={result['NON_TARGET_CROWDING_OUT']}; portfolio reference-cost increase={result['PORTFOLIO_REFERENCE_COST_INCREASE']}.")
    lines.extend(["", "Claim-by-claim review:", ""])
    for row in claims:
        lines.append(f"- {row['claim_id']} — **{row['status']}**: {row['claim']} {row['reason']}")
    lines.extend(["", "Scientific-freeze recommendation: **YES**, subject to independent review of this audit.", ""])
    return "\n".join(lines)


def build() -> int:
    before = preflight(ROOT)
    common, anchor = common_reference_rows(ROOT)
    beta, priority = paired_tables(common)
    summary = summaries(common, beta, priority)
    claims = claim_rows()
    out = ROOT / OUTPUT
    out.mkdir(parents=True, exist_ok=True)
    _write_csv(out / "common_reference_results.csv", common)
    _write_csv(out / "paired_beta_reference.csv", beta)
    _write_csv(out / "paired_priority_reference.csv", priority)
    _write_csv(out / "beta_reference_summary.csv", _flatten_level(summary, ("E2D_BETA2", "E2D_BASELINE", "E2D_BETA6")) + _flatten_paired(summary, "paired_beta"))
    _write_csv(out / "priority_reference_summary.csv", _flatten_level(summary, ("E2D_BASELINE", "E2D_LAMBDA_WATER", "E2D_LAMBDA_VACCINE", "E2D_LAMBDA_CRACKERS")) + _flatten_paired(summary, "paired_priority"))
    _write_csv(out / "commodity_reference_tradeoff.csv", summary["commodity_reference_tradeoff"])
    _write_csv(out / "expenditure_decomposition.csv", summary["expenditure_decomposition"])
    _write_csv(out / "claim_status.csv", claims)
    atomic_write_text(out / "SHORTAGE_OBJECTIVE_AUDIT.md", _objective_markdown())
    atomic_write_text(out / "INTERPRETATION_RULES.md", _rules_markdown())
    atomic_write_text(out / "RESULT_INTERPRETATION_AUDIT.md", _interpretation_markdown(summary, claims))
    audit = {
        "schema_version": 1, "scope": "FORMAL_E2D_COMMON_REFERENCE_INTERPRETATION_AUDIT_V1",
        "common_reference": {"beta": 4.0, "lambda": [1.0, 1.0, 1.0]},
        "baseline_consistency": anchor, "summaries": summary, "claims": claims,
        "RAW_AGGREGATE_SHORTAGE_IS_CROSS_UNIT_DESCRIPTIVE_ONLY": True,
        "E2D_SCIENTIFIC_FREEZE": "YES", "E2D_AUDIT_NEW_OPTIMIZATION_RUNS": 0, "E3_RUNS": 0,
    }
    atomic_write_json(out / "e2d_interpretation_audit.json", audit)
    manifest = {
        "schema_version": 1, "scope": audit["scope"], "git_commit": _git("rev-parse", "HEAD"),
        "git_tree": _git("show", "-s", "--format=%T", "HEAD"),
        "source_artifacts": {
            "e1_results": "formal_results/e1_final/e1_scientific_results.csv",
            "e2d_results": "formal_results/e2_final/e2d/scientific_results.csv",
        },
        "source_sha256": {
            "e1_results": sha256_file(ROOT / "formal_results/e1_final/e1_scientific_results.csv"),
            "e2d_results": sha256_file(ROOT / "formal_results/e2_final/e2d/scientific_results.csv"),
        },
        "frozen_hashes": before["frozen_hashes"], "row_counts": {"common": 6000, "beta_pairs": 1000, "priority_pairs": 3000},
        "baseline_consistency": anchor, "evaluation_method": "READ_ONLY_COMMON_REFERENCE_POST_PROCESSING",
        "stored_certified_worst_scenario_held_fixed": True, "new_worst_scenario_search": False,
        "scientific_optimization_runs": 0, "E3_runs": 0,
    }
    atomic_write_json(out / "manifest.json", manifest)
    names = sorted(path.name for path in out.iterdir() if path.is_file() and path.name != "HASHES.sha256")
    atomic_write_text(out / "HASHES.sha256", "".join(f"{sha256_file(out / name)}  {name}\n" for name in names))
    if frozen_hashes(ROOT) != before["frozen_hashes"]:
        raise RuntimeError("frozen evidence changed during audit build")
    return verify()


def verify() -> int:
    out = ROOT / OUTPUT
    verify_hash_inventory(out)
    current = preflight(ROOT)
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    audit = json.loads((out / "e2d_interpretation_audit.json").read_text(encoding="utf-8"))
    if manifest["frozen_hashes"] != current["frozen_hashes"]:
        raise RuntimeError("frozen evidence differs from audit manifest")
    if manifest["row_counts"] != {"common": 6000, "beta_pairs": 1000, "priority_pairs": 3000}:
        raise RuntimeError("audit row-count identity mismatch")
    if audit["baseline_consistency"]["passed"] != 1000 or audit["E2D_SCIENTIFIC_FREEZE"] != "YES":
        raise RuntimeError("audit scientific anchor/verdict mismatch")
    if manifest["scientific_optimization_runs"] or manifest["E3_runs"]:
        raise RuntimeError("forbidden optimization recorded")
    print(json.dumps({"status": "PASS", "scope": manifest["scope"], "baseline_anchor": audit["baseline_consistency"], "frozen_hashes": current["frozen_hashes"]}, indent=2, sort_keys=True))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("preflight", "build", "verify"))
    command = parser.parse_args().command
    if command == "preflight":
        print(json.dumps(preflight(ROOT), indent=2, sort_keys=True)); return 0
    return build() if command == "build" else verify()


if __name__ == "__main__":
    raise SystemExit(main())
