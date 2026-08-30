"""Run or replay the frozen R5 Q-F-R Pilot matrix."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from robust_budget_allocation.io.atomic import atomic_write_json
from robust_budget_allocation.pilot.qfr_r5 import run_r5_pilot, validate_r5_evidence


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workbook", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--replay", action="store_true")
    args = parser.parse_args()
    if args.replay:
        evidence = json.loads(args.output.resolve().read_text(encoding="utf-8"))
        print(json.dumps(validate_r5_evidence(ROOT, args.workbook, evidence), sort_keys=True))
        return 0
    evidence = run_r5_pilot(ROOT, args.workbook)
    atomic_write_json(args.output.resolve(), evidence)
    print(json.dumps(evidence["summary"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
