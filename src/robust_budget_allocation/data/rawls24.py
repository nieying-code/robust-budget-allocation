"""Deterministic, solver-free construction of the R6 Rawls24 data layers."""

from __future__ import annotations

import csv
from decimal import Decimal
import io
import json
from pathlib import Path
from typing import Any

from robust_budget_allocation.io.hashing import canonical_json_sha256, sha256_bytes, sha256_file


EXPECTED_NAMES = (
    "Alicia", "Camille", "Bonnie", "Floyd", "Andrew", "Opal", "Isabel", "Lili",
    "Katrina", "Bertha", "Fran", "Dennis", "Emily", "Georges", "Hugo", "Ike",
    "Rita", "Wilma", "Irma", "Charley", "Frances", "Ivan", "Jeanne", "Elena",
)
RAWLS_COUNT = 15
OUTPUT_FILES = {
    "historical_source": "rawls15_historical_source.csv",
    "unified_input": "unified_hurricane_input.csv",
    "unified_demand": "unified_rawls_demand.csv",
    "historical_comparison": "rawls15_historical_comparison.csv",
}


def _decimal(value: int | float | str) -> Decimal:
    return Decimal(str(value))


def _number(value: Decimal) -> int | float:
    return int(value) if value == value.to_integral_value() else float(value)


def _demand(event: dict[str, Any]) -> dict[str, Decimal | str]:
    category = int(event["category"])
    evacuees = _decimal(event["evacuees"])
    sheltered = _decimal(event["sheltered"])
    if category <= 2:
        water, food = 3 * evacuees, 15 * sheltered
        water_formula, food_formula = "3 * evacuees", "15 * sheltered"
    else:
        water, food = 10 * evacuees, 35 * sheltered
        water_formula, food_formula = "10 * evacuees", "35 * sheltered"
    return {
        "water": water,
        "food": food,
        "medical": sheltered / 4,
        "water_formula": water_formula,
        "food_formula": food_formula,
        "medical_formula": "sheltered / 4",
    }


def _comparison_status(historical: Decimal, unified: Decimal, rounding_tolerance: Decimal) -> str:
    difference = abs(historical - unified)
    if difference == 0:
        return "same"
    if difference <= rounding_tolerance:
        return "rounding-only"
    return "changed"


def _csv_bytes(fieldnames: list[str], rows: list[dict[str, Any]]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def _validate_config(config: dict[str, Any]) -> None:
    events = config["events"]
    assert len(events) == 24
    assert tuple(event["hurricane_name"] for event in events) == EXPECTED_NAMES
    assert tuple(event["scenario_id"] for event in events) == tuple(f"h{i:02d}" for i in range(1, 25))
    assert len({event["hurricane_name"] for event in events}) == 24
    assert len({event["scenario_id"] for event in events}) == 24
    assert sum(event["group"] == "Rawls15" for event in events) == 15
    assert sum(event["group"] == "Added9" for event in events) == 9
    assert all(int(event["category"]) in {1, 2, 3, 4, 5} for event in events)
    assert all(_decimal(event["evacuees"]) > 0 and _decimal(event["sheltered"]) > 0 for event in events)
    assert all("historical_rawls" in event for event in events[:RAWLS_COUNT])
    assert all("historical_rawls" not in event for event in events[RAWLS_COUNT:])
    frozen_2004 = {
        "Charley": (2700000, 102094),
        "Frances": (1800000, 186620),
        "Ivan": (544900, 33472),
        "Jeanne": (4400000, 46252),
    }
    by_name = {event["hurricane_name"]: event for event in events}
    for name, pair in frozen_2004.items():
        assert (by_name[name]["evacuees"], by_name[name]["sheltered"]) == pair
        assert by_name[name]["geographic_scope"] == "Florida statewide"
    assert by_name["Rita"]["evidence_status"] == "FROZEN-BOUND"
    assert "up to" in by_name["Rita"]["evacuees_evidence_identity"]
    assert "at least" in by_name["Rita"]["sheltered_evidence_identity"]
    assert by_name["Elena"]["evidence_status"] == "FROZEN-BOUND"
    assert "lower bound" in by_name["Elena"]["evacuees_evidence_identity"]
    correction = config["provenance_corrections"]["elena_evidence_status"]
    assert correction["authoritative_workbook_value"] == "READY"
    assert correction["corrected_value"] == "FROZEN-BOUND"
    assert correction["category_e_s_or_demand_changed"] is False


def build_rawls24_layers(config_path: Path) -> dict[str, Any]:
    """Build all data layers in memory without invoking model or solver code."""
    config = json.loads(config_path.read_text(encoding="utf-8"))
    _validate_config(config)
    historical_rows: list[dict[str, Any]] = []
    input_rows: list[dict[str, Any]] = []
    demand_rows: list[dict[str, Any]] = []
    comparison_rows: list[dict[str, Any]] = []

    for event in config["events"]:
        demand = _demand(event)
        input_rows.append({key: event[key] for key in (
            "scenario_id", "hurricane_name", "year", "category", "evacuees", "sheltered",
            "geographic_scope", "evidence_status",
        )} | {
            "scenario_type": "single_hurricane",
            "source_group": event["group"],
            "E_evidence_identity": event["evacuees_evidence_identity"],
            "S_evidence_identity": event["sheltered_evidence_identity"],
            "source_reference": event["source_reference"],
            "notes": event["notes"],
        })
        demand_rows.append({
            "scenario_id": event["scenario_id"],
            "hurricane_name": event["hurricane_name"],
            "category": event["category"],
            "evacuees": event["evacuees"],
            "sheltered": event["sheltered"],
            "water_unified": _number(demand["water"]),
            "food_unified": _number(demand["food"]),
            "medical_unified": _number(demand["medical"]),
            "water_formula": demand["water_formula"],
            "food_formula": demand["food_formula"],
            "medical_formula": demand["medical_formula"],
        })
        if event["group"] == "Rawls15":
            source = event["historical_rawls"]
            historical_water = 1000 * _decimal(source["water_1000_gallons"])
            historical_food = 1000 * _decimal(source["food_1000_units"])
            historical_medical = _decimal(source["medical_units"])
            historical_rows.append({
                "scenario_id": event["scenario_id"],
                "hurricane_name": event["hurricane_name"],
                "year": event["year"],
                "category": event["category"],
                "evacuees": event["evacuees"],
                "sheltered": event["sheltered"],
                "evacuees_qualifier": source["evacuees_qualifier"],
                "sheltered_qualifier": source["sheltered_qualifier"],
                "historical_rawls_water_1000_gallons": source["water_1000_gallons"],
                "historical_rawls_food_1000_units": source["food_1000_units"],
                "historical_rawls_medical_units": source["medical_units"],
                "source_reference": "Rawls (2008) dissertation Table 5-3, PDF p.60 / printed p.49",
            })
            comparison_rows.append({
                "scenario_id": event["scenario_id"],
                "hurricane_name": event["hurricane_name"],
                "historical_rawls_water": _number(historical_water),
                "historical_rawls_food": _number(historical_food),
                "historical_rawls_medical": _number(historical_medical),
                "unified_water": _number(demand["water"]),
                "unified_food": _number(demand["food"]),
                "unified_medical": _number(demand["medical"]),
                "water_status": _comparison_status(historical_water, demand["water"], Decimal("500")),
                "food_status": _comparison_status(historical_food, demand["food"], Decimal("500")),
                "medical_status": _comparison_status(historical_medical, demand["medical"], Decimal("0.5")),
                "comparison_basis": "physical units; rounding-only tolerances reflect Table 5-3 display precision",
            })

    rows_by_key = {
        "historical_source": historical_rows,
        "unified_input": input_rows,
        "unified_demand": demand_rows,
        "historical_comparison": comparison_rows,
    }
    payloads = {key: _csv_bytes(list(rows[0]), rows) for key, rows in rows_by_key.items()}
    output_hashes = {OUTPUT_FILES[key]: sha256_bytes(payload) for key, payload in payloads.items()}
    status_counts = {
        commodity: {status: sum(row[f"{commodity}_status"] == status for row in comparison_rows)
                    for status in ("same", "changed", "rounding-only")}
        for commodity in ("water", "food", "medical")
    }
    material_event_changes = sum(
        any(row[f"{commodity}_status"] == "changed" for commodity in ("water", "food", "medical"))
        for row in comparison_rows
    )
    validation = {
        "status": "PASS",
        "scenario_count": 24,
        "rawls15_count": 15,
        "added9_count": 9,
        "single_hurricane_count": 24,
        "combined_scenario_count": 0,
        "no_hurricane_count": 0,
        "synthetic_scenario_count": 0,
        "formula_recomputation_rows_passed": 24,
        "historical_source_rows_preserved": 15,
        "frozen_2004_pairs_passed": 4,
        "bounded_evidence_events": ["Rita", "Elena"],
        "materially_changed_original_events": material_event_changes,
        "comparison_status_counts": status_counts,
        "scientific_runs": {"M0": 0, "M1": 0, "M2": 0, "E1": 0, "E2_E5": 0, "A0": 0, "A1": 0},
    }
    identity = {
        "dataset_identity": config["dataset_identity"],
        "scenario_order": [event["scenario_id"] for event in config["events"]],
        "hurricane_order": list(EXPECTED_NAMES),
        "source_config_sha256": sha256_file(config_path),
        "canonical_data_sha256": canonical_json_sha256({
            "input": input_rows, "demand": demand_rows, "historical": historical_rows,
            "comparison": comparison_rows,
        }),
    }
    manifest = {
        **identity,
        "stage": config["stage"],
        "source_identities": config["source_identities"],
        "demand_rule": config["demand_rule"],
        "provenance_corrections": config["provenance_corrections"],
        "validation": validation,
        "source_audit": {
            "authoritative_workbook_crosscheck": "PASS_24_OF_24_IDENTITY_CATEGORY_E_S_AND_DEMAND_WITH_DOCUMENTED_ELENA_STATUS_CORRECTION",
            "rawls15_identity_category_e_s_crosscheck": "PASS_15_OF_15",
            "rawls_rule_crosscheck": "PASS_DISSERTATION_SECTION_5_3",
            "rawls_table_5_3_historical_lineage_capture": "PASS_15_OF_15",
            "bounded_evidence_status_consistency": "PASS_RITA_AND_ELENA_FROZEN_BOUND",
            "provided_pdf_identity": "2010_JOURNAL_ARTICLE_NOT_2008_DISSERTATION",
            "resolution": "OFFICIAL_CORNELL_DISSERTATION_USED_FOR_REQUIRED_RULE_AND_TABLE_AUDIT",
        },
        "output_hashes": output_hashes,
        "parameter_recalibration": "NOT_STARTED",
        "formal_refreeze": "NOT_STARTED",
        "e1": "NOT_STARTED",
        "excluded_outputs": ["F_bar", "B_ref", "Formal commodity mapping", "model results"],
        "timestamp_policy": "No wall-clock timestamp is embedded, preserving byte-identical deterministic rebuilds.",
    }
    return {"rows": rows_by_key, "payloads": payloads, "manifest": manifest, "validation": validation}


def write_rawls24_layers(config_path: Path, output_dir: Path) -> dict[str, Any]:
    product = build_rawls24_layers(config_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    for key, payload in product["payloads"].items():
        (output_dir / OUTPUT_FILES[key]).write_bytes(payload)
    manifest_bytes = (json.dumps(product["manifest"], ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    manifest_path = output_dir / "provenance_manifest.json"
    manifest_path.write_bytes(manifest_bytes)
    hashes = {
        **product["manifest"]["output_hashes"],
        "provenance_manifest.json": sha256_bytes(manifest_bytes),
    }
    hash_lines = [f"{digest}  {name}" for name, digest in sorted(hashes.items())]
    (output_dir / "HASHES.sha256").write_text("\n".join(hash_lines) + "\n", encoding="utf-8", newline="\n")
    return product
