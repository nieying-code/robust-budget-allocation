"""R6-I 2018-2025 extension built without mutating the frozen 1950-2017 layer."""

from __future__ import annotations

from collections import Counter
import csv
from datetime import date, datetime, timedelta
from decimal import Decimal
import gzip
import json
from pathlib import Path
import re
import shutil
import zipfile
from xml.etree import ElementTree as ET

from robust_budget_allocation.data import caribbean as base


ROOT = base.ROOT
BASE = base.BASE
RAW_EXTENSION = BASE / "raw/emdat_extension_2018_2025"
EXTENSION = BASE / "extension_2018_2025"
EXT_INTERMEDIATE = EXTENSION / "intermediate"
EXT_PROCESSED = EXTENSION / "processed"
EXT_PROVENANCE = EXTENSION / "provenance"
COMBINED = BASE / "combined_1950_2025"
COMBINED_PROCESSED = COMBINED / "processed"
COMBINED_AUDIT = COMBINED / "audit"
MANIFEST = BASE / "CARIBBEAN_DATA_EXTENSION_2018_2025_MANIFEST.json"
REPORT = ROOT / "docs/CARIBBEAN_DATA_EXTENSION_2018_2025.md"
PROVENANCE_REPORT = ROOT / "docs/CARIBBEAN_DATA_EXTENSION_2018_2025_PROVENANCE.md"

SOURCE_LIBRARY = ROOT.parents[1]
SOURCE_FILENAME = "public_emdat_custom_request_2026-09-02_29fd291d-8941-49e3-8719-e8911b23e14e.xlsx"
SOURCE_PATH = SOURCE_LIBRARY / SOURCE_FILENAME
RAW_SOURCE_PATH = RAW_EXTENSION / SOURCE_FILENAME
SOURCE_SHA256 = "1fb5bcb8228cf45a6baa0c39bcd3492e741f488d1ff385c81dc73e219156a600"
SOURCE_BYTES = 197338
FROZEN_BASE_MANIFEST_SHA256 = "648f644da811fe7c6492b554667c5462a4939776f65201ed1461bb71bfdae280"

EVENT_COLUMNS = [
    "event_id", "source_storm_id", "storm_name", "season_year", "storm_start_date",
    "storm_end_date", "event_date", "event_end_date", "two_week_period",
    "storm_lifetime_category", "storm_lifetime_severity", "historical_category",
    "severity_class", "max_wind", "max_wind_unit", "source_dataset",
    "source_reference", "source_locator", "provenance_class",
    "reconstruction_status", "transformation_rule", "notes",
]
EVENT_COUNTRY_COLUMNS = [
    "event_id", "source_storm_id", "storm_name", "season_year", "storm_start_date",
    "storm_end_date", "event_date", "two_week_period", "storm_lifetime_category",
    "storm_lifetime_severity", "historical_category", "severity_class",
    "country_impact_start_date", "country_impact_end_date", "country_impact_date",
    "country_impact_date_status", "country_impact_date_basis",
    "country_impact_category", "country_impact_category_status",
    "country_impact_category_basis", "country_impact_severity", "affected_country",
    "affected_country_code", "evidence_basis", "evidence_ids", "no_affected",
    "no_affected_status", "total_affected", "total_affected_status",
    "event_year_population", "population_unit", "no_affected_pct_population",
    "total_affected_pct_population", "native_demand_basis", "native_demand_value",
    "native_demand_unit", "demand_cap", "source_dataset", "source_reference",
    "source_locator", "provenance_class", "reconstruction_status",
    "transformation_rule", "notes",
]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _xlsx_records(path: Path) -> list[dict[str, str]]:
    """Read the first XLSX sheet with only Python standard-library XML tools."""
    namespace = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    with zipfile.ZipFile(path) as archive:
        shared: list[str] = []
        shared_root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
        for item in shared_root.findall(f"{namespace}si"):
            shared.append("".join(node.text or "" for node in item.iter(f"{namespace}t")))
        sheet = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))

    matrix: list[list[str]] = []
    for row in sheet.iter(f"{namespace}row"):
        values: dict[int, str] = {}
        for cell in row.findall(f"{namespace}c"):
            reference = cell.attrib["r"]
            letters = re.match(r"[A-Z]+", reference)
            if letters is None:
                raise ValueError(f"invalid XLSX cell reference: {reference}")
            column = 0
            for letter in letters.group(0):
                column = column * 26 + ord(letter) - 64
            value_node = cell.find(f"{namespace}v")
            value = "" if value_node is None else (value_node.text or "")
            if cell.attrib.get("t") == "inlineStr":
                inline = cell.find(f"{namespace}is")
                value = (
                    "".join(node.text or "" for node in inline.iter(f"{namespace}t"))
                    if inline is not None
                    else ""
                )
            elif cell.attrib.get("t") == "s" and value:
                value = shared[int(value)]
            values[column - 1] = value
        if values:
            matrix.append([values.get(index, "") for index in range(max(values) + 1)])
    if not matrix:
        raise ValueError("EM-DAT XLSX data sheet is empty")
    headers = matrix[0]
    if len(headers) != 47:
        raise ValueError(f"expected 47 EM-DAT columns; found {len(headers)}")
    records: list[dict[str, str]] = []
    for values in matrix[1:]:
        padded = values + [""] * (len(headers) - len(values))
        records.append(dict(zip(headers, padded[: len(headers)], strict=True)))
    return records


def validate_and_copy_extension_source() -> tuple[list[dict[str, str]], dict[str, object]]:
    if not SOURCE_PATH.exists():
        raise RuntimeError(f"specified EM-DAT extension source missing: {SOURCE_PATH}")
    if SOURCE_PATH.stat().st_size != SOURCE_BYTES or base.sha256(SOURCE_PATH) != SOURCE_SHA256:
        raise RuntimeError(f"specified EM-DAT extension source identity mismatch: {SOURCE_PATH}")
    records = _xlsx_records(SOURCE_PATH)
    years = sorted({int(row["Start Year"]) for row in records})
    subtypes = sorted({row["Disaster Subtype"] for row in records})
    if len(records) != 492 or years != list(range(2018, 2026)) or subtypes != ["Tropical cyclone"]:
        raise RuntimeError(
            f"invalid extension source: rows={len(records)}, years={years}, subtypes={subtypes}"
        )
    RAW_EXTENSION.mkdir(parents=True, exist_ok=True)
    if not RAW_SOURCE_PATH.exists():
        shutil.copyfile(SOURCE_PATH, RAW_SOURCE_PATH)
    if base.sha256(RAW_SOURCE_PATH) != SOURCE_SHA256:
        raise RuntimeError("repository raw copy hash does not match frozen extension source")
    metadata = {
        "identity": "EMDAT_PUBLIC_CUSTOM_REQUEST_2018_2025_2026_08_28",
        "source": "EM-DAT, CRED / UCLouvain, Brussels, Belgium",
        "source_library_path": str(SOURCE_PATH),
        "repository_raw_path": RAW_SOURCE_PATH.relative_to(ROOT).as_posix(),
        "filename": SOURCE_FILENAME,
        "bytes": SOURCE_BYTES,
        "sha256": SOURCE_SHA256,
        "version": "2026-08-28",
        "file_creation_utc": "2026-09-02T03:13:19Z",
        "table_type": "public_emdat_custom_request",
        "records": 492,
        "columns": 47,
        "start_year": 2018,
        "end_year": 2025,
        "disaster_type": "Storm",
        "disaster_subtype": "Tropical cyclone",
    }
    return records, metadata


def parse_hurdat_extension(path: Path) -> tuple[list[dict[str, object]], dict[str, dict[str, object]]]:
    rows: list[dict[str, object]] = []
    summaries: dict[str, dict[str, object]] = {}
    lines = path.read_text(encoding="utf-8").splitlines()
    cursor = 0
    while cursor < len(lines):
        header_line = cursor + 1
        header = [part.strip() for part in lines[cursor].split(",")]
        if len(header) < 3 or not re.fullmatch(r"AL\d{6}", header[0]):
            raise ValueError(f"invalid HURDAT header at source row {header_line}")
        storm_id, name, count_text = header[:3]
        count = int(count_text)
        year = int(storm_id[-4:])
        cursor += 1
        observations: list[dict[str, object]] = []
        for _ in range(count):
            source_row = cursor + 1
            fields = [part.strip() for part in lines[cursor].split(",")]
            cursor += 1
            if not 2018 <= year <= 2025:
                continue
            wind = int(fields[6]) if fields[6] and fields[6] != "-999" else None
            pressure = int(fields[7]) if fields[7] and fields[7] != "-999" else None
            item = {
                "source_row": source_row, "hurdat_storm_id": storm_id, "storm_name": name,
                "season_year": year, "observation_date": datetime.strptime(fields[0], "%Y%m%d").date().isoformat(),
                "observation_time": fields[1].zfill(4), "record_identifier": fields[2],
                "status": fields[3], "latitude": base._coordinate(fields[4]),
                "longitude": base._coordinate(fields[5]),
                "max_wind_knots": "" if wind is None else wind,
                "minimum_pressure_mb": "" if pressure is None else pressure,
                "saffir_simpson_category": base.category_from_knots(wind),
                "source_dataset": "NOAA_NHC_HURDAT2",
                "source_reference": "NHC_HURDAT2_ATLANTIC_1851_2025_2026_02_27",
                "source_locator": f"line:{source_row}",
                "provenance_class": "DIRECT" if wind is None else "RECONSTRUCTED",
            }
            rows.append(item)
            observations.append(item)
        if 2018 <= year <= 2025:
            winds = [int(x["max_wind_knots"]) for x in observations if x["max_wind_knots"] != ""]
            dates = [date.fromisoformat(str(x["observation_date"])) for x in observations]
            max_wind = max(winds) if winds else None
            summaries[storm_id] = {
                "hurdat_storm_id": storm_id, "storm_name": name,
                "normalized_name": base.normalize_name(name), "season_year": year,
                "start_date": min(dates), "end_date": max(dates),
                "max_wind_knots": max_wind,
                "historical_category": base.category_from_knots(max_wind),
                "observations": observations, "source_locator": f"header_line:{header_line}",
            }
    return rows, summaries


def parse_chn_extension(
    ledger: dict[str, object],
    summaries: dict[str, dict[str, object]],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    rows: list[dict[str, object]] = []
    ambiguous: list[dict[str, object]] = []
    for source in ledger["sources"]:  # type: ignore[index]
        if source["source_role"] != "explicit_affected_island_evidence":  # type: ignore[index]
            continue
        paper_code = str(source["paper_country_code"])
        path = ROOT / str(source["local_path"])
        if not path.exists() or base.sha256(path) != source["sha256"]:  # type: ignore[index]
            raise RuntimeError(f"frozen CHN source unavailable or changed: {path}")
        site_code, site_name = base._chn_site(path)
        for sequence, match in enumerate(base.CHN_LINE.finditer(base._html_text(path)), 1):
            event_date = datetime.strptime(match.group(1).title(), "%d %b %Y").date()
            if not 2018 <= event_date.year <= 2025:
                continue
            storm_name = match.group(5).strip()
            name_key = base.normalize_name(storm_name)
            candidates = [
                storm for storm in summaries.values()
                if storm["season_year"] == event_date.year
                and storm["start_date"] - timedelta(days=1) <= event_date <= storm["end_date"] + timedelta(days=1)
                and (name_key == "UNNAMED" or storm["normalized_name"] == name_key)
            ]
            confirmed = candidates[0] if len(candidates) == 1 else None
            row = {
                "chn_evidence_id": f"CHN-{site_code}-{event_date:%Y%m%d}-{sequence:03d}",
                "paper_country_code": paper_code,
                "affected_country": base.COUNTRY_BY_PAPER[paper_code][1],
                "affected_country_code": base.COUNTRY_BY_PAPER[paper_code][2],
                "chn_site_code": site_code, "chn_site_name": site_name,
                "event_date": event_date.isoformat(), "storm_name": storm_name,
                "wind_mph": match.group(2), "chn_original_category": match.group(3).upper(),
                "closest_point_of_approach_miles": "" if match.group(4).lower() == "n/a" else match.group(4),
                "hurdat_storm_id": confirmed["hurdat_storm_id"] if confirmed else "",
                "match_status": "CONFIRMED_EXACT_NAME_DATE" if confirmed else ("AMBIGUOUS" if candidates else "UNMATCHED"),
                "candidate_hurdat_ids": "|".join(str(x["hurdat_storm_id"]) for x in candidates),
                "source_dataset": "CARIBBEAN_HURRICANE_NETWORK",
                "source_reference": str(source["identity"]),
                "source_locator": f"{path.name}:storm_row:{sequence}",
                "source_url": str(source["source_url"]), "source_sha256": str(source["sha256"]),
                "proximity_rule": "named tropical system passing within 60 nautical miles of CHN location",
                "provenance_class": "DIRECT",
            }
            rows.append(row)
            if not confirmed:
                ambiguous.append({
                    "evidence_id": row["chn_evidence_id"], "source_dataset": row["source_dataset"],
                    "source_locator": row["source_locator"], "country_code": row["affected_country_code"],
                    "event_name": storm_name, "event_date": row["event_date"],
                    "candidate_hurdat_ids": row["candidate_hurdat_ids"], "status": row["match_status"],
                    "reason": "CHN row did not resolve to exactly one HURDAT storm by the frozen name/date rule",
                })
    return rows, ambiguous


def parse_emdat_extension(
    records: list[dict[str, str]],
    summaries: dict[str, dict[str, object]],
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    normalized: list[dict[str, object]] = []
    evidence: list[dict[str, object]] = []
    ambiguous: list[dict[str, object]] = []
    for source_row, raw in enumerate(records, 2):
        start, end = base._emdat_date(raw, "Start"), base._emdat_date(raw, "End")
        event_name = raw.get("Event Name", "").strip()
        item: dict[str, object] = {key: raw.get(key, "").strip() for key in records[0]}
        item.update({
            "source_row": source_row, "start_date": start.isoformat() if start else "",
            "end_date": end.isoformat() if end else "",
            "no_affected_status": "OBSERVED" if raw.get("No. Affected", "").strip() else "MISSING",
            "total_affected_status": "OBSERVED" if raw.get("Total Affected", "").strip() else "MISSING",
            "source_dataset": "EM_DAT",
            "source_reference": "EMDAT_PUBLIC_CUSTOM_REQUEST_2018_2025_2026_08_28",
            "source_locator": f"EM-DAT Data!row:{source_row}", "provenance_class": "DIRECT",
        })
        normalized.append(item)
        iso = raw.get("ISO", "").strip()
        if iso not in base.COUNTRY_BY_ISO3:
            continue
        year_text = raw.get("Start Year", "").strip()
        year = int(year_text) if year_text.isdigit() else None
        name_key = base.normalize_name(event_name)
        named = bool(name_key)
        candidates: list[dict[str, object]] = []
        if year is not None:
            for storm in summaries.values():
                if storm["season_year"] != year:
                    continue
                if named and storm["normalized_name"] != name_key:
                    continue
                if start and end and not (storm["start_date"] <= end and storm["end_date"] >= start):
                    continue
                candidates.append(storm)
        confirmed = candidates[0] if named and len(candidates) == 1 and start and end else None
        status = (
            "CONFIRMED_EXACT_NAME_DATE_OVERLAP" if confirmed
            else ("TRACK_DERIVED_CANDIDATE" if not named and candidates else ("AMBIGUOUS" if candidates else "UNMATCHED"))
        )
        row = {
            "emdat_evidence_id": f"EMDAT-{raw.get('DisNo.', '').strip()}",
            "disaster_number": raw.get("DisNo.", "").strip(),
            "affected_country": base.COUNTRY_BY_ISO3[iso][1], "affected_country_code": iso,
            "event_name": event_name, "start_date": start.isoformat() if start else "",
            "end_date": end.isoformat() if end else "",
            "hurdat_storm_id": confirmed["hurdat_storm_id"] if confirmed else "",
            "match_status": status,
            "candidate_hurdat_ids": "|".join(str(x["hurdat_storm_id"]) for x in candidates),
            "no_affected": raw.get("No. Affected", "").strip(),
            "no_affected_status": "OBSERVED" if raw.get("No. Affected", "").strip() else "MISSING",
            "total_affected": raw.get("Total Affected", "").strip(),
            "total_affected_status": "OBSERVED" if raw.get("Total Affected", "").strip() else "MISSING",
            "source_dataset": "EM_DAT",
            "source_reference": "EMDAT_PUBLIC_CUSTOM_REQUEST_2018_2025_2026_08_28",
            "source_locator": f"EM-DAT Data!row:{source_row}", "provenance_class": "DIRECT",
        }
        evidence.append(row)
        if not confirmed:
            ambiguous.append({
                "evidence_id": row["emdat_evidence_id"], "source_dataset": "EM_DAT",
                "source_locator": row["source_locator"], "country_code": iso,
                "event_name": event_name, "event_date": row["start_date"],
                "candidate_hurdat_ids": row["candidate_hurdat_ids"], "status": status,
                "reason": "EM-DAT row lacks a unique named HURDAT match with complete overlapping dates under the frozen rule",
            })
    return normalized, evidence, ambiguous


def parse_population_extension(path: Path) -> tuple[list[dict[str, object]], dict[tuple[str, int], dict[str, object]]]:
    rows: list[dict[str, object]] = []
    lookup: dict[tuple[str, int], dict[str, object]] = {}
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for source_row, raw in enumerate(reader, 2):
            iso = raw["ISO3_code"]
            year = int(raw["Time"])
            if iso not in base.COUNTRY_BY_ISO3 or not 2018 <= year <= 2025:
                continue
            thousands = Decimal(raw["TPopulation1July"])
            persons = int((thousands * 1000).to_integral_value())
            item = {
                "source_row": source_row, "paper_country_code": base.COUNTRY_BY_ISO3[iso][0],
                "country": base.COUNTRY_BY_ISO3[iso][1], "iso3": iso,
                "population_source_location": raw["Location"], "year": year,
                "population_1_july_persons": persons,
                "original_population_thousands": raw["TPopulation1July"], "variant": raw["Variant"],
                "source_dataset": "UN_WPP_2024",
                "source_reference": "UN_WPP_2024_MEDIUM_DEMOGRAPHIC_INDICATORS",
                "source_locator": f"row:{source_row}",
                "transformation_rule": "TPopulation1July (thousands) multiplied by 1000 and rounded to nearest person",
                "provenance_class": "DERIVED",
            }
            rows.append(item)
            lookup[(iso, year)] = item
    return rows, lookup


def _verify_frozen_base() -> dict[str, object]:
    manifest_path = BASE / "CARIBBEAN_DATA_MANIFEST.json"
    observed = base.sha256(manifest_path)
    if observed != FROZEN_BASE_MANIFEST_SHA256:
        raise RuntimeError(
            f"frozen 1950-2017 manifest changed: expected {FROZEN_BASE_MANIFEST_SHA256}, observed {observed}"
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for output in manifest["outputs"]:
        path = ROOT / output["path"]
        if base.sha256(path) != output["sha256"]:
            raise RuntimeError(f"frozen 1950-2017 output changed: {path}")
    return manifest


def _evidence_rows(
    chn_rows: list[dict[str, object]],
    emdat_rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    evidence: list[dict[str, object]] = []
    for row in chn_rows:
        evidence.append({
            "evidence_id": row["chn_evidence_id"], "source_dataset": row["source_dataset"],
            "source_reference": row["source_reference"], "source_locator": row["source_locator"],
            "hurdat_storm_id": row["hurdat_storm_id"], "candidate_hurdat_ids": row["candidate_hurdat_ids"],
            "match_status": row["match_status"], "affected_country": row["affected_country"],
            "affected_country_code": row["affected_country_code"], "evidence_date": row["event_date"],
            "event_name": row["storm_name"], "evidence_type": "CHN_EXPLICIT_WITHIN_60_NM",
            "chn_country_impact_category": row.get("chn_country_impact_category", ""),
            "hurdat_country_impact_category": row.get("hurdat_country_impact_category", ""),
            "conflict_flag": row.get("category_conflict_flag", ""),
            "adopted_country_impact_category": row.get("adopted_country_impact_category", ""),
            "no_affected": "", "total_affected": "", "provenance_class": "DIRECT",
            "notes": "2018-2025 extension; frozen CHN/HURDAT identity and +/-1-day category rules.",
        })
    for row in emdat_rows:
        evidence.append({
            "evidence_id": row["emdat_evidence_id"], "source_dataset": row["source_dataset"],
            "source_reference": row["source_reference"], "source_locator": row["source_locator"],
            "hurdat_storm_id": row["hurdat_storm_id"], "candidate_hurdat_ids": row["candidate_hurdat_ids"],
            "match_status": row["match_status"], "affected_country": row["affected_country"],
            "affected_country_code": row["affected_country_code"], "evidence_date": row["start_date"],
            "event_name": row["event_name"], "evidence_type": "EMDAT_EXPLICIT_COUNTRY_IMPACT",
            "chn_country_impact_category": "", "hurdat_country_impact_category": "",
            "conflict_flag": "", "adopted_country_impact_category": "",
            "no_affected": row["no_affected"], "total_affected": row["total_affected"],
            "provenance_class": "DIRECT",
            "notes": "2018-2025 extension; confirmed only by frozen unique-name and date-overlap rule.",
        })
    return sorted(evidence, key=lambda row: (str(row["source_dataset"]), str(row["evidence_id"])))


def _missingness_rows(
    old_rows: list[dict[str, str]],
    extension_rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    segments = {
        "1950-2017_FROZEN": old_rows,
        "2018-2025_EXTENSION": extension_rows,
        "1950-2025_COMBINED": [*old_rows, *extension_rows],
    }
    output: list[dict[str, object]] = []
    for segment, rows in segments.items():
        for field, status_field in (
            ("no_affected", "no_affected_status"),
            ("total_affected", "total_affected_status"),
        ):
            counts = Counter(str(row[status_field]) for row in rows)
            output.append({
                "segment": segment, "field": field, "rows": len(rows),
                "observed": counts["OBSERVED"], "missing": counts["MISSING"],
                "conflict": counts["CONFLICT"], "unresolved": counts["UNRESOLVED"],
                "supplemented": 0,
                "notes": "Existing EM-DAT values retained; no imputation or supplementation performed.",
            })
        both = sum(
            1 for row in rows
            if row["no_affected_status"] == "OBSERVED" and row["total_affected_status"] == "OBSERVED"
        )
        neither = sum(
            1 for row in rows
            if row["no_affected_status"] == "MISSING" and row["total_affected_status"] == "MISSING"
        )
        any_observed = sum(
            1 for row in rows
            if "OBSERVED" in {str(row["no_affected_status"]), str(row["total_affected_status"])}
        )
        output.append({
            "segment": segment, "field": "row_summary", "rows": len(rows),
            "observed": any_observed, "missing": neither,
            "partially_observed": len(rows) - both - neither, "conflict": 0,
            "unresolved": 0, "supplemented": 0,
            "notes": f"any_observed={any_observed}; both_observed={both}; neither_observed={neither}",
        })
        for row in output[-3:-1]:
            row["partially_observed"] = 0
    return output


def _canonical_content_map(rows: list[dict[str, object]] | list[dict[str, str]], keys: tuple[str, ...]) -> dict[tuple[str, ...], dict[str, object]]:
    return {
        tuple(str(row[key]) for key in keys): {field: row[field] for field in row}
        for row in rows
    }


def build_extension() -> dict[str, object]:
    frozen_manifest = _verify_frozen_base()
    records, extension_source = validate_and_copy_extension_source()
    acquisition = json.loads((BASE / "raw/source_acquisition.json").read_text(encoding="utf-8"))
    sources = {str(item["identity"]): item for item in acquisition["sources"]}
    hurdat_path = ROOT / str(sources["NHC_HURDAT2_ATLANTIC_1851_2025_2026_02_27"]["local_path"])
    wpp_path = ROOT / str(sources["UN_WPP_2024_MEDIUM_DEMOGRAPHIC_INDICATORS"]["local_path"])
    if base.sha256(hurdat_path) != sources["NHC_HURDAT2_ATLANTIC_1851_2025_2026_02_27"]["sha256"]:
        raise RuntimeError("frozen HURDAT2 source hash mismatch")
    if base.sha256(wpp_path) != sources["UN_WPP_2024_MEDIUM_DEMOGRAPHIC_INDICATORS"]["sha256"]:
        raise RuntimeError("frozen WPP source hash mismatch")

    hurdat_rows, summaries = parse_hurdat_extension(hurdat_path)
    chn_rows, chn_ambiguous = parse_chn_extension(acquisition, summaries)
    normalized_emdat, emdat_evidence, emdat_ambiguous = parse_emdat_extension(records, summaries)
    population_rows, population_lookup = parse_population_extension(wpp_path)
    events, event_country, conflicts = base.build_canonical(
        summaries, chn_rows, emdat_evidence, population_lookup,
    )
    events.sort(key=lambda row: (int(row["season_year"]), str(row["event_id"])))
    event_country.sort(key=lambda row: (int(row["season_year"]), str(row["event_id"]), str(row["affected_country_code"])))
    ambiguous = sorted(
        chn_ambiguous + emdat_ambiguous,
        key=lambda row: (str(row["source_dataset"]), str(row["evidence_id"])),
    )
    evidence = _evidence_rows(chn_rows, emdat_evidence)
    unresolved: list[dict[str, object]] = [{
        "record_id": f"MATCH-{row['evidence_id']}", "record_type": "SOURCE_MATCH",
        "source_reference": row["source_dataset"], "source_locator": row["source_locator"],
        "field_or_identity": "hurdat_storm_id", "status": row["status"],
        "observed_evidence": row["candidate_hurdat_ids"], "missing_information": row["reason"],
        "disposition": "excluded from canonical country inclusion; retained in extension evidence layer",
        "notes": "No manual match added and no new matching rule introduced.",
    } for row in ambiguous]
    unresolved.extend([
        {
            "record_id": "EXTENSION-CHN-COVERAGE-2020-2025", "record_type": "SOURCE_COVERAGE_LIMITATION",
            "source_reference": "CHN current 1851-2019 climatology snapshot", "source_locator": "selected frozen CHN pages",
            "field_or_identity": "CHN explicit island evidence", "status": "UNRESOLVED_SOURCE_COVERAGE",
            "observed_evidence": "CHN rows available for extension years 2018-2019 only",
            "missing_information": "No later rows in the frozen CHN snapshot",
            "disposition": "2020-2025 country inclusion can arise only from confirmed EM-DAT evidence under existing rules",
            "notes": "No new source priority or inclusion rule introduced.",
        },
        {
            "record_id": "EXTENSION-AFFECTED-POPULATION-SUPPLEMENTATION", "record_type": "DEFERRED_SCOPE",
            "source_reference": "R6-I extension authorization", "source_locator": "affected-population scope boundary",
            "field_or_identity": "No. Affected / Total Affected", "status": "NOT_PERFORMED",
            "observed_evidence": "EM-DAT observed values and missingness only",
            "missing_information": "future unified supplementation policy",
            "disposition": "preserve observed/missing/conflict without imputation",
            "notes": "No zero fill, donor transfer, interpolation, or model-derived estimate.",
        },
    ])
    unresolved.sort(key=lambda row: str(row["record_id"]))

    chn_columns = [
        "chn_evidence_id", "paper_country_code", "affected_country", "affected_country_code",
        "chn_site_code", "chn_site_name", "event_date", "storm_name", "wind_mph",
        "chn_original_category", "chn_country_impact_category", "closest_point_of_approach_miles",
        "hurdat_storm_id", "match_status", "candidate_hurdat_ids",
        "hurdat_country_impact_category", "category_conflict_flag",
        "adopted_country_impact_category", "country_impact_category_status", "adoption_rule",
        "source_dataset", "source_reference", "source_locator", "source_url", "source_sha256",
        "proximity_rule", "provenance_class",
    ]
    evidence_columns = [
        "evidence_id", "source_dataset", "source_reference", "source_locator", "hurdat_storm_id",
        "candidate_hurdat_ids", "match_status", "affected_country", "affected_country_code",
        "evidence_date", "event_name", "evidence_type", "chn_country_impact_category",
        "hurdat_country_impact_category", "conflict_flag", "adopted_country_impact_category",
        "no_affected", "total_affected", "provenance_class", "notes",
    ]
    ambiguous_columns = [
        "evidence_id", "source_dataset", "source_locator", "country_code", "event_name",
        "event_date", "candidate_hurdat_ids", "status", "reason",
    ]
    conflict_columns = [
        "conflict_id", "conflict_type", "hurdat_storm_id", "country_code", "source_a",
        "value_a", "source_b", "value_b", "resolution", "status", "notes",
    ]
    unresolved_columns = [
        "record_id", "record_type", "source_reference", "source_locator", "field_or_identity",
        "status", "observed_evidence", "missing_information", "disposition", "notes",
    ]
    base.write_csv(EXT_INTERMEDIATE / "normalized_hurdat2_2018_2025.csv", base.HURDAT_COLUMNS, hurdat_rows)
    base.write_csv(EXT_INTERMEDIATE / "normalized_chn_2018_2025.csv", chn_columns, chn_rows)
    base.write_csv(EXT_INTERMEDIATE / "normalized_emdat_2018_2025.csv", list(normalized_emdat[0].keys()), normalized_emdat)
    base.write_csv(EXT_INTERMEDIATE / "normalized_population_2018_2025.csv", list(population_rows[0].keys()), population_rows)
    base.write_csv(EXT_INTERMEDIATE / "storm_country_evidence_2018_2025.csv", evidence_columns, evidence)
    base.write_csv(EXT_INTERMEDIATE / "ambiguous_matches_2018_2025.csv", ambiguous_columns, ambiguous)
    base.write_csv(EXT_INTERMEDIATE / "source_conflicts_2018_2025.csv", conflict_columns, conflicts)
    base.write_csv(EXT_INTERMEDIATE / "unresolved_records_2018_2025.csv", unresolved_columns, unresolved)
    base.write_csv(EXT_PROCESSED / "caribbean_historical_events_2018_2025.csv", EVENT_COLUMNS, events)
    base.write_csv(EXT_PROCESSED / "caribbean_event_country_2018_2025.csv", EVENT_COUNTRY_COLUMNS, event_country)

    old_events = _read_csv(BASE / "processed/caribbean_historical_events.csv")
    old_event_country = _read_csv(BASE / "processed/caribbean_event_country.csv")
    combined_events: list[dict[str, object]] = [*old_events, *events]
    combined_event_country: list[dict[str, object]] = [*old_event_country, *event_country]
    combined_events.sort(key=lambda row: (int(row["season_year"]), str(row["event_id"])))
    combined_event_country.sort(key=lambda row: (int(row["season_year"]), str(row["event_id"]), str(row["affected_country_code"])))
    base.write_csv(COMBINED_PROCESSED / "caribbean_historical_events_1950_2025.csv", EVENT_COLUMNS, combined_events)
    base.write_csv(COMBINED_PROCESSED / "caribbean_event_country_1950_2025.csv", EVENT_COUNTRY_COLUMNS, combined_event_country)

    old_conflicts = _read_csv(BASE / "intermediate/source_conflicts.csv")
    combined_conflicts = sorted([*old_conflicts, *conflicts], key=lambda row: str(row["conflict_id"]))
    base.write_csv(COMBINED_AUDIT / "source_conflicts_1950_2025.csv", conflict_columns, combined_conflicts)
    old_unresolved = _read_csv(BASE / "intermediate/unresolved_records.csv")
    combined_unresolved = sorted([*old_unresolved, *unresolved], key=lambda row: str(row["record_id"]))
    base.write_csv(
        COMBINED_AUDIT / "unresolved_records_1950_2025.csv",
        unresolved_columns,
        combined_unresolved,
    )
    missingness = _missingness_rows(old_event_country, event_country)
    missingness_columns = [
        "segment", "field", "rows", "observed", "missing", "partially_observed",
        "conflict", "unresolved", "supplemented", "notes",
    ]
    base.write_csv(COMBINED_AUDIT / "affected_population_missingness_1950_2025.csv", missingness_columns, missingness)

    reconstruction_summary = [
        {
            "segment": "1950-2017_FROZEN", "start_year": 1950, "end_year": 2017,
            "canonical_events": len(old_events), "event_country_rows": len(old_event_country),
            "identity": "audited frozen R6-I reconstruction", "status": "UNCHANGED",
        },
        {
            "segment": "2018-2025_EXTENSION", "start_year": 2018, "end_year": 2025,
            "canonical_events": len(events), "event_country_rows": len(event_country),
            "identity": "source-based extension under frozen R6-I rules", "status": "RECONSTRUCTED",
        },
        {
            "segment": "1950-2025_COMBINED", "start_year": 1950, "end_year": 2025,
            "canonical_events": len(combined_events), "event_country_rows": len(combined_event_country),
            "identity": "frozen base union extension", "status": "COMBINED",
        },
    ]
    base.write_csv(
        COMBINED_AUDIT / "caribbean_reconstruction_summary_1950_2025.csv",
        ["segment", "start_year", "end_year", "canonical_events", "event_country_rows", "identity", "status"],
        reconstruction_summary,
    )

    country_counts = Counter(str(row["affected_country_code"]) for row in event_country)
    coverage_rows = [{
        "affected_country": country[1], "affected_country_code": country[2],
        "event_country_rows": country_counts[country[2]],
        "coverage_status": "PRESENT" if country_counts[country[2]] else "NO_CANONICAL_EXTENSION_ROW",
        "notes": "Absence is not interpreted as evidence of no physical impact.",
    } for country in base.COUNTRIES]
    base.write_csv(
        EXT_PROCESSED / "caribbean_country_coverage_2018_2025.csv",
        ["affected_country", "affected_country_code", "event_country_rows", "coverage_status", "notes"],
        coverage_rows,
    )
    yearly_counts = Counter(int(row["season_year"]) for row in events)
    yearly_rows = [{"season_year": year, "canonical_events": yearly_counts[year]} for year in range(2018, 2026)]
    base.write_csv(
        EXT_PROCESSED / "caribbean_event_counts_by_year_2018_2025.csv",
        ["season_year", "canonical_events"], yearly_rows,
    )
    provenance = base.provenance_rows()
    base.write_csv(EXT_PROVENANCE / "caribbean_field_provenance_2018_2025.csv", list(provenance[0].keys()), provenance)

    old_event_map = _canonical_content_map(old_events, ("event_id",))
    combined_old_event_map = _canonical_content_map(
        [row for row in combined_events if int(row["season_year"]) <= 2017], ("event_id",),
    )
    old_country_map = _canonical_content_map(old_event_country, ("event_id", "affected_country_code"))
    combined_old_country_map = _canonical_content_map(
        [row for row in combined_event_country if int(row["season_year"]) <= 2017],
        ("event_id", "affected_country_code"),
    )
    regression = {
        "status": "PASS" if old_event_map == combined_old_event_map and old_country_map == combined_old_country_map else "FAIL",
        "frozen_base_manifest_sha256": FROZEN_BASE_MANIFEST_SHA256,
        "old_event_count": len(old_events), "combined_projection_old_event_count": len(combined_old_event_map),
        "old_event_country_count": len(old_event_country),
        "combined_projection_old_event_country_count": len(combined_old_country_map),
        "event_fields_compared": EVENT_COLUMNS,
        "event_country_fields_compared": EVENT_COUNTRY_COLUMNS,
        "event_content_identical": old_event_map == combined_old_event_map,
        "event_country_content_identical": old_country_map == combined_old_country_map,
        "frozen_outputs_verified": len(frozen_manifest["outputs"]),
        "affected_population_note": "Observed/missing values remain unchanged in this extension; later supplementation is a separately authorized future stage.",
    }
    if regression["status"] != "PASS":
        raise RuntimeError("1950-2017 scientific content changed in combined projection")
    regression_path = COMBINED_AUDIT / "frozen_1950_2017_regression.json"
    regression_path.parent.mkdir(parents=True, exist_ok=True)
    regression_path.write_text(json.dumps(regression, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")

    source_ledger = {
        "schema_version": 1,
        "document_type": "R6_I_2018_2025_EXTENSION_SOURCE_ACQUISITION",
        "new_emdat_source": extension_source,
        "reused_frozen_sources": [
            {key: sources[identity][key] for key in ("identity", "source_url", "source_role", "local_path", "sha256")}
            for identity in (
                "NHC_HURDAT2_ATLANTIC_1851_2025_2026_02_27",
                "UN_WPP_2024_MEDIUM_DEMOGRAPHIC_INDICATORS",
            )
        ],
        "chn_source_identity": "same 35 frozen current CHN index/pages; coverage ends 2019",
        "frozen_old_manifest_sha256": FROZEN_BASE_MANIFEST_SHA256,
    }
    source_ledger_path = RAW_EXTENSION / "extension_source_acquisition.json"
    source_ledger_path.write_text(json.dumps(source_ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")

    # Re-verify frozen old files after every extension write.
    _verify_frozen_base()
    generated = sorted(
        [path for path in EXTENSION.rglob("*") if path.is_file()]
        + [path for path in COMBINED.rglob("*") if path.is_file()]
        + [source_ledger_path]
        + [path for path in (REPORT, PROVENANCE_REPORT) if path.is_file()],
        key=lambda path: path.as_posix(),
    )
    category_status = Counter(str(row["country_impact_category_status"]) for row in event_country)
    date_status = Counter(str(row["country_impact_date_status"]) for row in event_country)
    lifetime_severity = Counter(str(row["storm_lifetime_severity"]) for row in events)
    impact_severity = Counter(str(row["country_impact_severity"]) for row in event_country if row["country_impact_severity"])
    for status in ("RESOLVED", "CONFLICT", "UNRESOLVED"):
        category_status.setdefault(status, 0)
    for status in ("RESOLVED", "INTERVAL_ONLY", "CONFLICT", "UNRESOLVED"):
        date_status.setdefault(status, 0)
    manifest = {
        "schema_version": 1,
        "dataset_identity": "R6_I_CARIBBEAN_HISTORICAL_RECONSTRUCTION_EXTENSION_2018_2025",
        "combined_identity": "R6_I_CARIBBEAN_HISTORICAL_RECONSTRUCTION_1950_2025",
        "new_emdat_source": extension_source,
        "frozen_base": regression,
        "rules": {
            "rule_set": "same frozen R6-I reconstruction rules used by 1950-2017",
            "new_scientific_rule_added": False, "chn_match_tolerance_days": 1,
            "affected_population_supplementation_performed": False,
            "two_week_period_rule_changed": False,
        },
        "extension_counts": {
            "canonical_events": len(events), "canonical_event_country_rows": len(event_country),
            "events_by_year": dict(sorted(yearly_counts.items())),
            "country_coverage_count": sum(1 for value in country_counts.values() if value),
            "ambiguous_or_unmatched_records": len(ambiguous), "conflicts": len(conflicts),
            "unresolved_ledger_records": len(unresolved),
        },
        "combined_counts": {
            "canonical_events": len(combined_events),
            "canonical_event_country_rows": len(combined_event_country),
        },
        "storm_lifetime_severity_counts": dict(sorted(lifetime_severity.items())),
        "country_impact_severity_counts": dict(sorted(impact_severity.items())),
        "country_impact_category_status_counts": dict(sorted(category_status.items())),
        "country_impact_date_status_counts": dict(sorted(date_status.items())),
        "affected_population_missingness": missingness,
        "remaining_unresolved_records": len(combined_unresolved),
        "remaining_conflict_type_counts": dict(sorted(Counter(str(row["conflict_type"]) for row in conflicts).items())),
        "outputs": [{
            "path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size,
            "sha256": base.sha256(path),
            "rows": sum(1 for _ in path.open("r", encoding="utf-8")) - 1 if path.suffix == ".csv" else None,
        } for path in generated],
        "scripts": [{
            "path": path.relative_to(ROOT).as_posix(), "sha256": base.sha256(path),
        } for path in (Path(__file__), ROOT / "scripts/r6i_extend_caribbean_2018_2025.py")],
        "scientific_scope": {
            "m0_m1_m2_scientific_runs": 0, "formal_e1_e5_scientific_runs": 0,
            "gurobi_invoked": False, "b_ref_calculated": False,
            "affected_population_supplementation_performed": False, "r6_ii_started": False,
        },
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return manifest
