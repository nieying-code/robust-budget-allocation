"""CLI for E1-Historical preflight, formal execution, and replay."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from robust_budget_allocation.formal.e1_historical import (  # noqa: E402
    licensed_preflight,
    replay_delivery,
    run_e1_historical,
    solver_free_preflight,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("solver-free-preflight", "preflight", "run", "replay"))
    args = parser.parse_args()
    if args.mode == "solver-free-preflight":
        result = solver_free_preflight(ROOT)
    elif args.mode == "preflight":
        result = licensed_preflight(ROOT, execution_gate=True)
    elif args.mode == "run":
        result = run_e1_historical(ROOT)
    else:
        result = replay_delivery(ROOT)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
