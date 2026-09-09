# Final E1 Evidence Promotion v1

Status: `READY_FOR_INDEPENDENT_REVIEW`

This delivery re-registers the audited scientific content of PR #27 Layer B as
canonical Final E1 evidence. It performs no optimization and changes neither the
Final Formal Scientific Design nor `A1_FINAL_NO_MEMORY_V1`.

## Source and authorization chain

- clean base: `main@5f1d20a1c1cff18eceeb1f840866495e98df9812`
- immutable source: PR #27 head
  `675759cf955788d0200e8c1f24e7e1aff13af44b`
- source directory:
  `simulation_results/qfr_mechanism_layer_b_rawls24_n1000/`
- PR #28 audit:
  `docs/evidence/PR27_FINAL_E1_IDENTITY_AUDIT_v1.json`
- PR #29 implementation evidence:
  `docs/evidence/FINAL_A1_ENGINEERING_PROMOTION_v1.json`

The PR #28 audit records 25/25 identity checks passing, 53 committed artifact
hashes verified, 1000 traces checked, byte-identical LHS reconstruction, and no
scientific effect from the historical Memory phase. In particular, Memory hits
and candidate-plan changes were both zero, while all relevant misses continued
to Full Exact Certification.

This authorizes scientific-output reuse only. It does not authorize reuse of
runtime, scenario-evaluation counts, Memory metrics, historical algorithm labels,
ablation claims, or any E5 computational evidence.

## Promotion method

`scripts/promote_final_e1_evidence.py` reads the immutable PR #27 Git blobs and
fails closed unless all frozen identities and source hashes match. It then:

1. preserves the frozen 1000-row parameter table byte-for-byte;
2. joins every certified source row to its parameter row and input hash;
3. extracts a strict whitelist of scientific Q/F/R, cost, recourse, shortage,
   worst-scenario, and certificate fields;
4. translates the inert historical execution label to
   `A1_FINAL_NO_MEMORY_V1` only in the scientific registration layer;
5. recomputes policy labels and item activations using tolerance `1e-7`;
6. rebuilds all summaries from promoted rows; and
7. seals every output with SHA-256 hashes.

The script does not invoke Pyomo, Gurobi, A0, A1, or any experiment runner.
Scientific optimization runs are exactly zero.

## Canonical outputs

The canonical directory is `formal_results/e1_final/`:

- `e1_samples.csv`: frozen parameter rows;
- `e1_scientific_results.csv`: one whitelisted scientific row per sample;
- `e1_policy_summary.json`: recomputed P1--P5 counts and shares;
- `e1_commodity_summary.json`: item activation, reliability, coexistence, and
  portfolio summaries;
- `e1_worst_scenario_summary.json`: recomputed worst-scenario frequencies;
- `e1_output_schema.json`: explicit permitted and prohibited schema;
- `e1_provenance_manifest.json`: complete source, audit, translation, and hash
  lineage; and
- `HASHES.sha256`: deterministic output hash inventory.

These outputs may support E2 baseline reuse, E3 F-active filtering and
representative analysis, and E4 full24 baseline comparisons. They must not be
used as E5 timing, speedup, Memory-contribution, or algorithm-process evidence.

## Recomputed validation targets

- policies: P1 208, P2 26, P3a 4, P3b 3, P4 759, P5 0;
- aggregate reliability: NONE 1840, R0 1023, R1 86, R2 51;
- mixed aggregate Q+F: 33;
- same-item Q/F coexistence: 0;
- mixed specialization: Water-Q + Crackers-F 24; Water-Q + Vaccine-F 9;
- worst scenario: h09 / Katrina for 1000 of 1000 rows.

The policy shares describe coverage of the frozen parameter space, not real-world
probabilities.
