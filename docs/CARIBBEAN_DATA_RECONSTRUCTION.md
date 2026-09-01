# Caribbean Formal Data Reconstruction (R6-I)

Status: **source-based historical reconstruction ready for independent review; R6-II not started**

## 1. Scientific identity and scope

This delivery is a **SOURCE-BASED INDEPENDENT CARIBBEAN HISTORICAL RECONSTRUCTION** for 1950–2017. It is not the Balcik original dataset, not an author-released dataset, and not an exact replication of the unpublished 188-event table. The author-reported value 188 is a validation anchor, never a row-count constraint.

The scientific chain is:

`frozen source evidence -> normalized source tables -> explicit match/evidence layer -> canonical HURDAT storm layer -> auditable event-country layer`

No family-kit demand, five-variant season scenarios, commodity mapping, Q-F-R calibration, budget reference, formal experiment matrix, or scientific optimization run is part of R6-I.

## 2. Source hierarchy and identities

| Source | Frozen role | Version/identity | Use |
| --- | --- | --- | --- |
| NOAA/NHC Atlantic HURDAT2 | primary reconstruction source | 1851–2025 file updated 2026-02-27 | storm identity, lifecycle, track observations, maximum wind, category |
| Caribbean Hurricane Network (CHN) | explicit island evidence | current public 1851–2019 climatology pages retrieved 2026-09-01 UTC | named systems within the page-stated 60-nautical-mile convention; local category and closest approach |
| EM-DAT, CRED/UCLouvain | explicit country-impact evidence | public custom request; version 2026-08-28; created 2026-09-01 15:03:30 UTC | country-impact row, dates, No. Affected, Total Affected |
| UN World Population Prospects 2024 | reconstruction population denominator | Medium demographic indicators CSV | event-year 1 July country/territory population |
| Balcik et al. (2019), DOI 10.1111/poms.13053 | primary literature anchor | Production and Operations Management 28(10), 2431–2455 | study-region identity, severity grouping, reported 62/188/310 structure |
| Kasap-Şimşek et al. (2024) | later author-chain evidence | Decision Sciences paper supplied by user | later 268/494/852 lineage and demand-model evidence; never back-written as Balcik observations |

The exact URLs, retrieval timestamp, raw filenames, hashes, source roles, and license notes are frozen in `data/formal/caribbean/raw/source_acquisition.json`. CHN pages state All Rights Reserved, so raw HTML is local-only and ignored by Git. The ledger retains exact URLs and hashes; normalized factual rows and source locators are committed. A future download that differs from the frozen hash fails verification rather than silently changing the dataset.

The EM-DAT programmatic audit found 2,156 records, 47 source columns, start years 1950–2017, disaster type `Storm`, subtype `Tropical cyclone`, and no duplicate `DisNo.` values. Missing values remain missing: Event Name 259, Location 385, Magnitude 1,241, Start Month 4, Start Day 88, End Month 4, End Day 89, No. Affected 878, Total Affected 566, Latitude/Longitude 2,055 each. The 20-country study identity crosswalk yields 216 EM-DAT evidence rows.

## 3. Country and territory identity

Balcik et al. explicitly lists 20 CARICOM study states in the main text. These are recorded as `CONFIRMED_STUDY_COUNTRY` in `caribbean_country_identity.csv`. Paper identities remain separate from source identities: British Virgin Islands is paper code BVI and ISO3 VGB; Montserrat is paper code MST and ISO3 MSR. The later Decision Sciences 18-country set is not treated as the Balcik set.

CHN has no selected explicit location page for Guyana or Suriname. This absence is not converted into evidence of no impact. It only means those countries can enter the canonical event-country table through a confirmed EM-DAT match under the current rules.

## 4. Deterministic reconstruction rules

### 4.1 Storm identity and event definition

HURDAT2 is authoritative for storm identity. A historical event is one unique Atlantic HURDAT storm ID, irrespective of how many countries it affects. The event date is the first HURDAT observation date; the end date is the last observation date; maximum wind is the maximum nonmissing HURDAT wind over the lifecycle.

Saffir-Simpson categories are mechanically derived from knots: H1 64–82, H2 83–95, H3 96–112, H4 113–136, and H5 at least 137. Lower intensity is retained as `TS_OR_LOWER`. The literature severity rule is applied as H2 or lower = Mild, H3 = Strong, and H4/H5 = Very Strong.

### 4.2 CHN evidence and matching

Each selected CHN page explicitly reports systems passing within 60 nautical miles of its location. The normalized row retains page/location identity, date, wind in mph, CHN category, closest point of approach, storm name, URL, hash, and source locator.

A CHN row is confirmed only when its normalized name and date (with a one-day lifecycle tolerance) resolve to exactly one HURDAT storm in the same year. `UNNAMED` rows use date uniqueness but are not forced when multiple candidates exist. Ambiguous and unmatched rows remain in the evidence and ambiguity tables and do not create canonical country rows.

HURDAT's storm-lifetime category and CHN's local 60-nautical-mile category have different meanings. Both are retained. Where they differ, the implemented author-reported precedence rule adopts HURDAT while recording a conflict; no original CHN value is overwritten.

### 4.3 EM-DAT evidence and matching

An EM-DAT row is confirmed only when all of the following hold: its country belongs to the frozen study crosswalk; Event Name is nonempty; normalized name identifies exactly one same-year HURDAT storm; complete start and end dates exist; and the EM-DAT window overlaps the HURDAT lifecycle. Compound names, missing names, incomplete dates, spelling discrepancies, and nonoverlapping windows are retained as ambiguous/unmatched rather than manually repaired.

HURDAT-only spatial proximity never establishes country impact. Such rows may remain `TRACK_DERIVED_CANDIDATE`; none is silently promoted.

### 4.4 Canonical inclusion and population

An event-country key is included if and only if at least one confirmed CHN explicit record or one confirmed EM-DAT country-impact record supports it. Both sources are preserved as `BOTH`; conflicts are not deleted. Multiple source rows collapse only at the unique HURDAT storm × ISO3 key, and every contributing evidence ID and locator is retained.

EM-DAT No. Affected and Total Affected remain `OBSERVED`, `MISSING`, or `CONFLICT`. Missing never becomes zero. Conflicting nonmissing values remain blank in canonical output and are recorded in `source_conflicts.csv`. WPP `TPopulation1July` is in thousands and is mechanically converted to persons. Affected percentages exist only when both numerator and denominator are source-supported.

## 5. Author facts, current evidence, and reconstruction results

These layers must not be conflated.

### A. Author-reported facts

- 62 active historical seasons and 188 historical hurricane events are reported literature facts with unpublished final row identities.
- Five severity variants per active season produce 310 generated season scenarios: `62 × 5 = 310`. These are not 310 historical hurricanes.
- The later values 268, 494, and 852 refer to later processed scenario/period/country-event lineages. Their exact transformation tables remain unresolved and are not mixed into R6-I.

### B. Current-source evidence

- Current NOAA/NHC HURDAT2 provides 1,042 Atlantic storm identities and 29,040 track observations in 1950–2017 before regional evidence filtering.
- Current CHN selected pages provide 699 island evidence rows in the horizon; 690 resolve under the frozen rule and nine remain ambiguous/unmatched.
- The 2026 EM-DAT extract contains 2,156 total records and 216 rows for the frozen country identity set; 196 resolve under the strict rule and 20 remain candidate/ambiguous/unmatched.
- WPP provides all 20 country/territory identities for all 68 calendar years, totaling 1,360 normalized rows.

### C. Our reconstruction

- 211 unique source-supported HURDAT storms.
- 533 unique event-country rows: 337 CHN-only, 76 EM-DAT-only, and 120 supported by both.
- 64 active calendar years and four zero-event calendar years within the inclusive 68-year horizon.
- Severity: 124 Mild, 24 Strong, and 63 Very Strong.
- 29 ambiguous or unmatched source records, 434 preserved HURDAT/CHN category conflicts, and 33 unresolved-ledger rows including record-level ambiguities and four literature/scope conflicts.
- The event result is 23 above the literature anchor 188. No threshold, source page, match, or inclusion rule was adjusted to reduce this difference.

## 6. Reconciliation and unresolved evidence

The machine-readable reconciliation table separately records 67, 62, 5, 188, 310, 268, 494, 852, and actual reconstructed counts.

- `1950–2017` is 68 inclusive calendar years, while later literature says 67 seasons. This remains `UNRESOLVED_LITERATURE_COUNT_CONFLICT`.
- May 1–December 31 cannot be partitioned exhaustively into 16 periods of 14 days. Exact unpublished period boundaries remain unresolved. `two_week_period` is null in canonical tables because periodized scenario generation is outside this historical source layer.
- The final author 188-row identities, three-source deduplication choices, 2018 CHN snapshot, scenario random seed, 310 realizations, and later 268/494/852 transformations are unavailable. They are documented, not guessed.
- EM-DAT compound/misspelled names and incomplete date rows are preserved in `ambiguous_matches.csv`. No event-specific manual supplement was needed to form the source-supported layer; therefore none was invented.
- CHN current pages end in 2019 and are not the unknown 2018 author snapshot. The exact page identity and retrieval date prevent this distinction from disappearing.

## 7. Delivered tables

Normalized sources:

- `data/formal/caribbean/intermediate/normalized_hurdat2.csv`
- `data/formal/caribbean/intermediate/normalized_chn.csv`
- `data/formal/caribbean/intermediate/normalized_emdat.csv`
- `data/formal/caribbean/intermediate/normalized_population.csv`

Evidence/audit layer:

- `storm_country_evidence.csv`
- `ambiguous_matches.csv`
- `source_conflicts.csv`
- `unresolved_records.csv`
- `caribbean_country_identity.csv`

Canonical layer:

- `data/formal/caribbean/processed/caribbean_historical_events.csv` — one row per unique source-supported HURDAT storm.
- `data/formal/caribbean/processed/caribbean_event_country.csv` — one row per source-supported storm × country/territory.
- `data/formal/caribbean/processed/caribbean_reconciliation_summary.csv` — literature anchors and actual reconstruction results with distinct statistical units.

All CSV files are UTF-8, have stable column order and LF line endings, and are script-generated. Nulls remain empty and are accompanied by explicit status/provenance fields where scientifically material.

## 8. Deterministic rebuild and validation

From the repository root using the existing project environment:

```powershell
.\.venv\Scripts\python.exe scripts\r6i_acquire_caribbean_sources.py --source-library "D:\新建文件夹\项目：robust-budget-allocation"
.\.venv\Scripts\python.exe scripts\r6i_reconstruct_caribbean_data.py
.\.venv\Scripts\python.exe -m pytest tests\test_r6i_caribbean_data.py -q
```

The acquisition command verifies committed raw hashes and restores only license-excluded CHN pages from their exact URLs before checking frozen hashes. It does not change the acquisition timestamp or accept updated content silently. The reconstruction command writes every derived CSV and the manifest. The deterministic test rebuilds and requires identical hashes.

## 9. Limitations and frozen non-actions

The canonical table represents source-supported evidence under explicit R6-I rules, not all storms that physically affected the Caribbean and not the author's hidden merge. A CHN page set favors islands with public climatology pages; strict EM-DAT matching favors named, completely dated records. These are transparent coverage properties, not repaired by subjective additions.

Demand reconstruction status is **NOT GENERATED — OUTSIDE R6-I HISTORICAL SOURCE-LAYER SCOPE**. Family kits, 12,000 cap, severity-dependent ranges, later tarpaulin conversion, and stochastic realizations remain literature evidence only.

`PR #21 merged = NO`; `PR #21 used as base = NO`; `PR #21 scientific changes inherited = NO`. R6-II is not started.
