"""N7-PRE DIAGNOSTIC ONLY — NOT FORMAL SCIENTIFIC PARAMETERS."""

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from robust_budget_allocation.mechanism_confirmation.execution import gates, execute, worker
from robust_budget_allocation.mechanism_confirmation.audit import load_archive
from robust_budget_allocation.mechanism_confirmation.replay import replay_bundle


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("gates", "run", "worker", "replay"))
    parser.add_argument("--folder", type=Path)
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()
    if args.action == "gates": return gates()
    if args.action == "run": return execute()
    if args.action == "worker": return worker(args.folder)
    result = replay_bundle(load_archive(args.evidence))
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
