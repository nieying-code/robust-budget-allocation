from __future__ import annotations

import csv
from datetime import date
import hashlib
import json
from pathlib import Path

from robust_budget_allocation.data.caribbean import build_canonical, category_from_knots, reconstruct


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data/formal/caribbean"
MANIFEST = BASE / "CARIBBEAN_DATA_MANIFEST.json"


def _rows(relative: str) -> list[dict[str, str]]:
    with (BASE / relative).open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_source_hashes_and_frozen_horizon() -> None:
    ledger = json.loads((BASE / "raw/source_acquisition.json").read_text(encoding="utf-8"))
    for source in ledger["sources"]:
        path = ROOT / source["local_path"]
        assert path.exists()
        assert _hash(path) == source["sha256"]
    events = _rows("processed/caribbean_historical_events.csv")
    assert events
    assert min(int(row["season_year"]) for row in events) >= 1950
    assert max(int(row["season_year"]) for row in events) <= 2017


def test_event_identity_schema_and_dates() -> None:
    events = _rows("processed/caribbean_historical_events.csv")
    required = {
        "event_id", "source_storm_id", "storm_name", "season_year", "storm_start_date",
        "storm_end_date", "event_date", "two_week_period", "historical_category",
        "severity_class", "storm_lifetime_category", "storm_lifetime_severity", "max_wind",
        "source_dataset", "source_reference", "source_locator", "provenance_class",
        "reconstruction_status", "notes",
    }
    assert required <= set(events[0])
    ids = [row["event_id"] for row in events]
    assert len(ids) == len(set(ids))
    assert all(row["event_id"] == row["source_storm_id"] for row in events)
    assert all(row["event_id"].startswith("AL") for row in events)
    assert all(int(row["event_date"][:4]) == int(row["season_year"]) for row in events)
    assert all(row["event_date"] == row["storm_start_date"] for row in events)
    assert all(row["historical_category"] == row["storm_lifetime_category"] for row in events)
    assert all(row["severity_class"] == row["storm_lifetime_severity"] for row in events)
    assert all(row["historical_category"] in {"TS_OR_LOWER", "H1", "H2", "H3", "H4", "H5"} for row in events)
    assert all(row["severity_class"] in {"Mild", "Strong", "Very Strong"} for row in events)
    assert all(row["two_week_period"] == "" for row in events)


def test_event_country_key_foreign_key_country_and_missingness() -> None:
    events = {row["event_id"] for row in _rows("processed/caribbean_historical_events.csv")}
    rows = _rows("processed/caribbean_event_country.csv")
    countries = {row["iso_or_territory_code"] for row in _rows("intermediate/caribbean_country_identity.csv")}
    keys = [(row["event_id"], row["affected_country_code"]) for row in rows]
    assert len(keys) == len(set(keys))
    assert all(row["event_id"] in events for row in rows)
    assert all(row["affected_country_code"] in countries for row in rows)
    assert all(row["evidence_basis"] in {"CHN", "EMDAT", "BOTH"} for row in rows)
    assert all(row["event_date"] == row["storm_start_date"] for row in rows)
    assert all(row["country_impact_date_status"] in {"RESOLVED", "INTERVAL_ONLY", "CONFLICT", "UNRESOLVED"} for row in rows)
    assert all(row["country_impact_category_status"] in {"RESOLVED", "CONFLICT", "UNRESOLVED"} for row in rows)
    for row in rows:
        for value_key, status_key in (("no_affected", "no_affected_status"), ("total_affected", "total_affected_status")):
            if row[status_key] == "MISSING":
                assert row[value_key] == ""
            if row[value_key] != "":
                assert float(row[value_key]) >= 0
                assert row[status_key] == "OBSERVED"
        assert row["native_demand_value"] == ""
        assert row["native_demand_basis"] == "NOT_GENERATED_R6I_SCOPE"


def test_source_conflicts_and_candidates_are_retained() -> None:
    evidence = _rows("intermediate/storm_country_evidence.csv")
    ambiguous = _rows("intermediate/ambiguous_matches.csv")
    conflicts = _rows("intermediate/source_conflicts.csv")
    assert ambiguous
    assert conflicts
    assert any(row["match_status"] == "TRACK_DERIVED_CANDIDATE" for row in evidence)
    canonical_ids = {(row["event_id"], row["affected_country_code"]) for row in _rows("processed/caribbean_event_country.csv")}
    for row in evidence:
        if not row["match_status"].startswith("CONFIRMED"):
            assert not row["hurdat_storm_id"] or (row["hurdat_storm_id"], row["affected_country_code"]) not in canonical_ids
    assert any(row["conflict_type"] == "HURDAT_CHN_COUNTRY_IMPACT_CATEGORY" for row in conflicts)
    assert {
        "HURDAT_CHN_COUNTRY_IMPACT_CATEGORY",
        "MULTIPLE_CHN_COUNTRY_IMPACT_CATEGORIES",
        "MULTIPLE_CHN_COUNTRY_IMPACT_DATES",
        "CHN_EMDAT_IMPACT_DATE_CONFLICT",
        "EMDAT_IMPACT_INTERVAL_ONLY",
    } <= {row["conflict_type"] for row in conflicts}


def test_population_and_severity_rules() -> None:
    populations = _rows("intermediate/normalized_population.csv")
    assert len(populations) == 20 * 68
    assert {int(row["year"]) for row in populations} == set(range(1950, 2018))
    assert all(int(row["population_1_july_persons"]) > 0 for row in populations)
    events = _rows("processed/caribbean_historical_events.csv")
    expected = {"H1": "Mild", "H2": "Mild", "H3": "Strong", "H4": "Very Strong", "H5": "Very Strong", "TS_OR_LOWER": "Mild"}
    assert all(row["severity_class"] == expected[row["historical_category"]] for row in events)


def _storm(*, winds: list[tuple[str, int]]) -> dict[str, object]:
    observations = [
        {"observation_date": day, "max_wind_knots": wind}
        for day, wind in winds
    ]
    max_wind = max(wind for _, wind in winds)
    return {
        "hurdat_storm_id": "AL012000", "storm_name": "TEST", "season_year": 2000,
        "start_date": date.fromisoformat(winds[0][0]), "end_date": date.fromisoformat(winds[-1][0]),
        "max_wind_knots": max_wind, "historical_category": category_from_knots(max_wind),
        "observations": observations, "source_locator": "synthetic",
    }


def _chn(*, evidence_id: str, day: str, category: str, site: str = "A") -> dict[str, object]:
    return {
        "chn_evidence_id": evidence_id, "match_status": "CONFIRMED_EXACT_NAME_DATE",
        "hurdat_storm_id": "AL012000", "affected_country": "Barbados", "affected_country_code": "BRB",
        "event_date": day, "chn_original_category": category, "source_reference": f"CHN-{site}",
        "source_locator": f"site:{site}",
    }


def _emdat(*, start: str, end: str) -> dict[str, object]:
    return {
        "emdat_evidence_id": "EMDAT-TEST", "match_status": "CONFIRMED_EXACT_NAME_DATE_OVERLAP",
        "hurdat_storm_id": "AL012000", "affected_country": "Barbados", "affected_country_code": "BRB",
        "start_date": start, "end_date": end, "no_affected": "", "total_affected": "",
        "source_reference": "EMDAT-TEST", "source_locator": "row:1",
    }


def _canonical(
    storm: dict[str, object],
    *,
    chn: list[dict[str, object]] | None = None,
    emdat: list[dict[str, object]] | None = None,
) -> tuple[dict[str, object], dict[str, object], list[dict[str, object]]]:
    events, rows, conflicts = build_canonical(
        {"AL012000": storm}, chn or [], emdat or [], {},
    )
    return events[0], rows[0], conflicts


def test_country_impact_uses_timed_hurdat_not_lifetime_max() -> None:
    storm = _storm(winds=[("2000-08-01", 40), ("2000-08-05", 70), ("2000-08-08", 120)])
    event, row, _ = _canonical(storm, chn=[_chn(evidence_id="CHN-A", day="2000-08-05", category="H1")])
    assert event["storm_lifetime_category"] == "H4"
    assert row["storm_lifetime_category"] == "H4"
    assert row["country_impact_category"] == "H1"
    assert row["country_impact_category"] != row["storm_lifetime_category"]


def test_storm_start_date_is_not_country_impact_date() -> None:
    storm = _storm(winds=[("2000-08-01", 40), ("2000-08-05", 70), ("2000-08-08", 120)])
    event, row, _ = _canonical(storm, chn=[_chn(evidence_id="CHN-A", day="2000-08-05", category="H1")])
    assert event["storm_start_date"] == "2000-08-01"
    assert row["country_impact_date"] == "2000-08-05"
    assert row["country_impact_date"] != row["storm_start_date"]


def test_hurdat_precedes_chn_at_country_impact_time() -> None:
    storm = _storm(winds=[("2000-08-01", 40), ("2000-08-05", 100), ("2000-08-08", 120)])
    chn = _chn(evidence_id="CHN-A", day="2000-08-05", category="H2")
    _, row, conflicts = _canonical(storm, chn=[chn])
    assert chn["chn_country_impact_category"] == "H2"
    assert chn["hurdat_country_impact_category"] == "H3"
    assert chn["category_conflict_flag"] == "YES"
    assert row["country_impact_category"] == "H3"
    assert any(x["conflict_type"] == "HURDAT_CHN_COUNTRY_IMPACT_CATEGORY" for x in conflicts)


def test_multiple_chn_site_category_conflict_is_not_aggregated() -> None:
    storm = _storm(winds=[("2000-08-01", 40), ("2000-08-05", 70), ("2000-08-07", 85), ("2000-08-10", 120)])
    site_a = _chn(evidence_id="CHN-A", day="2000-08-05", category="H1", site="A")
    site_b = _chn(evidence_id="CHN-B", day="2000-08-07", category="H2", site="B")
    _, row, conflicts = _canonical(storm, chn=[site_a, site_b])
    assert row["country_impact_category"] == ""
    assert row["country_impact_category_status"] == "CONFLICT"
    assert {site_a["chn_country_impact_category"], site_b["chn_country_impact_category"]} == {"H1", "H2"}
    assert {site_a["adopted_country_impact_category"], site_b["adopted_country_impact_category"]} == {"H1", "H2"}
    assert any(x["conflict_type"] == "MULTIPLE_CHN_COUNTRY_IMPACT_CATEGORIES" for x in conflicts)


def test_chn_date_within_emdat_window_is_canonical_point_date() -> None:
    storm = _storm(winds=[("2000-08-01", 40), ("2000-08-05", 70), ("2000-08-08", 120)])
    _, row, _ = _canonical(
        storm,
        chn=[_chn(evidence_id="CHN-A", day="2000-08-05", category="H1")],
        emdat=[_emdat(start="2000-08-04", end="2000-08-06")],
    )
    assert row["country_impact_date"] == "2000-08-05"
    assert row["country_impact_date_basis"] == "CHN_DATE_WITHIN_EMDAT_WINDOW"
    assert row["country_impact_date_status"] == "RESOLVED"


def test_emdat_interval_only_retains_window_without_point_date() -> None:
    storm = _storm(winds=[("2000-08-01", 40), ("2000-08-05", 70), ("2000-08-08", 120)])
    _, row, conflicts = _canonical(storm, emdat=[_emdat(start="2000-08-04", end="2000-08-06")])
    assert row["country_impact_start_date"] == "2000-08-04"
    assert row["country_impact_end_date"] == "2000-08-06"
    assert row["country_impact_date"] == ""
    assert row["country_impact_date_status"] == "INTERVAL_ONLY"
    assert row["country_impact_category"] == "H1"
    assert row["country_impact_category_basis"] == "MAX_HURDAT_CATEGORY_WITHIN_EMDAT_IMPACT_WINDOW"
    assert any(x["conflict_type"] == "EMDAT_IMPACT_INTERVAL_ONLY" for x in conflicts)


def test_manifest_hashes_and_deterministic_rerun() -> None:
    before = json.loads(MANIFEST.read_text(encoding="utf-8"))
    before_hashes = {row["path"]: row["sha256"] for row in before["outputs"]}
    after = reconstruct()
    after_hashes = {row["path"]: row["sha256"] for row in after["outputs"]}
    assert before_hashes == after_hashes
    for item in after["outputs"]:
        path = ROOT / item["path"]
        assert _hash(path) == item["sha256"]
    assert after["counts"]["canonical_events"] != 0
    assert after["counts"]["canonical_events"] == 211
    assert after["counts"]["canonical_event_country_rows"] == 533
    assert after["scientific_scope"]["m0_m1_m2_scientific_runs"] == 0
    assert after["scientific_scope"]["formal_e1_e5_scientific_runs"] == 0


def test_reconciliation_keeps_statistical_units_separate() -> None:
    rows = _rows("processed/caribbean_reconciliation_summary.csv")
    anchors = {int(row["number"]): row for row in rows if row["source"] != "R6-I current-source reconstruction"}
    assert {67, 62, 5, 188, 310, 268, 494, 852} <= set(anchors)
    assert anchors[188]["statistical_unit"] == "historical hurricane events"
    assert anchors[310]["statistical_unit"] == "generated hurricane-season scenarios"
    assert anchors[188]["verification_status"] == "AUTHOR_REPORTED_UNPUBLISHED_IDENTITIES"


def test_every_canonical_column_has_field_provenance() -> None:
    documented = {row["field_name"] for row in _rows("provenance/caribbean_field_provenance.csv")}
    for relative in ("processed/caribbean_historical_events.csv", "processed/caribbean_event_country.csv"):
        rows = _rows(relative)
        assert set(rows[0]) <= documented
