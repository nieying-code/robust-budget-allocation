"""CLI for R7-E1 preflight, Formal execution, and replay."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from robust_budget_allocation.formal.e1 import licensed_preflight, replay_delivery, run_e1, solver_free_preflight


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("solver-free-preflight", "preflight", "run", "replay"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.mode == "solver-free-preflight":
        result = solver_free_preflight(root)
    elif args.mode == "preflight":
        result = licensed_preflight(root, execution_gate=True)
    elif args.mode == "run":
        result = run_e1(root)
    else:
        result = replay_delivery(root)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
