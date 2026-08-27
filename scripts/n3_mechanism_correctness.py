"""One-shot N3 development evidence, not an EF framework or experiment runner."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from robust_budget_allocation.data.mechanism_data import OptionData  # noqa: E402
from robust_budget_allocation.data.model_data import BudgetAllocationData  # noqa: E402
from robust_budget_allocation.io.atomic import atomic_write_json  # noqa: E402
from robust_budget_allocation.io.hashing import canonical_json_sha256, sha256_file  # noqa: E402
from robust_budget_allocation.models.m0 import (  # noqa: E402
    DEVELOPMENT_SCOPE, N2_ABSOLUTE_TOLERANCE as ATOL, N2_RELATIVE_TOLERANCE as RTOL, solve_m0,
)
from robust_budget_allocation.models.m1 import solve_m1  # noqa: E402
from robust_budget_allocation.models.m2 import solve_m2  # noqa: E402
from robust_budget_allocation.reproducibility.git_state import validate_source_state  # noqa: E402


def matches(actual, expected):
    if isinstance(expected, dict):
        return isinstance(actual, dict) and set(actual) == set(expected) and all(
            matches(actual[k], v) for k, v in expected.items())
    if isinstance(expected, (str, bool)) or expected is None:
        return actual == expected
    return isinstance(actual, (float, int)) and math.isclose(actual, expected, abs_tol=ATOL, rel_tol=RTOL)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "docs/evidence/N3_M1_M2_CORRECTNESS.json")
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("evidence already exists; choose a new output path")
    fixture = ROOT / "tests/fixtures/n3_mechanisms.json"
    old_fixture = ROOT / "tests/fixtures/n2_m0_hand_cases.json"
    inputs = (Path(__file__).resolve(), fixture, old_fixture)
    gate = dict(required_tracked_paths=inputs,
                scientific_roots=("src/robust_budget_allocation", "tests", "scripts", "configs"))
    source = validate_source_state(ROOT, **gate)
    cases = json.loads(fixture.read_text(encoding="utf-8"))
    old_cases = json.loads(old_fixture.read_text(encoding="utf-8"))
    if any(c["classification"] != DEVELOPMENT_SCOPE for c in (cases, old_cases)):
        raise ValueError("only development/correctness fixtures are permitted")
    results, mechanisms, degenerations, regressions = {}, [], [], []
    for case in cases["cases"]:
        data = OptionData.from_dict(case["data"])
        prefix = case["id"] + "/"
        solved = {
            "m0": solve_m0(data.base, audit_inputs=inputs),
            "m1_base": solve_m1(data.reliability, fixed_reliability={j: "0" for j in data.base.suppliers}, audit_inputs=inputs),
            "m1": solve_m1(data.reliability, audit_inputs=inputs),
            "m2_off": solve_m2(data, fixed_option=0, audit_inputs=inputs),
        }
        if case["model"] == "M2":
            solved["m2"] = solve_m2(data, audit_inputs=inputs)
        snapshots = {key: result.to_dict() for key, result in solved.items()}
        results.update({prefix + key: value for key, value in snapshots.items()})
        target = snapshots[case["model"].lower()]
        checks = {key: matches(target[key], value) for key, value in case["expected"].items()}
        checks["optimal"] = target["status"] == "optimal"
        if case["id"] == "expensive_emergency_no_exercise":
            checks["expensive_no_exercise"] = matches(target["g"]["expensive"], 0)
        mechanisms.append(dict(id=case["id"], result_id=prefix + case["model"].lower(),
                               expected=case["expected"], checks=checks))
        zero, base, one, off = (snapshots[k] for k in ("m0", "m1_base", "m1", "m2_off"))
        checks = {"all_optimal": all(r["status"] == "optimal" for r in snapshots.values())}
        for key in ("objective", "C_Q", "q", "x", "u", "h", "worst_loss", "worst_scenario"):
            checks["m1_base_" + key] = matches(base[key], zero[key])
        checks["m1_base_zero_premium"] = matches(base["C_R"], 0)
        for key in ("objective", "C_Q", "C_R", "q", "q_by_level", "reliability_choice", "x", "u", "h", "worst_loss", "worst_scenario", "unused_budget"):
            checks["m2_off_" + key] = matches(off[key], one[key])
        checks["no_option_no_purchase"] = off["y_F"] == 0 and all(matches(v, 0) for v in (*off["g"].values(), *off["E"].values()))
        checks["same_base_and_scenarios"] = all(
            r["audit"]["scenario_sha256"] == data.base.scenario_sha256 for r in snapshots.values())
        degenerations.append(dict(id=case["id"], result_ids={k: prefix + k for k in solved}, checks=checks))
    for case in old_cases["cases"]:
        result = solve_m0(BudgetAllocationData.from_dict(case["data"]), audit_inputs=inputs).to_dict()
        key = "n2/" + case["id"]
        results[key] = result
        checks = {name: matches(result[name], value) for name, value in case["expected"].items()}
        checks["optimal"] = result["status"] == "optimal"
        regressions.append(dict(id=case["id"], result_id=key, expected=case["expected"], checks=checks))
    after = validate_source_state(ROOT, **gate)
    if any(source[key] != after[key] for key in ("commit_sha", "tree_sha")):
        raise RuntimeError("source identity changed during correctness evidence generation")
    rows = mechanisms + degenerations + regressions
    payload = dict(schema_version=1, classification=DEVELOPMENT_SCOPE, source_gate=source,
                   fixture_hashes={p.relative_to(ROOT).as_posix(): sha256_file(p) for p in (fixture, old_fixture)},
                   status="PASS" if all(all(row["checks"].values()) for row in rows) else "FAIL",
                   mechanism_count=len(mechanisms), degeneration_count=len(degenerations),
                   m0_regression_count=len(regressions), mechanisms=mechanisms,
                   degenerations=degenerations, m0_regressions=regressions, results=results)
    payload["evidence_sha256"] = canonical_json_sha256(payload)
    atomic_write_json(args.output, payload)
    print(json.dumps({"status": payload["status"], "mechanisms": len(mechanisms),
                      "degenerations": len(degenerations), "m0_regressions": len(regressions),
                      "commit": source["commit_sha"], "tree": source["tree_sha"], "output": str(args.output)}, indent=2))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
