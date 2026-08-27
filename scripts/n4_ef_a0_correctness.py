"""One-shot, clean-commit N4 development correctness evidence; no pilot/formal run."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from robust_budget_allocation.algorithms.common import PROTOCOL_PATH, PROTOCOL_SHA256, SCOPE  # noqa: E402
from robust_budget_allocation.algorithms.extensive_form import solve_extensive_form  # noqa: E402
from robust_budget_allocation.algorithms.standard_ccg import solve_a0  # noqa: E402
from robust_budget_allocation.algorithms.verification import verify_pair  # noqa: E402
from robust_budget_allocation.data.mechanism_data import OptionData  # noqa: E402
from robust_budget_allocation.io.atomic import atomic_write_json  # noqa: E402
from robust_budget_allocation.io.hashing import canonical_json_sha256, sha256_file  # noqa: E402
from robust_budget_allocation.reproducibility.git_state import validate_source_state  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "docs/evidence/N4_EF_A0_CORRECTNESS.json")
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("evidence already exists; use a new output path")
    fixture = ROOT / "tests/fixtures/n4_correctness.json"
    inputs = (Path(__file__).resolve(), fixture, ROOT / PROTOCOL_PATH)
    gate = dict(required_tracked_paths=inputs,
                scientific_roots=("src/robust_budget_allocation", "tests", "scripts", "configs"))
    before = validate_source_state(ROOT, **gate)
    cases = json.loads(fixture.read_text(encoding="utf-8"))
    if cases["classification"] != SCOPE:
        raise ValueError("only development/correctness input is permitted")
    rows = []
    for case in cases["cases"]:
        data = OptionData.from_dict(case["data"])
        ef = solve_extensive_form(data, audit_inputs=inputs)
        a0 = solve_a0(data, audit_inputs=inputs)
        try:
            checks = verify_pair(data, ef, a0)
        except (ValueError, KeyError, TypeError, ArithmeticError) as exc:
            checks = dict(status="FAIL", diagnostic=str(exc))
        rows.append(dict(id=case["id"], EF=ef, A0=a0, checks=checks))
    after = validate_source_state(ROOT, **gate)
    if any(before[key] != after[key] for key in ("commit_sha", "tree_sha")):
        raise RuntimeError("execution source changed")
    successful = [r["checks"] for r in rows if r["checks"]["status"] == "PASS"]
    payload = dict(schema_version=1, classification=SCOPE, source_gate=before,
                   protocol_path=PROTOCOL_PATH, protocol_sha256=PROTOCOL_SHA256,
                   fixture_path=fixture.relative_to(ROOT).as_posix(), fixture_sha256=sha256_file(fixture),
                   status="PASS" if len(successful) == len(rows) else "FAIL", case_count=len(rows), cases=rows,
                   maxima={key: max((c[key] for c in successful), default=None) for key in
                           ("objective_difference", "relative_objective_difference", "final_gap", "final_violation")})
    payload["evidence_sha256"] = canonical_json_sha256(payload)
    atomic_write_json(args.output, payload)
    print(json.dumps({"status": payload["status"], "case_count": len(rows), "maxima": payload["maxima"],
                      "iterations": [r["A0"]["iterations"] for r in rows],
                      "commit": before["commit_sha"], "tree": before["tree_sha"]}, indent=2))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
