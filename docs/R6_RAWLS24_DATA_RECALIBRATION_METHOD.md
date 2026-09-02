# R6 — 24 Real Single-Hurricane Data Recalibration

## Scope

This delivery is **data recalibration only**. It creates an auditable 24-event real single-hurricane data layer containing the original 15 Rawls events and nine added events. It does not recalibrate parameters, re-freeze the Formal design, calculate or freeze `F_bar` or `B_ref`, map the data to Formal commodities, or execute M0/M1/M2, E1, E2–E5, A0, or A1.

## Source-based harmonization

Rawls's 2008 dissertation Table 5-3 preserves the historical Category, Evacuees, Sheltered, Water, Food, and Medical values for the original 15 events. The same dissertation's section 5.3 states one reproducible final demand-generation rule:

- Categories 1–2: Water = `3 × Evacuees`; Food = `15 × Sheltered`.
- Categories 3–5: Water = `10 × Evacuees`; Food = `35 × Sheltered`.
- All categories: Medical = `Sheltered / 4`.

Table 5-3 nevertheless contains two calibration lineages. Its first eight events use approximately `9 × Sheltered` or `21 × Sheltered` for Food and approximately `Sheltered / 50` for Medical, while later rows follow the stated final rule (subject to table-display rounding). Directly appending nine new events to those mixed historical demand columns would therefore put different events on different demand definitions.

The project retains each original Rawls event's identity, Category, Evacuees, Sheltered, qualifiers, and Table 5-3 reported demands in a historical source layer. It then reconstructs Water, Food, and Medical for all 24 events from Category/E/S using the single final rule above. The historical comparison layer exposes every `same`, `changed`, or `rounding-only` cell. Historical source values are not overwritten and cannot silently feed the unified demand master.

This is **source-based harmonization**, not result-driven calibration. No M0/M1/M2 or other scientific result was generated or consulted when selecting or transforming the data.

## Source identity note

The user-supplied PDF named `Pre-positioning of emergency supplies for disaster response.pdf` is, by its metadata and contents, the 14-page Rawls and Turnquist (2010) *Transportation Research Part B* article. It is retained as a journal cross-check. The required dissertation evidence was audited against the official Cornell eCommons copy of Carmen Gloria Rawls's August 2008 dissertation. The exact local-attachment, workbook, and official-dissertation SHA-256 identities are recorded in the provenance manifest.

## Event scope and bounded evidence

The authoritative workbook freezes the 2004 events Charley, Frances, Ivan, and Jeanne to Florida-statewide paired E/S values from the same official summary. Broader multi-state totals and narrower regional values are not mixed into those pairs.

Rita remains bounded evidence: `E ≈ / up to 2,000,000` and `S ≥ 150,000`; these are not exact observations. Elena uses a Pinellas County same-scope conservative lower-bound representation, `E = 300,000` and `S = 150,000`, derived from official statements of more than 300,000 evacuated and roughly half in public shelters; these are also not exact counts. Those qualifications propagate to the derived demand interpretation.

## Deterministic rebuild

Run:

```text
python scripts/r6_rawls24_data_recalibration.py
python scripts/r6_rawls24_data_recalibration.py --check
```

The builder uses only the frozen configuration, Python standard library, and project hashing helpers. It emits LF-normalized CSV/JSON evidence, a canonical data identity, and `HASHES.sha256`. No solver or model module is imported.
