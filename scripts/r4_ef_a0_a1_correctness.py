"""Run or replay the preregistered R4 EF/A0/A1 correctness evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from robust_budget_allocation.algorithms.qfr_a1_suite import run_r4_correctness_suite
from robust_budget_allocation.algorithms.qfr_a1_verification import validate_r4_evidence
from robust_budget_allocation.io.atomic import atomic_write_json


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/r3_correctness_v2.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--replay", action="store_true")
    parser.add_argument("--without-memory", action="store_true")
    args = parser.parse_args()
    if args.replay:
        evidence = json.loads(args.output.resolve().read_text(encoding="utf-8"))
        print(json.dumps(validate_r4_evidence(ROOT, evidence), sort_keys=True))
        return 0
    evidence = run_r4_correctness_suite(
        ROOT, FIXTURE, memory_phase_enabled=not args.without_memory
    )
    atomic_write_json(args.output.resolve(), evidence)
    print(json.dumps(evidence["summary"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
