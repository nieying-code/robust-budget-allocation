# Caribbean Data Provenance (R6-I)

## Provenance classes

- `DIRECT`: the value or identity is present in the cited source.
- `RECONSTRUCTED`: public raw inputs are joined using a documented source-based rule.
- `DERIVED`: a deterministic mechanical calculation from confirmed fields.
- `UNRESOLVED`: evidence is insufficient or the required rule is unpublished; the value remains null or outside scope.

The machine-readable field ledger is `data/formal/caribbean/provenance/caribbean_field_provenance.csv`. Row-level provenance is carried by source dataset, frozen source reference, source locator, evidence ID, reconstruction status, and transformation rule in the normalized, evidence, and canonical tables.

## Source roles and immutability

HURDAT2 is the sole primary storm identity. CHN is explicit 60-nautical-mile island evidence. EM-DAT is explicit country-impact and affected-population evidence only after an unambiguous named/date-overlap HURDAT match. WPP 2024 supplies reconstruction denominators and is never described as Balcik's original population source.

Raw HURDAT2, EM-DAT CSV, and WPP gzip files are committed byte-for-byte with hashes in the acquisition ledger. The user-provided EM-DAT XLSX remains in the read-only library; its filename, size, and SHA-256 are recorded. CHN HTML is excluded from Git because the site states All Rights Reserved. Each exact page URL, byte count, hash, location-to-country mapping, retrieval timestamp, and license note is retained in the ledger.

## Key transformations

| Final field | Source evidence | Rule | Class | Missing/conflict policy |
| --- | --- | --- | --- | --- |
| event/source storm ID | HURDAT header | copy unique Atlantic ID | DIRECT | never substituted with EM-DAT DisNo. |
| storm start/end date | HURDAT observations | min/max observation date | DERIVED | storm lifecycle boundaries; never country-impact timing |
| event date/end date | HURDAT observations | compatibility aliases for storm start/end | DERIVED | explicitly not impact dates |
| storm lifetime category | HURDAT observations | full-lifecycle maximum nonmissing knots; fixed Saffir-Simpson thresholds | DERIVED | descriptive storm identity only |
| storm lifetime severity | storm lifetime category + literature rule | ≤H2 Mild; H3 Strong; H4/H5 Very Strong | DERIVED | must not be consumed as country-impact severity |
| affected country | confirmed CHN and/or confirmed EM-DAT row | Rule A OR Rule B | RECONSTRUCTED | HURDAT-only proximity cannot confirm impact |
| country-impact point date | CHN date and/or EM-DAT interval | CHN exact date if consistent; EM-DAT-only only when single day | RECONSTRUCTED | multi-day interval leaves point blank; conflicts remain blank |
| country-impact start/end | EM-DAT interval or CHN point evidence | retain unique source-supported boundaries | RECONSTRUCTED | no earliest/latest aggregation across conflicting windows |
| CHN-supported country-impact category | CHN date + HURDAT track | HURDAT category within frozen ±1 day; retain CHN original and adopt HURDAT on disagreement | RECONSTRUCTED | multiple site results remain blank with CONFLICT |
| EM-DAT-only country-impact category | EM-DAT impact window + HURDAT track | maximum HURDAT category inside the window | RECONSTRUCTED | no lifecycle-max fallback when the window has no observation |
| country-impact severity | resolved country-impact category + literature rule | ≤H2 Mild; H3 Strong; H4/H5 Very Strong | DERIVED | blank when category is unresolved/conflicting |
| affected values | EM-DAT | copy a unique observed value | DIRECT | missing stays blank; conflicting values stay blank and are logged |
| event-year population | WPP 1 July population | thousands × 1,000 | DERIVED | no neighbor-country substitution |
| affected percentage | EM-DAT numerator + WPP denominator | numerator / denominator × 100 | DERIVED | generated only when both are supported |
| two-week period | unpublished author rule | none | UNRESOLVED | blank in all canonical rows |
| native demand | outside R6-I | none | UNRESOLVED | no zero, imputation, family-kit, or cap value generated |

## Conflict and ambiguity retention

`ambiguous_matches.csv` retains every selected CHN/EM-DAT row that does not satisfy the frozen unique-match rule, including candidate HURDAT IDs. `source_conflicts.csv` retains country-timed HURDAT/CHN category disagreements, multiple-site category/date conflicts, CHN/EM-DAT timing conflicts, and EM-DAT interval-only records. `unresolved_records.csv` combines row-level failures with the 67/68 count conflict, periodization conflict, unpublished 188 identities, and excluded 310 realization layer.

The semantic separation is strict: `storm_lifetime_category != country_impact_category` in meaning even when values happen to match, and `storm_start_date != country_impact_date` in meaning even when dates happen to coincide. No downstream stage may substitute one level for the other.

No row is manually promoted, deleted, or altered to approach 188. The actual canonical event count is a reconstruction output.

## Evidence chain audit

For an event-country row, auditors can follow:

`event_id + evidence_ids -> storm_country_evidence.csv -> normalized_chn.csv and/or normalized_emdat.csv -> source_locator -> frozen source file/hash`

For storm identity and severity:

`event_id -> normalized_hurdat2.csv -> header/observation source locator -> frozen HURDAT2 file/hash`

For population and percentages:

`country ISO3 + season year -> normalized_population.csv -> WPP source row -> frozen WPP gzip/hash`

The manifest records hashes and row counts for every derived CSV plus SHA-256 identities for both reconstruction scripts and the reconstruction module.
