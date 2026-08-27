"""One-shot N2 hand-fixture evidence, not an experiment runner or registry."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from robust_budget_allocation.data.model_data import BudgetAllocationData  # noqa: E402
from robust_budget_allocation.io.atomic import atomic_write_json  # noqa: E402
from robust_budget_allocation.io.hashing import canonical_json_sha256, sha256_file  # noqa: E402
from robust_budget_allocation.models.m0 import (  # noqa: E402
    DEVELOPMENT_SCOPE, N2_ABSOLUTE_TOLERANCE, N2_RELATIVE_TOLERANCE, solve_m0,
)
from robust_budget_allocation.reproducibility.git_state import validate_source_state  # noqa: E402


def matches(actual: object, expected: object) -> bool:
    if isinstance(expected, dict):
        return isinstance(actual, dict) and set(actual) == set(expected) and all(
            matches(actual[k], value) for k, value in expected.items()
        )
    return isinstance(actual, (float, int)) and math.isclose(
        actual, expected, abs_tol=N2_ABSOLUTE_TOLERANCE, rel_tol=N2_RELATIVE_TOLERANCE,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=ROOT / "docs" / "evidence" / "N2_M0_CORRECTNESS.json")
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("development evidence already exists; choose a new output path")
    fixture = ROOT / "tests" / "fixtures" / "n2_m0_hand_cases.json"
    inputs = (Path(__file__).resolve(), fixture)
    # Editable-install metadata is generated under src/*.egg-info, outside the
    # actual scientific package. Package code and all test/config/script inputs
    # remain subject to the N1 untracked-input gate, including ignored files.
    gate = dict(required_tracked_paths=inputs,
                scientific_roots=("src/robust_budget_allocation", "tests", "scripts", "configs"))
    source = validate_source_state(ROOT, **gate)
    cases = json.loads(fixture.read_text(encoding="utf-8"))
    if cases["classification"] != DEVELOPMENT_SCOPE:
        raise ValueError("only development/correctness fixtures are permitted")
    rows = []
    for case in cases["cases"]:
        result = solve_m0(BudgetAllocationData.from_dict(case["data"]), audit_inputs=inputs)
        snapshot = result.to_dict()
        checks = {name: matches(snapshot[name], expected) for name, expected in case["expected"].items()}
        passed = result.status == "optimal" and all(checks.values())
        rows.append({"id": case["id"], "expected": case["expected"], "checks": checks,
                     "status": "PASS" if passed else "FAIL", "result": snapshot})
    after = validate_source_state(ROOT, **gate)
    if (source["commit_sha"], source["tree_sha"]) != (after["commit_sha"], after["tree_sha"]):
        raise RuntimeError("source identity changed during development checks")
    payload = {
        "schema_version": 1,
        "classification": DEVELOPMENT_SCOPE,
        "source_gate": source,
        "fixture_path": fixture.relative_to(ROOT).as_posix(),
        "fixture_sha256": sha256_file(fixture),
        "status": "PASS" if all(row["status"] == "PASS" for row in rows) else "FAIL",
        "case_count": len(rows),
        "cases": rows,
    }
    payload["evidence_sha256"] = canonical_json_sha256(payload)
    atomic_write_json(args.output, payload)
    print(json.dumps({"status": payload["status"], "case_count": len(rows),
                      "commit": source["commit_sha"], "tree": source["tree_sha"],
                      "output": str(args.output)}, indent=2))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
