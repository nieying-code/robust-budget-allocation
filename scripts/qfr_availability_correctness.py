"""Run or replay the Q-F-R availability-revision correctness regression."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from robust_budget_allocation.algorithms.qfr_revision_suite import (
    run_revision_correctness_suite,
    validate_revision_evidence,
)
from robust_budget_allocation.io.atomic import atomic_write_json


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/qfr_availability_correctness_v2_1.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--replay", action="store_true")
    args = parser.parse_args()
    output = args.output.resolve()
    if args.replay:
        evidence = json.loads(output.read_text(encoding="utf-8"))
        print(json.dumps(validate_revision_evidence(ROOT, evidence), sort_keys=True))
        return 0
    evidence = run_revision_correctness_suite(ROOT, FIXTURE)
    atomic_write_json(output, evidence)
    print(json.dumps(evidence["summary"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
