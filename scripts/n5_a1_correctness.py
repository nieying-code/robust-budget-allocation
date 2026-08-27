"""One-shot clean-source EF/A0/A1 development evidence, never a pilot runner."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from robust_budget_allocation.algorithms.common import PROTOCOL_PATH, PROTOCOL_SHA256, SCOPE  # noqa: E402
from robust_budget_allocation.algorithms.memory_guided_ccg import A1_PROTOCOL_PATH, A1_PROTOCOL_SHA256, solve_a1  # noqa: E402
from robust_budget_allocation.algorithms.a1_verification import verify_three  # noqa: E402
from robust_budget_allocation.algorithms.extensive_form import solve_extensive_form  # noqa: E402
from robust_budget_allocation.algorithms.standard_ccg import solve_a0  # noqa: E402
from robust_budget_allocation.data.mechanism_data import OptionData  # noqa: E402
from robust_budget_allocation.io.atomic import atomic_write_json  # noqa: E402
from robust_budget_allocation.io.hashing import canonical_json_sha256, sha256_file  # noqa: E402
from robust_budget_allocation.reproducibility.git_state import validate_source_state  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "docs/evidence/N5_EF_A0_A1_CORRECTNESS.json")
    args = parser.parse_args()
    if args.output.exists(): raise FileExistsError("evidence exists; use a new output path")
    fixture = ROOT / "tests/fixtures/n5_correctness.json"
    inputs = (Path(__file__).resolve(), fixture, ROOT / PROTOCOL_PATH, ROOT / A1_PROTOCOL_PATH)
    gate = dict(required_tracked_paths=inputs,
                scientific_roots=("src/robust_budget_allocation", "tests", "scripts", "configs"))
    before = validate_source_state(ROOT, **gate)
    cases = json.loads(fixture.read_text(encoding="utf-8"))
    if cases["classification"] != SCOPE: raise ValueError("only development correctness inputs are permitted")
    rows = []
    for case in cases["cases"]:
        d = OptionData.from_dict(case["data"])
        ef, a0, a1 = solve_extensive_form(d, audit_inputs=inputs), solve_a0(d, audit_inputs=inputs), solve_a1(d, audit_inputs=inputs)
        try:
            checks = verify_three(d, ef, a0, a1)
        except (ValueError, TypeError, KeyError, ArithmeticError) as exc:
            checks = dict(status="FAIL", diagnostic=str(exc))
        rows.append(dict(id=case["id"], EF=ef, A0=a0, A1=a1, checks=checks))
        if checks["status"] != "PASS": break  # Do not tune/retry a genuine correctness failure.
    after = validate_source_state(ROOT, **gate)
    if any(before[k] != after[k] for k in ("commit_sha", "tree_sha")): raise RuntimeError("source changed during execution")
    passed = [r["checks"] for r in rows if r["checks"]["status"] == "PASS"]
    payload = dict(schema_version=1, classification=SCOPE, source_gate=before,
                   protocol_hashes={PROTOCOL_PATH: PROTOCOL_SHA256, A1_PROTOCOL_PATH: A1_PROTOCOL_SHA256},
                   fixture_path=fixture.relative_to(ROOT).as_posix(), fixture_sha256=sha256_file(fixture),
                   expected_case_count=len(cases["cases"]), case_count=len(rows), cases=rows,
                   status="PASS" if len(passed) == len(cases["cases"]) else "FAIL",
                   maxima={k: max((c[k] for c in passed), default=None) for k in
                           ("max_objective_difference", "relative_objective_difference", "final_gap", "final_violation")},
                   diagnostics={k: sum(r["A1"][k] for r in rows) for k in
                                ("iterations", "phase_i_hits", "phase_ii_hits", "phase_iii_calls", "exact_oracle_calls", "complete_oracle_calls", "scenario_evaluations")})
    payload["evidence_sha256"] = canonical_json_sha256(payload)
    atomic_write_json(args.output, payload)
    print(json.dumps({k: payload[k] for k in ("status", "case_count", "maxima", "diagnostics")}, indent=2))
    print(json.dumps({k: before[k] for k in ("commit_sha", "tree_sha")}, indent=2))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
