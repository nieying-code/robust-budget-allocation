"""Materialize the R6-C revised data and matrix; never invokes a solver."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from robust_budget_allocation.data.qfr_r6c import (  # noqa: E402
    build_revised_experiment_matrix,
    build_revised_formal_data,
)


REVISION = ROOT / "configs/r6c_scientific_revision_v2.json"
READY = ROOT / "configs/r6c_formal_ready_data_v2.json"
MATRIX_CONFIG = ROOT / "configs/r6c_formal_experiment_matrix_v2.json"
EXPANDED = ROOT / "configs/r6c_formal_experiment_matrix_expanded_v2.json"


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-only", action="store_true")
    args = parser.parse_args()
    ready = build_revised_formal_data(REVISION, ROOT)
    _write_json(READY, ready)
    output = {
        "status": "PASS", "stage": "R6-C", "formal_scientific_runs": 0,
        "data_sha256": ready["data_sha256"], "scenario_sha256": ready["scenario_sha256"],
        "reference_budget": ready["reference_budget"],
    }
    if not args.data_only:
        matrix = build_revised_experiment_matrix(MATRIX_CONFIG, ROOT)
        _write_json(EXPANDED, matrix)
        output.update({"matrix_sha256": matrix["matrix_sha256"], "counts": matrix["counts"],
                       "deduplication": matrix["deduplication"]})
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
