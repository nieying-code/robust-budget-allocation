"""Deterministic, source-based Caribbean historical reconstruction for R6-I.

This module implements public-source identity and matching rules. It does not
attempt to reproduce the unpublished Balcik et al. 188-event merge and never
invokes an optimization solver.
"""

from __future__ import annotations

from collections import Counter, defaultdict
import csv
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
import gzip
import hashlib
from html import unescape
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from typing import Iterable


ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / "data/formal/caribbean"
RAW = BASE / "raw"
INTERMEDIATE = BASE / "intermediate"
PROCESSED = BASE / "processed"
PROVENANCE = BASE / "provenance"
MANIFEST = BASE / "CARIBBEAN_DATA_MANIFEST.json"

COUNTRIES = (
    ("AIA", "Anguilla", "AIA", "Anguilla"),
    ("ATG", "Antigua and Barbuda", "ATG", "Antigua and Barbuda"),
    ("BHS", "Bahamas", "BHS", "Bahamas"),
    ("BLZ", "Belize", "BLZ", "Belize"),
    ("BMU", "Bermuda", "BMU", "Bermuda"),
    ("BRB", "Barbados", "BRB", "Barbados"),
    ("BVI", "British Virgin Islands", "VGB", "British Virgin Islands"),
    ("CYM", "Cayman Islands", "CYM", "Cayman Islands"),
    ("DMA", "Dominica", "DMA", "Dominica"),
    ("GRD", "Grenada", "GRD", "Grenada"),
    ("GUY", "Guyana", "GUY", "Guyana"),
    ("HTI", "Haiti", "HTI", "Haiti"),
    ("JAM", "Jamaica", "JAM", "Jamaica"),
    ("KNA", "Saint Kitts and Nevis", "KNA", "Saint Kitts and Nevis"),
    ("LCA", "Saint Lucia", "LCA", "Saint Lucia"),
    ("MST", "Montserrat", "MSR", "Montserrat"),
    ("SUR", "Suriname", "SUR", "Suriname"),
    ("TCA", "Turks and Caicos Islands", "TCA", "Turks and Caicos Islands"),
    ("TTO", "Trinidad and Tobago", "TTO", "Trinidad and Tobago"),
    ("VCT", "Saint Vincent and the Grenadines", "VCT", "Saint Vincent and the Grenadines"),
)
COUNTRY_BY_PAPER = {row[0]: row for row in COUNTRIES}
COUNTRY_BY_ISO3 = {row[2]: row for row in COUNTRIES}

HURDAT_COLUMNS = [
    "source_row", "hurdat_storm_id", "storm_name", "season_year", "observation_date",
    "observation_time", "record_identifier", "status", "latitude", "longitude",
    "max_wind_knots", "minimum_pressure_mb", "saffir_simpson_category",
    "source_dataset", "source_reference", "source_locator", "provenance_class",
]


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_csv(path: Path, fieldnames: list[str], rows: Iterable[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def normalize_name(value: str) -> str:
    value = unescape(value).upper().replace("’", "'")
    value = re.sub(r"\b(HURRICANE|TROPICAL STORM|TROPICAL CYCLONE|CYCLONE|STORM)\b", " ", value)
    return re.sub(r"[^A-Z0-9]", "", value)


def category_from_knots(wind: int | None) -> str:
    if wind is None:
        return ""
    if wind >= 137:
        return "H5"
    if wind >= 113:
        return "H4"
    if wind >= 96:
        return "H3"
    if wind >= 83:
        return "H2"
    if wind >= 64:
        return "H1"
    return "TS_OR_LOWER"


def severity(category: str) -> str:
    if category in {"H4", "H5"}:
        return "Very Strong"
    if category == "H3":
        return "Strong"
    if category:
        return "Mild"
    return ""


def _coordinate(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    sign = -1 if value[-1] in "SW" else 1
    return f"{sign * float(value[:-1]):.3f}"


def parse_hurdat(path: Path) -> tuple[list[dict[str, object]], dict[str, dict[str, object]]]:
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
            if len(fields) < 8:
                raise ValueError(f"invalid HURDAT observation at source row {source_row}")
            if not 1950 <= year <= 2017:
                continue
            wind = int(fields[6]) if fields[6] and fields[6] != "-999" else None
            pressure = int(fields[7]) if fields[7] and fields[7] != "-999" else None
            item = {
                "source_row": source_row,
                "hurdat_storm_id": storm_id,
                "storm_name": name,
                "season_year": year,
                "observation_date": datetime.strptime(fields[0], "%Y%m%d").date().isoformat(),
                "observation_time": fields[1].zfill(4),
                "record_identifier": fields[2],
                "status": fields[3],
                "latitude": _coordinate(fields[4]),
                "longitude": _coordinate(fields[5]),
                "max_wind_knots": "" if wind is None else wind,
                "minimum_pressure_mb": "" if pressure is None else pressure,
                "saffir_simpson_category": category_from_knots(wind),
                "source_dataset": "NOAA_NHC_HURDAT2",
                "source_reference": "NHC_HURDAT2_ATLANTIC_1851_2025_2026_02_27",
                "source_locator": f"line:{source_row}",
                "provenance_class": "DIRECT" if wind is None else "RECONSTRUCTED",
            }
            rows.append(item)
            observations.append(item)
        if 1950 <= year <= 2017:
            winds = [int(x["max_wind_knots"]) for x in observations if x["max_wind_knots"] != ""]
            dates = [date.fromisoformat(str(x["observation_date"])) for x in observations]
            max_wind = max(winds) if winds else None
            summaries[storm_id] = {
                "hurdat_storm_id": storm_id,
                "storm_name": name,
                "normalized_name": normalize_name(name),
                "season_year": year,
                "start_date": min(dates),
                "end_date": max(dates),
                "max_wind_knots": max_wind,
                "historical_category": category_from_knots(max_wind),
                "observations": observations,
                "source_locator": f"header_line:{header_line}",
            }
    return rows, summaries


def _html_text(path: Path) -> str:
    parser = _TextExtractor()
    parser.feed(path.read_text(encoding="latin-1"))
    return "\n".join(unescape(part) for part in parser.parts)


CHN_LINE = re.compile(
    r"(?m)^\s*(\d{1,2}\s+[A-Z][a-z]{2}\s+\d{4})\s+(\d+)\s+(ts|h[1-5])\s+(\d+|n/a)\s+([^\r\n]+?)\s*$",
    re.IGNORECASE,
)


def _chn_site(path: Path) -> tuple[str, str]:
    text = _html_text(path)
    match = re.search(r"([A-Za-z0-9 .,'&/-]+)\s*\(([A-Z0-9]{4})\)", text)
    return (match.group(2), match.group(1).strip()) if match else (path.name[:4], path.name[:4])


def parse_chn(ledger: dict[str, object], summaries: dict[str, dict[str, object]]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    rows: list[dict[str, object]] = []
    ambiguous: list[dict[str, object]] = []
    for source in ledger["sources"]:  # type: ignore[index]
        if source["source_role"] != "explicit_affected_island_evidence":  # type: ignore[index]
            continue
        paper_code = str(source["paper_country_code"])
        path = ROOT / str(source["local_path"])
        site_code, site_name = _chn_site(path)
        for sequence, match in enumerate(CHN_LINE.finditer(_html_text(path)), 1):
            event_date = datetime.strptime(match.group(1).title(), "%d %b %Y").date()
            if not 1950 <= event_date.year <= 2017:
                continue
            storm_name = match.group(5).strip()
            name_key = normalize_name(storm_name)
            candidates = [
                s for s in summaries.values()
                if s["season_year"] == event_date.year
                and s["start_date"] - timedelta(days=1) <= event_date <= s["end_date"] + timedelta(days=1)
                and (name_key == "UNNAMED" or s["normalized_name"] == name_key)
            ]
            matched = candidates[0] if len(candidates) == 1 else None
            row = {
                "chn_evidence_id": f"CHN-{site_code}-{event_date:%Y%m%d}-{sequence:03d}",
                "paper_country_code": paper_code,
                "affected_country": COUNTRY_BY_PAPER[paper_code][1],
                "affected_country_code": COUNTRY_BY_PAPER[paper_code][2],
                "chn_site_code": site_code,
                "chn_site_name": site_name,
                "event_date": event_date.isoformat(),
                "storm_name": storm_name,
                "wind_mph": match.group(2),
                "chn_original_category": match.group(3).upper(),
                "closest_point_of_approach_miles": "" if match.group(4).lower() == "n/a" else match.group(4),
                "hurdat_storm_id": matched["hurdat_storm_id"] if matched else "",
                "match_status": "CONFIRMED_EXACT_NAME_DATE" if matched else ("AMBIGUOUS" if candidates else "UNMATCHED"),
                "candidate_hurdat_ids": "|".join(str(x["hurdat_storm_id"]) for x in candidates),
                "source_dataset": "CARIBBEAN_HURRICANE_NETWORK",
                "source_reference": str(source["identity"]),
                "source_locator": f"{path.name}:storm_row:{sequence}",
                "source_url": str(source["source_url"]),
                "source_sha256": str(source["sha256"]),
                "proximity_rule": "named tropical system passing within 60 nautical miles of CHN location",
                "provenance_class": "DIRECT",
            }
            rows.append(row)
            if not matched:
                ambiguous.append({"evidence_id": row["chn_evidence_id"], "source_dataset": row["source_dataset"], "source_locator": row["source_locator"], "country_code": row["affected_country_code"], "event_name": storm_name, "event_date": row["event_date"], "candidate_hurdat_ids": row["candidate_hurdat_ids"], "status": row["match_status"], "reason": "CHN row did not resolve to exactly one HURDAT storm by name/date"})
    return rows, ambiguous


def _emdat_date(row: dict[str, str], prefix: str) -> date | None:
    try:
        year = int(row[f"{prefix} Year"])
        month = int(row[f"{prefix} Month"])
        day = int(row[f"{prefix} Day"])
        return date(year, month, day)
    except (KeyError, TypeError, ValueError):
        return None


def parse_emdat(path: Path, summaries: dict[str, dict[str, object]]) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    normalized: list[dict[str, object]] = []
    evidence: list[dict[str, object]] = []
    ambiguous: list[dict[str, object]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for source_row, raw in enumerate(reader, 2):
            start, end = _emdat_date(raw, "Start"), _emdat_date(raw, "End")
            event_name = raw.get("Event Name", "").strip()
            item = {key: raw.get(key, "").strip() for key in reader.fieldnames or []}
            item.update({
                "source_row": source_row,
                "start_date": start.isoformat() if start else "",
                "end_date": end.isoformat() if end else "",
                "no_affected_status": "OBSERVED" if raw.get("No. Affected", "").strip() else "MISSING",
                "total_affected_status": "OBSERVED" if raw.get("Total Affected", "").strip() else "MISSING",
                "source_dataset": "EM_DAT",
                "source_reference": "EMDAT_PUBLIC_CUSTOM_REQUEST_2026_08_28",
                "source_locator": f"row:{source_row}",
                "provenance_class": "DIRECT",
            })
            normalized.append(item)
            iso = raw.get("ISO", "").strip()
            if iso not in COUNTRY_BY_ISO3:
                continue
            year_text = raw.get("Start Year", "").strip()
            year = int(year_text) if year_text.isdigit() else None
            name_key = normalize_name(event_name)
            named = bool(name_key)
            candidates = []
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
            status = "CONFIRMED_EXACT_NAME_DATE_OVERLAP" if confirmed else ("TRACK_DERIVED_CANDIDATE" if not named and candidates else ("AMBIGUOUS" if candidates else "UNMATCHED"))
            ev = {
                "emdat_evidence_id": f"EMDAT-{raw.get('DisNo.', '').strip()}",
                "disaster_number": raw.get("DisNo.", "").strip(),
                "affected_country": COUNTRY_BY_ISO3[iso][1],
                "affected_country_code": iso,
                "event_name": event_name,
                "start_date": start.isoformat() if start else "",
                "end_date": end.isoformat() if end else "",
                "hurdat_storm_id": confirmed["hurdat_storm_id"] if confirmed else "",
                "match_status": status,
                "candidate_hurdat_ids": "|".join(str(x["hurdat_storm_id"]) for x in candidates),
                "no_affected": raw.get("No. Affected", "").strip(),
                "no_affected_status": "OBSERVED" if raw.get("No. Affected", "").strip() else "MISSING",
                "total_affected": raw.get("Total Affected", "").strip(),
                "total_affected_status": "OBSERVED" if raw.get("Total Affected", "").strip() else "MISSING",
                "source_dataset": "EM_DAT",
                "source_reference": "EMDAT_PUBLIC_CUSTOM_REQUEST_2026_08_28",
                "source_locator": f"row:{source_row}",
                "provenance_class": "DIRECT",
            }
            evidence.append(ev)
            if not confirmed:
                ambiguous.append({"evidence_id": ev["emdat_evidence_id"], "source_dataset": "EM_DAT", "source_locator": ev["source_locator"], "country_code": iso, "event_name": event_name, "event_date": ev["start_date"], "candidate_hurdat_ids": ev["candidate_hurdat_ids"], "status": status, "reason": "EM-DAT row lacks a unique named HURDAT match with complete overlapping dates"})
    return normalized, evidence, ambiguous


def parse_population(path: Path) -> tuple[list[dict[str, object]], dict[tuple[str, int], dict[str, object]]]:
    rows: list[dict[str, object]] = []
    lookup: dict[tuple[str, int], dict[str, object]] = {}
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for source_row, raw in enumerate(reader, 2):
            iso = raw["ISO3_code"]
            year = int(raw["Time"])
            if iso not in COUNTRY_BY_ISO3 or not 1950 <= year <= 2017:
                continue
            thousands = Decimal(raw["TPopulation1July"])
            persons = int((thousands * 1000).to_integral_value())
            item = {
                "source_row": source_row,
                "paper_country_code": COUNTRY_BY_ISO3[iso][0],
                "country": COUNTRY_BY_ISO3[iso][1],
                "iso3": iso,
                "population_source_location": raw["Location"],
                "year": year,
                "population_1_july_persons": persons,
                "original_population_thousands": raw["TPopulation1July"],
                "variant": raw["Variant"],
                "source_dataset": "UN_WPP_2024",
                "source_reference": "UN_WPP_2024_MEDIUM_DEMOGRAPHIC_INDICATORS",
                "source_locator": f"row:{source_row}",
                "transformation_rule": "TPopulation1July (thousands) multiplied by 1000 and rounded to nearest person",
                "provenance_class": "DERIVED",
            }
            rows.append(item)
            lookup[(iso, year)] = item
    return rows, lookup


def _hurdat_category_on_date(storm: dict[str, object], target: date) -> str:
    observations = [
        x for x in storm["observations"]
        if abs((date.fromisoformat(str(x["observation_date"])) - target).days) <= 1
        and x["max_wind_knots"] != ""
    ]
    if not observations:
        return ""
    wind = max(int(x["max_wind_knots"]) for x in observations)
    return category_from_knots(wind)


def _hurdat_category_in_window(storm: dict[str, object], start: date, end: date) -> str:
    """Return maximum HURDAT category inside an EM-DAT country-impact window."""
    observations = [
        x for x in storm["observations"]
        if start <= date.fromisoformat(str(x["observation_date"])) <= end
        and x["max_wind_knots"] != ""
    ]
    if not observations:
        return ""
    wind = max(int(x["max_wind_knots"]) for x in observations)
    return category_from_knots(wind)


def build_canonical(
    summaries: dict[str, dict[str, object]],
    chn_rows: list[dict[str, object]],
    emdat_rows: list[dict[str, object]],
    population: dict[tuple[str, int], dict[str, object]],
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    confirmed: dict[tuple[str, str], dict[str, list[dict[str, object]]]] = defaultdict(lambda: {"CHN": [], "EMDAT": []})
    conflicts: list[dict[str, object]] = []
    for row in chn_rows:
        if not str(row["match_status"]).startswith("CONFIRMED"):
            continue
        storm = summaries[str(row["hurdat_storm_id"])]
        impact_date = date.fromisoformat(str(row["event_date"]))
        hurdat_cat = _hurdat_category_on_date(storm, impact_date)
        chn_cat = str(row["chn_original_category"]).upper()
        row["chn_country_impact_category"] = chn_cat
        row["hurdat_country_impact_category"] = hurdat_cat
        comparable_chn_cat = "TS_OR_LOWER" if chn_cat == "TS" else chn_cat
        row["category_conflict_flag"] = "YES" if hurdat_cat and hurdat_cat != comparable_chn_cat else "NO"
        row["adopted_country_impact_category"] = hurdat_cat
        row["country_impact_category_status"] = "RESOLVED" if hurdat_cat else "UNRESOLVED"
        row["adoption_rule"] = "HURDAT category within +/-1 day of CHN country-impact date; adopt HURDAT when it differs from CHN"
        confirmed[(str(row["hurdat_storm_id"]), str(row["affected_country_code"]))]["CHN"].append(row)
        if row["category_conflict_flag"] == "YES":
            conflicts.append({
                "conflict_id": f"CATEGORY-{row['chn_evidence_id']}", "conflict_type": "HURDAT_CHN_COUNTRY_IMPACT_CATEGORY",
                "hurdat_storm_id": row["hurdat_storm_id"], "country_code": row["affected_country_code"],
                "source_a": "NOAA_NHC_HURDAT2", "value_a": hurdat_cat,
                "source_b": "CARIBBEAN_HURRICANE_NETWORK", "value_b": chn_cat,
                "resolution": "ADOPT_HURDAT_PRESERVE_BOTH", "status": "RESOLVED_BY_AUTHOR_REPORTED_RULE",
                "notes": "HURDAT value is country-impact-date +/-1 day intensity, not storm-lifetime maximum; both originals remain in evidence.",
            })
    for row in emdat_rows:
        if str(row["match_status"]).startswith("CONFIRMED"):
            confirmed[(str(row["hurdat_storm_id"]), str(row["affected_country_code"]))]["EMDAT"].append(row)

    event_country: list[dict[str, object]] = []
    for (storm_id, iso), grouped in sorted(confirmed.items()):
        storm = summaries[storm_id]
        chn = grouped["CHN"]
        emdat = grouped["EMDAT"]
        sources = "BOTH" if chn and emdat else ("CHN" if chn else "EMDAT")
        no_values = sorted({str(x["no_affected"]) for x in emdat if x["no_affected"] != ""})
        total_values = sorted({str(x["total_affected"]) for x in emdat if x["total_affected"] != ""})
        no_status = "MISSING" if not no_values else ("OBSERVED" if len(no_values) == 1 else "CONFLICT")
        total_status = "MISSING" if not total_values else ("OBSERVED" if len(total_values) == 1 else "CONFLICT")
        if no_status == "CONFLICT" or total_status == "CONFLICT":
            conflicts.append({
                "conflict_id": f"AFFECTED-{storm_id}-{iso}", "conflict_type": "EMDAT_AFFECTED_VALUES",
                "hurdat_storm_id": storm_id, "country_code": iso, "source_a": "EM_DAT_ROWS",
                "value_a": "|".join(no_values), "source_b": "EM_DAT_ROWS", "value_b": "|".join(total_values),
                "resolution": "LEAVE_CONFLICTING_FIELD_BLANK", "status": "UNRESOLVED",
                "notes": "No imputation or silent aggregation performed.",
            })
        pop = population.get((iso, int(storm["season_year"])))
        no_value = no_values[0] if no_status == "OBSERVED" else ""
        total_value = total_values[0] if total_status == "OBSERVED" else ""
        pop_value = str(pop["population_1_july_persons"]) if pop else ""
        def pct(value: str) -> str:
            if not value or not pop_value or Decimal(pop_value) == 0:
                return ""
            return format((Decimal(value) / Decimal(pop_value) * 100).quantize(Decimal("0.000001")), "f")
        country_name = COUNTRY_BY_ISO3[iso][1]
        evidence_ids = [str(x["chn_evidence_id"]) for x in chn] + [str(x["emdat_evidence_id"]) for x in emdat]

        chn_dates = sorted({str(x["event_date"]) for x in chn})
        emdat_windows = sorted({(str(x["start_date"]), str(x["end_date"])) for x in emdat})
        impact_start = ""
        impact_end = ""
        impact_date = ""
        impact_date_status = "UNRESOLVED"
        impact_date_basis = ""
        if chn and len(chn_dates) > 1:
            conflicts.append({
                "conflict_id": f"IMPACT-DATE-{storm_id}-{iso}", "conflict_type": "MULTIPLE_CHN_COUNTRY_IMPACT_DATES",
                "hurdat_storm_id": storm_id, "country_code": iso, "source_a": "CHN_LOCATIONS",
                "value_a": "|".join(chn_dates), "source_b": "", "value_b": "",
                "resolution": "LEAVE_COUNTRY_IMPACT_DATE_BLANK", "status": "CONFLICT",
                "notes": "No rule authorizes earliest/latest aggregation across CHN sites.",
            })
            impact_date_status = "CONFLICT"
            impact_date_basis = "MULTIPLE_CHN_DATES"
        elif chn:
            chn_date = chn_dates[0]
            impact_start = chn_date
            impact_end = chn_date
            if emdat:
                if len(emdat_windows) == 1:
                    impact_start, impact_end = emdat_windows[0]
                windows_contain_chn = all(start <= chn_date <= end for start, end in emdat_windows)
                if windows_contain_chn:
                    impact_date = chn_date
                    impact_date_status = "RESOLVED"
                    impact_date_basis = "CHN_DATE_WITHIN_EMDAT_WINDOW"
                else:
                    impact_date_status = "CONFLICT"
                    impact_date_basis = "CHN_EMDAT_DATE_CONFLICT"
                    conflicts.append({
                        "conflict_id": f"CHN-EMDAT-DATE-{storm_id}-{iso}", "conflict_type": "CHN_EMDAT_IMPACT_DATE_CONFLICT",
                        "hurdat_storm_id": storm_id, "country_code": iso, "source_a": "CHN_LOCATIONS",
                        "value_a": chn_date, "source_b": "EM_DAT_ROWS",
                        "value_b": "|".join(f"{start}/{end}" for start, end in emdat_windows),
                        "resolution": "LEAVE_COUNTRY_IMPACT_DATE_BLANK", "status": "CONFLICT",
                        "notes": "CHN point date is outside at least one confirmed EM-DAT impact interval.",
                    })
            else:
                impact_date = chn_date
                impact_date_status = "RESOLVED"
                impact_date_basis = "CHN_EXPLICIT_DATE"
        elif len(emdat_windows) == 1:
            impact_start, impact_end = emdat_windows[0]
            if impact_start == impact_end:
                impact_date = impact_start
                impact_date_status = "RESOLVED"
                impact_date_basis = "EMDAT_SINGLE_DAY"
            else:
                impact_date_status = "INTERVAL_ONLY"
                impact_date_basis = "EMDAT_DATE_WINDOW"
                conflicts.append({
                    "conflict_id": f"EMDAT-INTERVAL-{storm_id}-{iso}", "conflict_type": "EMDAT_IMPACT_INTERVAL_ONLY",
                    "hurdat_storm_id": storm_id, "country_code": iso, "source_a": "EM_DAT_ROWS",
                    "value_a": f"{impact_start}/{impact_end}", "source_b": "", "value_b": "",
                    "resolution": "RETAIN_INTERVAL_LEAVE_POINT_DATE_BLANK", "status": "INTERVAL_ONLY",
                    "notes": "No source-supported unique country-impact date exists.",
                })
        elif emdat_windows:
            impact_date_status = "CONFLICT"
            impact_date_basis = "MULTIPLE_EMDAT_WINDOWS"
            conflicts.append({
                "conflict_id": f"EMDAT-WINDOW-{storm_id}-{iso}", "conflict_type": "MULTIPLE_EMDAT_IMPACT_WINDOWS",
                "hurdat_storm_id": storm_id, "country_code": iso, "source_a": "EM_DAT_ROWS",
                "value_a": "|".join(f"{start}/{end}" for start, end in emdat_windows), "source_b": "", "value_b": "",
                "resolution": "LEAVE_IMPACT_TIMING_BLANK", "status": "CONFLICT",
                "notes": "No union, earliest, or latest aggregation rule is authorized.",
            })

        chn_categories = sorted({str(x.get("adopted_country_impact_category", "")) for x in chn if x.get("adopted_country_impact_category")})
        impact_category = ""
        impact_category_status = "UNRESOLVED"
        impact_category_basis = ""
        if chn:
            impact_category_basis = "HURDAT_AT_CHN_IMPACT_DATE_PLUS_MINUS_1_DAY"
            if len(chn_categories) == 1 and all(str(x.get("country_impact_category_status")) == "RESOLVED" for x in chn):
                impact_category = chn_categories[0]
                impact_category_status = "RESOLVED"
            elif len(chn_categories) > 1:
                impact_category_status = "CONFLICT"
                conflicts.append({
                    "conflict_id": f"IMPACT-CATEGORY-{storm_id}-{iso}", "conflict_type": "MULTIPLE_CHN_COUNTRY_IMPACT_CATEGORIES",
                    "hurdat_storm_id": storm_id, "country_code": iso, "source_a": "CHN_LOCATIONS",
                    "value_a": "|".join(chn_categories), "source_b": "", "value_b": "",
                    "resolution": "LEAVE_COUNTRY_IMPACT_CATEGORY_BLANK", "status": "CONFLICT",
                    "notes": "No max/min/average/earliest/latest aggregation rule is authorized.",
                })
        elif len(emdat_windows) == 1:
            start_date, end_date = (date.fromisoformat(x) for x in emdat_windows[0])
            impact_category = _hurdat_category_in_window(storm, start_date, end_date)
            impact_category_status = "RESOLVED" if impact_category else "UNRESOLVED"
            impact_category_basis = "MAX_HURDAT_CATEGORY_WITHIN_EMDAT_IMPACT_WINDOW"

        event_country.append({
            "event_id": storm_id, "source_storm_id": storm_id, "storm_name": storm["storm_name"],
            "season_year": storm["season_year"], "event_date": storm["start_date"].isoformat(),
            "storm_start_date": storm["start_date"].isoformat(), "storm_end_date": storm["end_date"].isoformat(),
            "two_week_period": "", "historical_category": storm["historical_category"],
            "severity_class": severity(str(storm["historical_category"])),
            "storm_lifetime_category": storm["historical_category"],
            "storm_lifetime_severity": severity(str(storm["historical_category"])),
            "country_impact_start_date": impact_start, "country_impact_end_date": impact_end,
            "country_impact_date": impact_date, "country_impact_date_status": impact_date_status,
            "country_impact_date_basis": impact_date_basis,
            "country_impact_category": impact_category, "country_impact_category_status": impact_category_status,
            "country_impact_category_basis": impact_category_basis,
            "country_impact_severity": severity(impact_category),
            "affected_country": country_name, "affected_country_code": iso,
            "evidence_basis": sources, "evidence_ids": "|".join(sorted(evidence_ids)),
            "no_affected": no_value, "no_affected_status": no_status,
            "total_affected": total_value, "total_affected_status": total_status,
            "event_year_population": pop_value, "population_unit": "persons" if pop else "",
            "no_affected_pct_population": pct(no_value), "total_affected_pct_population": pct(total_value),
            "native_demand_basis": "NOT_GENERATED_R6I_SCOPE", "native_demand_value": "",
            "native_demand_unit": "", "demand_cap": "",
            "source_dataset": "CHN+EM_DAT" if sources == "BOTH" else ("CARIBBEAN_HURRICANE_NETWORK" if sources == "CHN" else "EM_DAT"),
            "source_reference": "|".join(sorted({str(x["source_reference"]) for x in chn + emdat})),
            "source_locator": "|".join(sorted({str(x["source_locator"]) for x in chn + emdat})),
            "provenance_class": "RECONSTRUCTED", "reconstruction_status": "SOURCE_SUPPORTED",
            "transformation_rule": "included iff at least one confirmed CHN explicit or EM-DAT explicit matched country-impact record; impact timing/category use only country-specific CHN date or EM-DAT window evidence; storm-lifetime maximum is never substituted",
            "notes": "event_date is a compatibility alias for storm_start_date, not country-impact timing. historical_category/severity_class are storm-lifetime aliases, not country-impact intensity. Not an assertion of the unpublished Balcik mapping.",
        })

    event_ids = sorted({str(row["event_id"]) for row in event_country})
    events: list[dict[str, object]] = []
    for event_id in event_ids:
        storm = summaries[event_id]
        events.append({
            "event_id": event_id, "source_storm_id": event_id, "storm_name": storm["storm_name"],
            "season_year": storm["season_year"], "event_date": storm["start_date"].isoformat(),
            "event_end_date": storm["end_date"].isoformat(),
            "storm_start_date": storm["start_date"].isoformat(), "storm_end_date": storm["end_date"].isoformat(),
            "two_week_period": "",
            "historical_category": storm["historical_category"], "severity_class": severity(str(storm["historical_category"])),
            "storm_lifetime_category": storm["historical_category"], "storm_lifetime_severity": severity(str(storm["historical_category"])),
            "max_wind": storm["max_wind_knots"] if storm["max_wind_knots"] is not None else "", "max_wind_unit": "knots",
            "source_dataset": "NOAA_NHC_HURDAT2", "source_reference": "NHC_HURDAT2_ATLANTIC_1851_2025_2026_02_27",
            "source_locator": storm["source_locator"], "provenance_class": "RECONSTRUCTED",
            "reconstruction_status": "SOURCE_SUPPORTED_COUNTRY_EVIDENCE",
            "transformation_rule": "unique HURDAT storm retained when at least one canonical source-supported event-country row exists",
            "notes": "event_date is a compatibility alias for storm_start_date, never a country-impact date. historical_category/severity_class are compatibility aliases for storm-lifetime fields. Two-week period remains unresolved.",
        })
    return events, event_country, sorted(conflicts, key=lambda x: str(x["conflict_id"]))


def country_identity(ledger: dict[str, object]) -> list[dict[str, object]]:
    pages = ledger["rules"]["chn_country_pages"]  # type: ignore[index]
    return [{
        "paper_name": name, "paper_code": paper_code, "normalized_name": name,
        "iso_or_territory_code": iso3, "study_membership_evidence": "Balcik et al. (2019) main-text explicit 20-state list",
        "study_membership_status": "CONFIRMED_STUDY_COUNTRY",
        "chn_identity": "|".join(str(x)[:4] for x in pages[paper_code]),
        "emdat_identity": iso3, "population_source_identity": wpp_name,
        "notes": "Paper-specific code retained separately from ISO3 (BVI/VGB and MST/MSR differ).",
    } for paper_code, name, iso3, wpp_name in COUNTRIES]


def provenance_rows() -> list[dict[str, object]]:
    definitions = [
        ("event_id", "NOAA HURDAT2", "storm header identifier", "DIRECT", "Copied as canonical identity"),
        ("source_storm_id", "NOAA HURDAT2", "storm header identifier", "DIRECT", "Copied as source identity"),
        ("storm_name", "NOAA HURDAT2", "storm header name", "DIRECT", "Copied"),
        ("season_year", "NOAA HURDAT2", "storm identifier year", "DERIVED", "Parsed from storm ID"),
        ("event_date", "NOAA HURDAT2", "first track observation date", "DERIVED", "Minimum observation date"),
        ("event_end_date", "NOAA HURDAT2", "last track observation date", "DERIVED", "Maximum observation date"),
        ("storm_start_date", "NOAA HURDAT2", "first track observation date", "DERIVED", "Minimum observation date; not a country-impact date"),
        ("storm_end_date", "NOAA HURDAT2", "last track observation date", "DERIVED", "Maximum observation date; not a country-impact date"),
        ("two_week_period", "Balcik literature", "unpublished calendar boundary rule", "UNRESOLVED", "Left null; no rule selected"),
        ("historical_category", "NOAA HURDAT2", "full-lifecycle maximum sustained wind", "DERIVED", "Compatibility alias for storm_lifetime_category; never country-impact intensity"),
        ("severity_class", "Balcik et al. (2019)", "storm-lifetime H2 or lower/H3/H4-H5 rule", "DERIVED", "Compatibility alias for storm_lifetime_severity; never country-impact severity"),
        ("storm_lifetime_category", "NOAA HURDAT2", "full-lifecycle maximum sustained wind in knots", "DERIVED", "Saffir-Simpson thresholds over the full storm lifecycle"),
        ("storm_lifetime_severity", "Balcik et al. (2019) + storm_lifetime_category", "H2 or lower/H3/H4-H5 rule", "DERIVED", "Mild/Strong/Very Strong storm-level mapping"),
        ("max_wind", "NOAA HURDAT2", "maximum track wind", "DERIVED", "Maximum nonmissing observation wind"),
        ("max_wind_unit", "NOAA HURDAT2", "data specification", "DIRECT", "Recorded as knots"),
        ("country_impact_start_date", "EM-DAT or CHN", "confirmed country-impact interval/point evidence", "RECONSTRUCTED", "Unique EM-DAT window boundary or CHN point date; blank on conflicting windows"),
        ("country_impact_end_date", "EM-DAT or CHN", "confirmed country-impact interval/point evidence", "RECONSTRUCTED", "Unique EM-DAT window boundary or CHN point date; blank on conflicting windows"),
        ("country_impact_date", "CHN or single-day EM-DAT", "country-specific point-date evidence", "RECONSTRUCTED", "CHN exact date when consistent, or single-day EM-DAT; never storm start date"),
        ("country_impact_date_status", "CHN + EM-DAT timing evidence", "date consistency result", "DERIVED", "RESOLVED, INTERVAL_ONLY, CONFLICT, or UNRESOLVED"),
        ("country_impact_date_basis", "CHN + EM-DAT timing evidence", "date rule identity", "DERIVED", "Explicitly identifies CHN point, EM-DAT single day/window, or conflict"),
        ("country_impact_category", "CHN-timed or EM-DAT-window HURDAT observations", "country-specific impact timing", "RECONSTRUCTED", "CHN: HURDAT within +/-1 day; EM-DAT-only: maximum HURDAT category inside impact window; never lifecycle maximum"),
        ("country_impact_category_status", "country-timed category evidence", "category consistency result", "DERIVED", "RESOLVED, CONFLICT, or UNRESOLVED"),
        ("country_impact_category_basis", "country-timed category evidence", "intensity rule identity", "DERIVED", "CHN +/-1-day or EM-DAT-window rule"),
        ("country_impact_severity", "country_impact_category + Balcik severity rule", "country-specific impact category", "DERIVED", "Mild/Strong/Very Strong only when country-impact category resolves"),
        ("affected_country", "CHN or matched EM-DAT", "explicit island/country evidence", "RECONSTRUCTED", "Included only under frozen Rule A or B"),
        ("affected_country_code", "Balcik country identity + ISO3 crosswalk", "country crosswalk", "RECONSTRUCTED", "Paper code normalized to ISO3/territory code"),
        ("evidence_basis", "CHN and EM-DAT evidence rows", "source membership", "DERIVED", "CHN, EMDAT, or BOTH"),
        ("evidence_ids", "CHN and EM-DAT evidence rows", "source row identities", "DERIVED", "Stable sorted evidence-ID join"),
        ("no_affected", "EM-DAT", "No. Affected", "DIRECT", "Copied when observed; missing remains null"),
        ("no_affected_status", "EM-DAT", "No. Affected missingness", "DERIVED", "OBSERVED, MISSING, or CONFLICT"),
        ("total_affected", "EM-DAT", "Total Affected", "DIRECT", "Copied when observed; missing remains null"),
        ("total_affected_status", "EM-DAT", "Total Affected missingness", "DERIVED", "OBSERVED, MISSING, or CONFLICT"),
        ("event_year_population", "UN WPP 2024", "TPopulation1July in thousands", "DERIVED", "Multiply by 1000"),
        ("population_unit", "UN WPP 2024", "WPP unit metadata", "DERIVED", "Converted output unit persons"),
        ("no_affected_pct_population", "EM-DAT + UN WPP 2024", "No. Affected/population", "DERIVED", "Only when numerator and denominator exist"),
        ("total_affected_pct_population", "EM-DAT + UN WPP 2024", "Total Affected/population", "DERIVED", "Only when numerator and denominator exist"),
        ("native_demand_basis", "R6-I scope decision", "historical source layer boundary", "DIRECT", "Fixed marker NOT_GENERATED_R6I_SCOPE"),
        ("native_demand_value", "none", "not in historical source layer", "UNRESOLVED", "Not generated in R6-I"),
        ("native_demand_unit", "none", "not in historical source layer", "UNRESOLVED", "Not generated in R6-I"),
        ("demand_cap", "none", "not in historical source layer", "UNRESOLVED", "Not generated in R6-I"),
        ("source_dataset", "source acquisition ledger", "source identity", "DIRECT", "Copied or composed without deleting source identity"),
        ("source_reference", "source acquisition ledger", "frozen source identity", "DIRECT", "Stable identity or sorted identity join"),
        ("source_locator", "normalized evidence tables", "row/header locator", "DIRECT", "Stable row locators retained"),
        ("provenance_class", "R6-I provenance policy", "field/row classification", "DERIVED", "DIRECT, RECONSTRUCTED, DERIVED, or UNRESOLVED"),
        ("reconstruction_status", "R6-I inclusion policy", "rule outcome", "DERIVED", "Source-supported status marker"),
        ("transformation_rule", "R6-I inclusion policy", "implemented deterministic rule", "DIRECT", "Human-readable rule copied into each row"),
        ("notes", "R6-I audit policy", "scope and identity disclaimer", "DIRECT", "Human-readable limitation copied into each row"),
    ]
    return [{
        "field_name": field, "source_type": source, "source_reference": source,
        "source_locator": locator, "original_value": "row-specific", "original_unit": "source-specific",
        "transformation_rule": rule, "final_value": "row-specific or null", "final_unit": "schema-specific",
        "provenance_class": provenance, "reconstruction_status": "DOCUMENTED" if provenance != "UNRESOLVED" else "UNRESOLVED",
        "notes": "Row-level source locators are retained in canonical and evidence tables.",
    } for field, source, locator, provenance, rule in definitions]


def reconstruct() -> dict[str, object]:
    ledger = json.loads((RAW / "source_acquisition.json").read_text(encoding="utf-8"))
    by_identity = {str(x["identity"]): x for x in ledger["sources"]}
    hurdat_path = ROOT / str(by_identity["NHC_HURDAT2_ATLANTIC_1851_2025_2026_02_27"]["local_path"])
    emdat_path = ROOT / str(by_identity["EMDAT_PUBLIC_CUSTOM_REQUEST_2026_08_28"]["local_path"])
    wpp_path = ROOT / str(by_identity["UN_WPP_2024_MEDIUM_DEMOGRAPHIC_INDICATORS"]["local_path"])

    hurdat_rows, summaries = parse_hurdat(hurdat_path)
    chn_rows, chn_ambiguous = parse_chn(ledger, summaries)
    normalized_emdat, emdat_evidence, emdat_ambiguous = parse_emdat(emdat_path, summaries)
    population_rows, population_lookup = parse_population(wpp_path)
    events, event_country, conflicts = build_canonical(summaries, chn_rows, emdat_evidence, population_lookup)
    ambiguous = sorted(chn_ambiguous + emdat_ambiguous, key=lambda x: (str(x["source_dataset"]), str(x["evidence_id"])))

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
            "notes": "CHN factual row; HURDAT identity is reconstructed by frozen name/date rule.",
        })
    for row in emdat_evidence:
        evidence.append({
            "evidence_id": row["emdat_evidence_id"], "source_dataset": row["source_dataset"],
            "source_reference": row["source_reference"], "source_locator": row["source_locator"],
            "hurdat_storm_id": row["hurdat_storm_id"], "candidate_hurdat_ids": row["candidate_hurdat_ids"],
            "match_status": row["match_status"], "affected_country": row["affected_country"],
            "affected_country_code": row["affected_country_code"], "evidence_date": row["start_date"],
            "event_name": row["event_name"], "evidence_type": "EMDAT_EXPLICIT_COUNTRY_IMPACT",
            "chn_country_impact_category": "", "hurdat_country_impact_category": "", "conflict_flag": "", "adopted_country_impact_category": "",
            "no_affected": row["no_affected"], "total_affected": row["total_affected"], "provenance_class": "DIRECT",
            "notes": "Confirmed only for a unique named HURDAT storm with complete overlapping dates.",
        })
    evidence.sort(key=lambda x: (str(x["source_dataset"]), str(x["evidence_id"])))

    unresolved: list[dict[str, object]] = [{
        "record_id": f"MATCH-{x['evidence_id']}", "record_type": "SOURCE_MATCH",
        "source_reference": x["source_dataset"], "source_locator": x["source_locator"],
        "field_or_identity": "hurdat_storm_id", "status": x["status"], "observed_evidence": x["candidate_hurdat_ids"],
        "missing_information": x["reason"], "disposition": "excluded from canonical country inclusion; retained in evidence layer",
        "notes": "No manual match added.",
    } for x in ambiguous]
    unresolved.extend([
        {"record_id": "LITERATURE-67-68", "record_type": "LITERATURE_CONFLICT", "source_reference": "Balcik author-chain", "source_locator": "1950-2017 horizon versus reported 67 seasons", "field_or_identity": "historical_season_count", "status": "UNRESOLVED", "observed_evidence": "68 inclusive calendar years; literature reports 67 hurricane seasons", "missing_information": "author season-count convention", "disposition": "nonblocking for historical source layer", "notes": "No correction inferred."},
        {"record_id": "LITERATURE-PERIODIZATION", "record_type": "LITERATURE_CONFLICT", "source_reference": "Balcik author-chain", "source_locator": "May 1-Dec 31 and 16 two-week periods", "field_or_identity": "two_week_period", "status": "UNRESOLVED", "observed_evidence": "16 x 14 days does not cover May 1-Dec 31", "missing_information": "exact unpublished calendar boundaries", "disposition": "left null; scenario periodization is outside R6-I", "notes": "No boundary selected."},
        {"record_id": "LITERATURE-188-IDENTITY", "record_type": "UNPUBLISHED_AUTHOR_DATA", "source_reference": "Balcik et al. (2019)", "source_locator": "reported historical event count", "field_or_identity": "author_final_event_list", "status": "UNRESOLVED", "observed_evidence": "188 reported historical hurricane events", "missing_information": "author final merged row identities and deduplication decisions", "disposition": "188 retained only as literature validation anchor", "notes": "Canonical reconstruction is not count-constrained."},
        {"record_id": "LITERATURE-310-REALIZATIONS", "record_type": "UNPUBLISHED_AUTHOR_DATA", "source_reference": "Balcik et al. (2019)", "source_locator": "62 x 5 scenario construction", "field_or_identity": "generated_scenarios", "status": "NOT_RECONSTRUCTED_R6I_SCOPE", "observed_evidence": "310 model-generated season scenarios", "missing_information": "random seed and realization table", "disposition": "excluded from historical canonical layer", "notes": "Not historical events."},
    ])
    unresolved.sort(key=lambda x: str(x["record_id"]))

    # Normalized/evidence outputs.
    write_csv(INTERMEDIATE / "normalized_hurdat2.csv", HURDAT_COLUMNS, hurdat_rows)
    chn_columns = ["chn_evidence_id", "paper_country_code", "affected_country", "affected_country_code", "chn_site_code", "chn_site_name", "event_date", "storm_name", "wind_mph", "chn_original_category", "chn_country_impact_category", "closest_point_of_approach_miles", "hurdat_storm_id", "match_status", "candidate_hurdat_ids", "hurdat_country_impact_category", "category_conflict_flag", "adopted_country_impact_category", "country_impact_category_status", "adoption_rule", "source_dataset", "source_reference", "source_locator", "source_url", "source_sha256", "proximity_rule", "provenance_class"]
    write_csv(INTERMEDIATE / "normalized_chn.csv", chn_columns, chn_rows)
    emdat_columns = list(normalized_emdat[0].keys())
    write_csv(INTERMEDIATE / "normalized_emdat.csv", emdat_columns, normalized_emdat)
    population_columns = list(population_rows[0].keys())
    write_csv(INTERMEDIATE / "normalized_population.csv", population_columns, population_rows)
    evidence_columns = ["evidence_id", "source_dataset", "source_reference", "source_locator", "hurdat_storm_id", "candidate_hurdat_ids", "match_status", "affected_country", "affected_country_code", "evidence_date", "event_name", "evidence_type", "chn_country_impact_category", "hurdat_country_impact_category", "conflict_flag", "adopted_country_impact_category", "no_affected", "total_affected", "provenance_class", "notes"]
    write_csv(INTERMEDIATE / "storm_country_evidence.csv", evidence_columns, evidence)
    ambiguous_columns = ["evidence_id", "source_dataset", "source_locator", "country_code", "event_name", "event_date", "candidate_hurdat_ids", "status", "reason"]
    write_csv(INTERMEDIATE / "ambiguous_matches.csv", ambiguous_columns, ambiguous)
    conflict_columns = ["conflict_id", "conflict_type", "hurdat_storm_id", "country_code", "source_a", "value_a", "source_b", "value_b", "resolution", "status", "notes"]
    write_csv(INTERMEDIATE / "source_conflicts.csv", conflict_columns, conflicts)
    unresolved_columns = ["record_id", "record_type", "source_reference", "source_locator", "field_or_identity", "status", "observed_evidence", "missing_information", "disposition", "notes"]
    write_csv(INTERMEDIATE / "unresolved_records.csv", unresolved_columns, unresolved)
    country_rows = country_identity(ledger)
    write_csv(INTERMEDIATE / "caribbean_country_identity.csv", list(country_rows[0].keys()), country_rows)

    event_columns = ["event_id", "source_storm_id", "storm_name", "season_year", "storm_start_date", "storm_end_date", "event_date", "event_end_date", "two_week_period", "storm_lifetime_category", "storm_lifetime_severity", "historical_category", "severity_class", "max_wind", "max_wind_unit", "source_dataset", "source_reference", "source_locator", "provenance_class", "reconstruction_status", "transformation_rule", "notes"]
    event_country_columns = ["event_id", "source_storm_id", "storm_name", "season_year", "storm_start_date", "storm_end_date", "event_date", "two_week_period", "storm_lifetime_category", "storm_lifetime_severity", "historical_category", "severity_class", "country_impact_start_date", "country_impact_end_date", "country_impact_date", "country_impact_date_status", "country_impact_date_basis", "country_impact_category", "country_impact_category_status", "country_impact_category_basis", "country_impact_severity", "affected_country", "affected_country_code", "evidence_basis", "evidence_ids", "no_affected", "no_affected_status", "total_affected", "total_affected_status", "event_year_population", "population_unit", "no_affected_pct_population", "total_affected_pct_population", "native_demand_basis", "native_demand_value", "native_demand_unit", "demand_cap", "source_dataset", "source_reference", "source_locator", "provenance_class", "reconstruction_status", "transformation_rule", "notes"]
    write_csv(PROCESSED / "caribbean_historical_events.csv", event_columns, events)
    write_csv(PROCESSED / "caribbean_event_country.csv", event_country_columns, event_country)

    active_seasons = len({int(x["season_year"]) for x in events})
    zero_seasons = 68 - active_seasons
    reconciliation = [
        {"number": 67, "statistical_unit": "historical seasons", "source": "author-reported literature", "meaning": "reported full historical horizon", "relationship": "literature anchor; conflicts with inclusive calendar arithmetic", "verification_status": "UNRESOLVED_LITERATURE_COUNT_CONFLICT", "notes": "1950-2017 inclusive contains 68 calendar years."},
        {"number": 62, "statistical_unit": "active historical seasons", "source": "Balcik et al. (2019)", "meaning": "reported seasons containing relevant hurricanes", "relationship": "subset of author historical horizon", "verification_status": "AUTHOR_REPORTED", "notes": "Not imposed on reconstruction."},
        {"number": 5, "statistical_unit": "severity variants per active season", "source": "Balcik et al. (2019)", "meaning": "model-generated variants", "relationship": "multiplier for synthetic scenarios", "verification_status": "AUTHOR_REPORTED", "notes": "Not generated in R6-I."},
        {"number": 188, "statistical_unit": "historical hurricane events", "source": "Balcik et al. (2019)", "meaning": "reported historical event observations", "relationship": "literature validation anchor only", "verification_status": "AUTHOR_REPORTED_UNPUBLISHED_IDENTITIES", "notes": "Not a construction target or test constraint."},
        {"number": 310, "statistical_unit": "generated hurricane-season scenarios", "source": "Balcik et al. (2019)", "meaning": "62 x 5 severity variants", "relationship": "synthetic/derived", "verification_status": "AUTHOR_REPORTED", "notes": "Not 310 real hurricanes and not canonical R6-I data."},
        {"number": 268, "statistical_unit": "later processed scenarios/seasons", "source": "later author-chain literature", "meaning": "later filtered dataset", "relationship": "separate lineage", "verification_status": "UNRESOLVED_TRANSFORMATION_DETAILS", "notes": "Not mixed into R6-I."},
        {"number": 494, "statistical_unit": "disaster periods/events", "source": "later author-chain literature", "meaning": "later processed event-period observations", "relationship": "separate lineage", "verification_status": "UNRESOLVED_TRANSFORMATION_DETAILS", "notes": "Not mixed into R6-I."},
        {"number": 852, "statistical_unit": "disaster-country combinations", "source": "later author-chain literature", "meaning": "later country-event rows", "relationship": "separate lineage", "verification_status": "UNRESOLVED_TRANSFORMATION_DETAILS", "notes": "Not mixed into R6-I."},
        {"number": len(events), "statistical_unit": "reconstructed unique HURDAT storms", "source": "R6-I current-source reconstruction", "meaning": "storms with at least one source-supported country row", "relationship": "our reconstruction result", "verification_status": "RECONSTRUCTED", "notes": f"Difference from 188: {len(events)-188:+d}; no rule adjusted to reach 188."},
        {"number": active_seasons, "statistical_unit": "reconstructed active seasons", "source": "R6-I current-source reconstruction", "meaning": "calendar years with at least one canonical storm", "relationship": "our reconstruction result", "verification_status": "RECONSTRUCTED", "notes": "Computed over 1950-2017 inclusive."},
        {"number": zero_seasons, "statistical_unit": "reconstructed zero-event seasons", "source": "R6-I current-source reconstruction", "meaning": "calendar years without a canonical storm", "relationship": "68 minus reconstructed active seasons", "verification_status": "DERIVED", "notes": "Uses inclusive 68-year source horizon."},
        {"number": len(event_country), "statistical_unit": "reconstructed event-country rows", "source": "R6-I current-source reconstruction", "meaning": "unique HURDAT storm x source-supported country", "relationship": "our canonical long table", "verification_status": "RECONSTRUCTED", "notes": "CHN and/or unambiguous named EM-DAT evidence required."},
    ]
    recon_columns = ["number", "statistical_unit", "source", "meaning", "relationship", "verification_status", "notes"]
    write_csv(PROCESSED / "caribbean_reconciliation_summary.csv", recon_columns, reconciliation)
    provenance = provenance_rows()
    write_csv(PROVENANCE / "caribbean_field_provenance.csv", list(provenance[0].keys()), provenance)

    outputs = sorted(
        list(INTERMEDIATE.glob("*.csv")) + list(PROCESSED.glob("*.csv")) + list(PROVENANCE.glob("*.csv")),
        key=lambda p: p.as_posix(),
    )
    severity_counts = Counter(str(x["severity_class"]) for x in events)
    country_impact_severity_counts = Counter(str(x["country_impact_severity"]) for x in event_country if x["country_impact_severity"])
    country_impact_category_status_counts = Counter(str(x["country_impact_category_status"]) for x in event_country)
    country_impact_date_status_counts = Counter(str(x["country_impact_date_status"]) for x in event_country)
    for value in ("Mild", "Strong", "Very Strong"):
        country_impact_severity_counts.setdefault(value, 0)
    for value in ("RESOLVED", "CONFLICT", "UNRESOLVED"):
        country_impact_category_status_counts.setdefault(value, 0)
    for value in ("RESOLVED", "INTERVAL_ONLY", "CONFLICT", "UNRESOLVED"):
        country_impact_date_status_counts.setdefault(value, 0)
    conflict_type_counts = Counter(str(x["conflict_type"]) for x in conflicts)
    status_counts = Counter(str(x["status"]) for x in ambiguous)
    manifest = {
        "schema_version": 2, "dataset_identity": "R6_I_SOURCE_BASED_INDEPENDENT_CARIBBEAN_HISTORICAL_RECONSTRUCTION",
        "semantic_revision": "B1 country-timed impact category and B2 country-impact timing separation",
        "identity_disclaimer": "Not the Balcik original dataset, not an author-released dataset, and not exact replication of the unpublished 188-event table.",
        "historical_horizon": {"start_year": 1950, "end_year": 2017, "inclusive_calendar_years": 68},
        "source_acquisition_timestamp_utc": ledger["retrieved_at_utc"],
        "source_library_evidence": ledger["source_library"],
        "source_audits": {"emdat": {"records": len(normalized_emdat), "columns_including_original_only": 47, "start_year_min": min(int(x["Start Year"]) for x in normalized_emdat), "start_year_max": max(int(x["Start Year"]) for x in normalized_emdat), "disaster_type_values": sorted({str(x["Disaster Type"]) for x in normalized_emdat}), "disaster_subtype_values": sorted({str(x["Disaster Subtype"]) for x in normalized_emdat}), "duplicate_disaster_numbers": len(normalized_emdat) - len({str(x["DisNo."]) for x in normalized_emdat}), "missingness": {field: sum(1 for x in normalized_emdat if str(x[field]) == "") for field in ("Event Name", "Location", "Magnitude", "Start Month", "Start Day", "End Month", "End Day", "No. Affected", "Total Affected", "Latitude", "Longitude")}}},
        "parameters": {"start_year": 1950, "end_year": 2017, "chn_proximity_nm": 60, "chn_match_date_tolerance_days": 1, "emdat_requires_nonempty_name": True, "emdat_requires_complete_date_window": True, "emdat_requires_date_overlap": True, "canonical_country_rule": "confirmed CHN explicit evidence OR confirmed EM-DAT explicit matched impact evidence", "chn_country_impact_category_rule": "maximum HURDAT category within +/-1 day of each confirmed CHN impact date; HURDAT precedes CHN on disagreement", "emdat_only_country_impact_category_rule": "maximum HURDAT category within the confirmed EM-DAT country-impact window", "multiple_chn_site_aggregation_rule": None, "storm_lifetime_category_used_as_country_impact_category": False, "author_event_count_constraint": None},
        "sources": [{key: record[key] for key in ("identity", "source_url", "source_role", "local_path", "bytes", "sha256", "committed", "license_note")} for record in ledger["sources"]],
        "review_baseline_counts": {"canonical_events_before_b1_b2_fix": 211, "canonical_event_country_rows_before_b1_b2_fix": 533},
        "counts": {"normalized_hurdat_observations": len(hurdat_rows), "normalized_hurdat_storms": len(summaries), "normalized_chn_rows": len(chn_rows), "normalized_emdat_rows": len(normalized_emdat), "study_region_emdat_rows": len(emdat_evidence), "normalized_population_rows": len(population_rows), "canonical_events": len(events), "canonical_event_country_rows": len(event_country), "active_seasons": active_seasons, "zero_event_seasons": zero_seasons, "ambiguous_or_unmatched_records": len(ambiguous), "source_conflicts": len(conflicts), "unresolved_ledger_records": len(unresolved)},
        "severity_counts": dict(sorted(severity_counts.items())),
        "country_impact_severity_counts": dict(sorted(country_impact_severity_counts.items())),
        "country_impact_category_status_counts": dict(sorted(country_impact_category_status_counts.items())),
        "country_impact_date_status_counts": dict(sorted(country_impact_date_status_counts.items())),
        "conflict_type_counts": dict(sorted(conflict_type_counts.items())),
        "match_status_counts": dict(sorted(status_counts.items())),
        "provenance_counts": dict(sorted(Counter(str(x["provenance_class"]) for x in provenance).items())),
        "outputs": [{"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha256(path), "rows": sum(1 for _ in path.open("r", encoding="utf-8")) - 1} for path in outputs],
        "reconstruction_scripts": [{"path": path.relative_to(ROOT).as_posix(), "sha256": sha256(path)} for path in (ROOT / "scripts/r6i_acquire_caribbean_sources.py", ROOT / "scripts/r6i_reconstruct_caribbean_data.py", Path(__file__))],
        "scientific_scope": {"qfr_parameter_calibration_performed": False, "water_vaccine_crackers_mapping_performed": False, "b_ref_calculated": False, "formal_experiment_matrix_frozen": False, "m0_m1_m2_scientific_runs": 0, "formal_e1_e5_scientific_runs": 0, "gurobi_invoked": False, "family_kit_demand_generated": False, "r6_ii_started": False},
    }
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return manifest
