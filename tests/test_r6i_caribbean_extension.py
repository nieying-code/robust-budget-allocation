from __future__ import annotations

import csv
from datetime import date
import hashlib
import json
from pathlib import Path

from robust_budget_allocation.data.caribbean import build_canonical, category_from_knots
from robust_budget_allocation.data.caribbean_extension import (
    BASE,
    FROZEN_BASE_MANIFEST_SHA256,
    MANIFEST,
    SOURCE_PATH,
    SOURCE_SHA256,
    _xlsx_records,
    build_extension,
)


ROOT = Path(__file__).resolve().parents[1]
EXTENSION = BASE / "extension_2018_2025"
COMBINED = BASE / "combined_1950_2025"


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_extension_emdat_source_identity_and_scope() -> None:
    assert SOURCE_PATH.exists()
    assert _hash(SOURCE_PATH) == SOURCE_SHA256
    rows = _xlsx_records(SOURCE_PATH)
    assert len(rows) == 492
    assert {row["Disaster Subtype"] for row in rows} == {"Tropical cyclone"}
    assert {row["Disaster Type"] for row in rows} == {"Storm"}
    assert {int(row["Start Year"]) for row in rows} == set(range(2018, 2026))


def test_extension_boundaries_identity_and_aliases() -> None:
    events = _rows(EXTENSION / "processed/caribbean_historical_events_2018_2025.csv")
    years = {int(row["season_year"]) for row in events}
    assert years == set(range(2018, 2026))
    assert 2017 not in years
    assert 2026 not in years
    ids = [row["event_id"] for row in events]
    assert len(ids) == len(set(ids))
    assert all(row["event_date"] == row["storm_start_date"] for row in events)
    assert all(row["historical_category"] == row["storm_lifetime_category"] for row in events)
    assert all(row["severity_class"] == row["storm_lifetime_severity"] for row in events)
    assert all(row["two_week_period"] == "" for row in events)


def test_extension_event_country_semantics_and_foreign_keys() -> None:
    events = {
        row["event_id"]
        for row in _rows(EXTENSION / "processed/caribbean_historical_events_2018_2025.csv")
    }
    rows = _rows(EXTENSION / "processed/caribbean_event_country_2018_2025.csv")
    keys = [(row["event_id"], row["affected_country_code"]) for row in rows]
    assert len(keys) == len(set(keys))
    assert all(row["event_id"] in events for row in rows)
    assert all(row["country_impact_category_status"] in {"RESOLVED", "CONFLICT", "UNRESOLVED"} for row in rows)
    assert all(row["country_impact_date_status"] in {"RESOLVED", "INTERVAL_ONLY", "CONFLICT", "UNRESOLVED"} for row in rows)
    assert all(row["native_demand_basis"] == "NOT_GENERATED_R6I_SCOPE" for row in rows)
    assert all(row["native_demand_value"] == "" for row in rows)
    for row in rows:
        if row["evidence_basis"] == "EMDAT" and row["country_impact_category"]:
            assert row["country_impact_category_basis"] == "MAX_HURDAT_CATEGORY_WITHIN_EMDAT_IMPACT_WINDOW"
        if row["country_impact_date_status"] == "INTERVAL_ONLY":
            assert row["country_impact_date"] == ""
            assert row["country_impact_start_date"]
            assert row["country_impact_end_date"]


def test_frozen_plus_or_minus_one_day_category_rule() -> None:
    observations = [
        {"observation_date": "2020-08-04", "max_wind_knots": 100},
        {"observation_date": "2020-08-05", "max_wind_knots": 70},
        {"observation_date": "2020-08-06", "max_wind_knots": 85},
        {"observation_date": "2020-08-10", "max_wind_knots": 120},
    ]
    storm = {
        "hurdat_storm_id": "AL012020", "storm_name": "TEST", "season_year": 2020,
        "start_date": date(2020, 8, 4), "end_date": date(2020, 8, 10),
        "max_wind_knots": 120, "historical_category": category_from_knots(120),
        "observations": observations, "source_locator": "synthetic",
    }
    chn = {
        "chn_evidence_id": "CHN-TEST", "match_status": "CONFIRMED_EXACT_NAME_DATE",
        "hurdat_storm_id": "AL012020", "affected_country": "Barbados",
        "affected_country_code": "BRB", "event_date": "2020-08-05",
        "chn_original_category": "H1", "source_reference": "CHN-TEST",
        "source_locator": "synthetic",
    }
    events, rows, conflicts = build_canonical({"AL012020": storm}, [chn], [], {})
    assert events[0]["storm_lifetime_category"] == "H4"
    assert chn["hurdat_country_impact_category"] == "H3"
    assert rows[0]["country_impact_category"] == "H3"
    assert any(item["conflict_type"] == "HURDAT_CHN_COUNTRY_IMPACT_CATEGORY" for item in conflicts)


def test_frozen_1950_2017_layer_is_byte_and_content_identical() -> None:
    assert _hash(BASE / "CARIBBEAN_DATA_MANIFEST.json") == FROZEN_BASE_MANIFEST_SHA256
    regression = json.loads(
        (COMBINED / "audit/frozen_1950_2017_regression.json").read_text(encoding="utf-8")
    )
    assert regression["status"] == "PASS"
    assert regression["event_content_identical"] is True
    assert regression["event_country_content_identical"] is True
    assert regression["old_event_count"] == regression["combined_projection_old_event_count"] == 211
    assert regression["old_event_country_count"] == regression["combined_projection_old_event_country_count"] == 533
    old_manifest = json.loads((BASE / "CARIBBEAN_DATA_MANIFEST.json").read_text(encoding="utf-8"))
    assert regression["frozen_outputs_verified"] == len(old_manifest["outputs"])
    for output in old_manifest["outputs"]:
        assert _hash(ROOT / output["path"]) == output["sha256"]


def test_combined_is_exact_union_of_frozen_base_and_extension() -> None:
    old_events = _rows(BASE / "processed/caribbean_historical_events.csv")
    extension_events = _rows(EXTENSION / "processed/caribbean_historical_events_2018_2025.csv")
    combined_events = _rows(COMBINED / "processed/caribbean_historical_events_1950_2025.csv")
    old_rows = _rows(BASE / "processed/caribbean_event_country.csv")
    extension_rows = _rows(EXTENSION / "processed/caribbean_event_country_2018_2025.csv")
    combined_rows = _rows(COMBINED / "processed/caribbean_event_country_1950_2025.csv")
    assert len(combined_events) == len(old_events) + len(extension_events)
    assert len(combined_rows) == len(old_rows) + len(extension_rows)
    assert {row["event_id"] for row in combined_events} == {
        row["event_id"] for row in [*old_events, *extension_events]
    }
    assert {(row["event_id"], row["affected_country_code"]) for row in combined_rows} == {
        (row["event_id"], row["affected_country_code"])
        for row in [*old_rows, *extension_rows]
    }


def test_affected_population_is_observed_or_missing_without_supplementation() -> None:
    rows = _rows(EXTENSION / "processed/caribbean_event_country_2018_2025.csv")
    for row in rows:
        for value_field, status_field in (
            ("no_affected", "no_affected_status"),
            ("total_affected", "total_affected_status"),
        ):
            assert row[status_field] in {"OBSERVED", "MISSING", "CONFLICT", "UNRESOLVED"}
            if row[status_field] == "MISSING":
                assert row[value_field] == ""
            if row[value_field]:
                assert float(row[value_field]) >= 0
                assert row[status_field] == "OBSERVED"
    inventory = _rows(COMBINED / "audit/affected_population_missingness_1950_2025.csv")
    assert {row["segment"] for row in inventory} == {
        "1950-2017_FROZEN", "2018-2025_EXTENSION", "1950-2025_COMBINED"
    }
    assert all(row["supplemented"] == "0" for row in inventory)


def test_extension_provenance_and_manifest_hashes() -> None:
    documented = {
        row["field_name"]
        for row in _rows(EXTENSION / "provenance/caribbean_field_provenance_2018_2025.csv")
    }
    for path in (
        EXTENSION / "processed/caribbean_historical_events_2018_2025.csv",
        EXTENSION / "processed/caribbean_event_country_2018_2025.csv",
    ):
        rows = _rows(path)
        assert set(rows[0]) <= documented
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["rules"]["new_scientific_rule_added"] is False
    assert manifest["scientific_scope"]["affected_population_supplementation_performed"] is False
    assert manifest["scientific_scope"]["gurobi_invoked"] is False
    assert manifest["scientific_scope"]["r6_ii_started"] is False
    for output in manifest["outputs"]:
        assert _hash(ROOT / output["path"]) == output["sha256"]


def test_extension_deterministic_rebuild_and_manifest_stability() -> None:
    before = json.loads(MANIFEST.read_text(encoding="utf-8"))
    before_hashes = {item["path"]: item["sha256"] for item in before["outputs"]}
    before_manifest_hash = _hash(MANIFEST)
    after = build_extension()
    after_hashes = {item["path"]: item["sha256"] for item in after["outputs"]}
    assert before_hashes == after_hashes
    assert _hash(MANIFEST) == before_manifest_hash
