"""Materialize the deterministic E1-Historical Rawls-15 dataset."""

from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from robust_budget_allocation.data.qfr_e1_historical import build_e1_historical_data  # noqa: E402
from robust_budget_allocation.io.atomic import atomic_write_json  # noqa: E402


OUTPUT = ROOT / "configs/e1_historical_rawls15_data_v1.json"


def main() -> int:
    product = build_e1_historical_data(ROOT)
    atomic_write_json(OUTPUT, product)
    print(json.dumps({
        "status": "PASS",
        "output": OUTPUT.relative_to(ROOT).as_posix(),
        "dataset_kind": product["dataset_kind"],
        "scenario_count": product["scenario_counts"]["total"],
        "scenario_ids": product["scenario_ordering"],
        "B_ref": product["reference_budget"],
        "F_bar": product["flexible_capacity"],
        "data_sha256": product["data_sha256"],
        "scenario_set_sha256": product["scenario_set_sha256"],
        "parameter_sha256": product["parameter_sha256"],
    }, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
