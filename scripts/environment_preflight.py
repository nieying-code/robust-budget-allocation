"""Print the locked environment report as JSON, or exit nonzero."""

from __future__ import annotations

import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from robust_budget_allocation.environment import (  # noqa: E402
    EnvironmentPreflightError,
    run_preflight,
)


def main() -> int:
    try:
        report = run_preflight()
    except EnvironmentPreflightError as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, indent=2))
        return 1
    print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
