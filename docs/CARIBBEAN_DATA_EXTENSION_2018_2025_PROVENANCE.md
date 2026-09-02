# Caribbean Extension Provenance, 2018–2025

## Layer boundaries

The immutable source layer contains the byte-identical new EM-DAT workbook plus the existing hashed HURDAT2, CHN, and WPP sources. Normalized extension tables preserve source identities and locators. Evidence tables retain source-specific observations before canonical aggregation. Canonical extension tables contain only source-supported reconstructed rows. Combined tables are a deterministic union of the frozen 1950–2017 canonical tables and the independently built 2018–2025 tables.

No file in the frozen 1950–2017 reconstruction is rewritten by the extension script. Its manifest and all recorded output hashes are hard preconditions and postconditions.

## Source roles

- NOAA/NHC Atlantic HURDAT2: primary storm identity, lifecycle dates, track observations, winds, lifecycle maximum category, and timed/windowed impact-category reconstruction.
- Caribbean Hurricane Network: explicit island evidence, local impact dates, and original local category evidence where present. The frozen snapshot has no post-2019 observations.
- EM-DAT 2026-08-28 custom request: explicit matched country-impact evidence, country impact intervals, and observed affected-population fields for 2018–2025.
- UN WPP 2024: event-year country/territory population under the existing R6-I country mapping. It is a project reconstruction source, not attributed to Balcik's unpublished data construction.

## Canonical field semantics

The machine-readable field ledger is `extension_2018_2025/provenance/caribbean_field_provenance_2018_2025.csv`. It documents every canonical column. The following distinctions are scientifically binding:

- `storm_start_date` is not `country_impact_date`.
- `storm_lifetime_category` is not `country_impact_category`.
- Storm-lifetime category is a storm-level descriptive maximum only.
- Country-impact category is reconstructed at CHN country-impact timing ±1 day or within an EM-DAT country-impact window.
- Blank unresolved or conflicting values are not zero.
- `event_date`, `historical_category`, and `severity_class` are legacy storm-level aliases only.

Each event-country row carries evidence IDs, evidence basis, source dataset/reference/locator, transformation rule, provenance class, reconstruction status, timing basis/status, intensity basis/status, and affected-population status.

## Audit ledgers

- `storm_country_evidence_2018_2025.csv` retains CHN and EM-DAT evidence separately.
- `ambiguous_matches_2018_2025.csv` retains noncanonical matching candidates; it is empty for this source snapshot under the frozen rule.
- `source_conflicts_2018_2025.csv` retains resolved source disagreements, interval-only timing, and unresolved conflicts.
- `unresolved_records_2018_2025.csv` retains source limitations and deliberately deferred work.
- `source_conflicts_1950_2025.csv` and `unresolved_records_1950_2025.csv` preserve the full combined audit trail.
- `affected_population_missingness_1950_2025.csv` reports old, extension, and combined missingness without supplementation.
- `frozen_1950_2017_regression.json` records the field-for-field and hash regression result.

The manifest `CARIBBEAN_DATA_EXTENSION_2018_2025_MANIFEST.json` records all generated data/audit hashes, source identity, counts, rule flags, script hashes, regression evidence, and explicit confirmation that Gurobi, Formal experiments, R6-II, B_ref, and affected-population supplementation were not performed.
