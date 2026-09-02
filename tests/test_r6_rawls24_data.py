import csv
import hashlib
import io
import json
from pathlib import Path

from robust_budget_allocation.data.rawls24 import EXPECTED_NAMES, OUTPUT_FILES, build_rawls24_layers


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/r6_rawls24_data_v1.json"
OUTPUT_DIR = ROOT / "data/r6_rawls24"


def _product():
    return build_rawls24_layers(CONFIG)


def _csv_rows(payload: bytes):
    return list(csv.DictReader(io.StringIO(payload.decode("utf-8"))))


def test_rawls24_identity_is_exactly_24_unique_single_hurricanes():
    product = _product()
    validation = product["validation"]
    assert validation["scenario_count"] == 24
    assert validation["rawls15_count"] == 15
    assert validation["added9_count"] == 9
    assert validation["combined_scenario_count"] == 0
    assert validation["no_hurricane_count"] == 0
    assert validation["synthetic_scenario_count"] == 0
    assert product["manifest"]["hurricane_order"] == list(EXPECTED_NAMES)
    assert product["manifest"]["scenario_order"] == [f"h{i:02d}" for i in range(1, 25)]


def test_unified_demands_are_recomputed_row_by_row_from_category_e_and_s():
    rows = _csv_rows(_product()["payloads"]["unified_demand"])
    assert len(rows) == 24
    for row in rows:
        category = int(row["category"])
        evacuees = int(row["evacuees"])
        sheltered = int(row["sheltered"])
        assert float(row["water_unified"]) == (3 if category <= 2 else 10) * evacuees
        assert float(row["food_unified"]) == (15 if category <= 2 else 35) * sheltered
        assert float(row["medical_unified"]) == sheltered / 4
        assert row["water_formula"] == ("3 * evacuees" if category <= 2 else "10 * evacuees")
        assert row["food_formula"] == ("15 * sheltered" if category <= 2 else "35 * sheltered")
        assert row["medical_formula"] == "sheltered / 4"


def test_rawls15_historical_values_are_preserved_but_never_feed_unified_demand():
    product = _product()
    historical = _csv_rows(product["payloads"]["historical_source"])
    comparison = _csv_rows(product["payloads"]["historical_comparison"])
    assert len(historical) == len(comparison) == 15
    alicia = historical[0]
    assert (alicia["historical_rawls_food_1000_units"], alicia["historical_rawls_medical_units"]) == ("525", "500")
    demand = _csv_rows(product["payloads"]["unified_demand"])[0]
    assert (demand["food_unified"], demand["medical_unified"]) == ("875000", "6250")
    assert product["validation"]["materially_changed_original_events"] == 8
    assert product["validation"]["comparison_status_counts"] == {
        "water": {"same": 14, "changed": 0, "rounding-only": 1},
        "food": {"same": 4, "changed": 8, "rounding-only": 3},
        "medical": {"same": 5, "changed": 8, "rounding-only": 2},
    }


def test_frozen_2004_pairs_and_bounded_evidence_are_exact():
    rows = {row["hurricane_name"]: row for row in _csv_rows(_product()["payloads"]["unified_input"])}
    assert {row["scenario_type"] for row in rows.values()} == {"single_hurricane"}
    assert sum(row["source_group"] == "Rawls15" for row in rows.values()) == 15
    assert sum(row["source_group"] == "Added9" for row in rows.values()) == 9
    assert (rows["Charley"]["evacuees"], rows["Charley"]["sheltered"]) == ("2700000", "102094")
    assert (rows["Frances"]["evacuees"], rows["Frances"]["sheltered"]) == ("1800000", "186620")
    assert (rows["Ivan"]["evacuees"], rows["Ivan"]["sheltered"]) == ("544900", "33472")
    assert (rows["Jeanne"]["evacuees"], rows["Jeanne"]["sheltered"]) == ("4400000", "46252")
    assert rows["Rita"]["evidence_status"] == "FROZEN-BOUND"
    assert "up to" in rows["Rita"]["E_evidence_identity"]
    assert "at least" in rows["Rita"]["S_evidence_identity"]
    assert rows["Elena"]["evidence_status"] == "READY"
    assert "not exact" in rows["Elena"]["notes"]


def test_rebuild_is_deterministic_and_committed_outputs_match():
    first = _product()
    second = _product()
    assert first["manifest"] == second["manifest"]
    assert first["payloads"] == second["payloads"]
    for key, filename in OUTPUT_FILES.items():
        assert (OUTPUT_DIR / filename).read_bytes() == first["payloads"][key]
    stored_manifest = json.loads((OUTPUT_DIR / "provenance_manifest.json").read_text(encoding="utf-8"))
    assert stored_manifest == first["manifest"]


def test_hash_manifest_covers_every_emitted_evidence_file():
    entries = {}
    for line in (OUTPUT_DIR / "HASHES.sha256").read_text(encoding="utf-8").splitlines():
        digest, filename = line.split("  ", 1)
        entries[filename] = digest
    assert set(entries) == {*OUTPUT_FILES.values(), "provenance_manifest.json"}
    for filename, expected in entries.items():
        assert hashlib.sha256((OUTPUT_DIR / filename).read_bytes()).hexdigest() == expected


def test_stage_boundary_explicitly_records_zero_scientific_runs():
    manifest = _product()["manifest"]
    assert manifest["stage"] == "DATA_RECALIBRATION_ONLY"
    assert manifest["parameter_recalibration"] == "NOT_STARTED"
    assert manifest["formal_refreeze"] == "NOT_STARTED"
    assert manifest["e1"] == "NOT_STARTED"
    assert set(manifest["validation"]["scientific_runs"].values()) == {0}
    assert manifest["excluded_outputs"] == ["F_bar", "B_ref", "Formal commodity mapping", "model results"]
    assert manifest["source_audit"]["authoritative_workbook_crosscheck"] == "PASS_24_OF_24"
    assert manifest["source_audit"]["rawls15_identity_category_e_s_crosscheck"] == "PASS_15_OF_15"
