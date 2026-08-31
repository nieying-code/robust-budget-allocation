"""Validate and materialize the R6-B experiment matrix without optimization."""

from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from robust_budget_allocation.data.qfr_formal_experiments import (  # noqa: E402
    build_experiment_matrix,
)


CONFIG = ROOT / "configs/r6_formal_experiment_matrix_v1.json"
EXPANDED = ROOT / "configs/r6_formal_experiment_matrix_expanded_v1.json"


def main() -> int:
    matrix = build_experiment_matrix(CONFIG, ROOT)
    EXPANDED.write_text(
        json.dumps(matrix, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps({
        "status": "PASS",
        "matrix_sha256": matrix["matrix_sha256"],
        "counts": matrix["counts"],
        "scientific_runs": matrix["scientific_runs"],
        "r7_started": matrix["r7_started"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
