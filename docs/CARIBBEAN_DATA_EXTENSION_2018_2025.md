# Caribbean Historical Reconstruction Extension, 2018–2025

## Scientific identity and scope

This asset is a source-based independent extension of the reviewed R6-I Caribbean historical hurricane reconstruction. It is not an author-released Balcik dataset and is not an exact reproduction of the unpublished 188-event table. The extension independently reconstructs 2018–2025 and combines it with the frozen 1950–2017 output by union; it does not rebuild or reinterpret the old segment.

No affected-population supplementation, family-kit demand generation, 310-scenario construction, two-week periodization, commodity mapping, Q-F-R calibration, B_ref calculation, Formal experiment, or solver invocation is part of this extension.

## New source and reused sources

The sole new EM-DAT input is `public_emdat_custom_request_2026-09-02_29fd291d-8941-49e3-8719-e8911b23e14e.xlsx`. It was read from the external source library, validated before copying, and preserved unchanged in the repository raw layer.

- EM-DAT identity: public custom request; EM-DAT, CRED / UCLouvain
- EM-DAT version: 2026-08-28
- File creation: 2026-09-02 03:13:19 UTC
- Records: 492
- Columns: 47
- Years: exactly 2018–2025
- Disaster subtype: exactly `Tropical cyclone`
- SHA-256: `1fb5bcb8228cf45a6baa0c39bcd3492e741f488d1ff385c81dc73e219156a600`

The extension reuses the already acquired and hashed NOAA/NHC Atlantic HURDAT2, UN WPP 2024, and frozen CHN page set. The current frozen CHN snapshot ends in 2019. Consequently, CHN explicit evidence is available for extension years 2018–2019; 2020–2025 canonical country inclusion can arise only from confirmed EM-DAT evidence under the existing inclusion rule. This is retained as an unresolved source-coverage limitation, not repaired with a new source or rule.

## Frozen reconstruction rules

HURDAT2 remains the storm-identity source. Canonical events use unique HURDAT storm IDs. A storm affecting several countries remains one event, with separate event-country rows.

Canonical country inclusion requires CHN explicit evidence or unambiguously matched EM-DAT country-impact evidence. HURDAT track proximity alone does not confirm country impact.

Storm lifecycle fields retain their reviewed meanings:

- `storm_start_date` and `storm_end_date` are HURDAT lifecycle bounds.
- `storm_lifetime_category` is the maximum category over the full HURDAT lifecycle.
- `storm_lifetime_severity` is mechanically derived from that category.
- Legacy aliases remain exact aliases; they are not country-impact fields.

Country-impact timing and intensity use the existing country-specific rules:

- CHN evidence uses the CHN impact date and the maximum HURDAT category within ±1 day.
- HURDAT takes precedence over CHN category when they conflict; both source values and the conflict remain preserved.
- EM-DAT-only evidence uses the maximum HURDAT category inside the confirmed country-impact window, with no fallback to storm-lifetime maximum.
- Multiple incompatible CHN dates or adopted categories remain conflicts; no maximum, minimum, earliest, or latest aggregation is introduced.
- A CHN point date resolves BOTH-source timing only when it lies within every confirmed EM-DAT interval.
- EM-DAT-only multi-day timing remains `INTERVAL_ONLY`; the point date stays blank.
- `two_week_period` remains blank. No periodization rule is introduced.

The ±1 day and EM-DAT-window intensity operations are project reconstruction rules, not claimed author-disclosed event-by-event methods.

## Outputs and results

The extension contains 17 canonical storms and 42 canonical event-country rows. Annual storm counts are 3, 3, 2, 2, 1, 1, 3, and 2 for 2018 through 2025 respectively. Fourteen of the twenty frozen study-country identities have at least one canonical extension row.

The combined layer contains 228 storms and 575 event-country rows. It is the exact union of the 211/533 frozen old layer and the 17/42 extension.

Extension storm-lifetime severity counts are Mild 10, Strong 2, and Very Strong 5. Extension country-impact severity counts are Mild 31, Strong 3, and Very Strong 8. All 42 country-impact categories are resolved. Country-impact date states are 25 `RESOLVED`, 16 `INTERVAL_ONLY`, 1 `CONFLICT`, and 0 `UNRESOLVED`.

The extension conflict ledger retains five HURDAT/CHN impact-category disagreements resolved by the frozen precedence rule, sixteen EM-DAT interval-only timing records, and one multiple-CHN-date conflict. The extension unresolved ledger separately retains deferred affected-population supplementation and the CHN 2020–2025 coverage limitation. The combined unresolved ledger contains all old and extension records.

## Affected-population inventory

EM-DAT `No. Affected` and `Total Affected` values are retained only when observed. Missing values remain blank; no zero fill, donor transfer, interpolation, neighboring-country rule, severity estimate, or model-derived value is applied.

- Frozen 1950–2017 (533 rows): `No. Affected` 98 observed / 435 missing; `Total Affected` 117 observed / 416 missing. At least one measure is observed for 117 rows; neither is observed for 416.
- Extension 2018–2025 (42 rows): `No. Affected` 17 observed / 25 missing; `Total Affected` 18 observed / 24 missing. At least one measure is observed for 18 rows; neither is observed for 24.
- Combined 1950–2025 (575 rows): `No. Affected` 115 observed / 460 missing; `Total Affected` 135 observed / 440 missing. At least one measure is observed for 135 rows; neither is observed for 440.

## Frozen-base regression and deterministic rebuild

Before and after every extension build, the script verifies the frozen manifest SHA-256 and every output hash recorded in it. The combined projection for years through 2017 is then compared field-for-field with the audited event and event-country tables. The required result is 211 events, 533 event-country rows, identical content, and all 13 frozen output hashes verified. Any difference aborts the build.

Run the solver-free deterministic build from the repository root:

```powershell
.\.venv\Scripts\python.exe scripts\r6i_extend_caribbean_2018_2025.py
```

Run the complete R6-I data test suite:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_r6i_caribbean_data.py tests\test_r6i_caribbean_extension.py -q
```

The extension manifest records source, output, and script hashes and is the authoritative inventory for review.
