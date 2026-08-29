"""Run or replay the frozen R3 Q-F-R v2 EF/A0 correctness evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from robust_budget_allocation.algorithms.qfr_correctness_suite import run_r3_correctness_suite
from robust_budget_allocation.algorithms.qfr_verification import validate_r3_evidence
from robust_budget_allocation.io.atomic import atomic_write_json


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURE = ROOT / "tests/fixtures/r3_correctness_v2.json"
DEFAULT_EVIDENCE = ROOT / "docs/evidence/R3_CORRECTNESS_RESULTS_v2.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--output", type=Path, default=DEFAULT_EVIDENCE)
    parser.add_argument("--replay", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.replay is not None:
        evidence = json.loads(args.replay.resolve().read_text(encoding="utf-8"))
        result = validate_r3_evidence(ROOT, evidence)
        print(json.dumps(result, sort_keys=True))
        return 0
    evidence = run_r3_correctness_suite(ROOT, args.fixture)
    atomic_write_json(args.output.resolve(), evidence)
    print(json.dumps(evidence["summary"], sort_keys=True))
    return 0 if evidence["summary"]["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
