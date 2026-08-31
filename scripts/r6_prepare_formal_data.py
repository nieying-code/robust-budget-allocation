"""Generate deterministic R6-A data products; this script never invokes a solver."""

from __future__ import annotations

import csv
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from robust_budget_allocation.data.qfr_formal import build_formal_data  # noqa: E402


CONFIG = ROOT / "configs/r6_formal_data_v1.json"
READY = ROOT / "configs/r6_formal_ready_data_v1.json"
SOURCE_TABLE = ROOT / "docs/evidence/R6_SOURCE_SCENARIO_TABLE_v1.csv"
TRANSFORM_TABLE = ROOT / "docs/evidence/R6_FORMAL_DEMAND_TRANSFORMATION_v1.csv"


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    product = build_formal_data(CONFIG)
    _write_json(READY, product)
    source_rows = []
    transformation_rows = []
    for row in product["scenarios"]:
        source_rows.append({
            "scenario_id": row["scenario_id"],
            "scenario_type": row["scenario_type"],
            "probability": row["probability"],
            "hurricanes": "+".join(row["hurricanes"]) or "NONE",
            "category": row["category"],
            "raw_water_1000_gallons": row["raw_demand"]["water"],
            "raw_mre_1000_meals": row["raw_demand"]["mre"],
            "raw_medical_units": row["raw_demand"]["medical"],
            "q_availability": row["q_availability"],
            "disruption": row["disruption"],
            "source_identity": "RAWLS_TABLES_3_4_YANG_TABLES_12_13",
        })
        for item, raw_field, raw_unit, multiplier, rationale in (
            ("Water", "water", "1000 gallons", 1000.0, "physical_unit_conversion"),
            ("Seasonal Influenza Vaccine", "medical", "abstract medical unit", product["demand_normalization"]["vaccine"], "economic_scale_preserving_service_normalization"),
            ("Crackers", "mre", "1000 meals", 14000.0, "approximate_energy_service_normalization"),
        ):
            transformation_rows.append({
                "scenario_id": row["scenario_id"],
                "commodity": item,
                "raw_value": row["raw_demand"][raw_field],
                "raw_unit": raw_unit,
                "multiplier": multiplier,
                "formal_value": row["formal_demand"][item],
                "formal_unit": {"Water": "gallon", "Seasonal Influenza Vaccine": "dose", "Crackers": "22 g serving"}[item],
                "rounding_status": "none_exact_float_expression",
                "rationale": rationale,
                "provenance_identity": "R6_FINAL_FORMAL_DESIGN_2026_08_31",
            })
    _write_csv(SOURCE_TABLE, list(source_rows[0]), source_rows)
    _write_csv(TRANSFORM_TABLE, list(transformation_rows[0]), transformation_rows)
    print(json.dumps({
        "status": "PASS",
        "scientific_runs": 0,
        "data_sha256": product["data_sha256"],
        "reference_budget": product["reference_budget"],
        "flexible_capacity": product["flexible_capacity"],
        "scale_guard_flags": product["economic_scale_audit"].get("scale_guard_flags", []),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
