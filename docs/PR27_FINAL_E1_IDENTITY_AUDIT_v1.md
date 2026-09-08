# PR #27 Layer B to Final E1 identity audit v1

Status: **STATIC AUDIT COMPLETE / SCIENTIFIC OPTIMIZATION RUNS = 0**

Audited PR: #27, head `675759cf955788d0200e8c1f24e7e1aff13af44b`, branch
`simulation/qfr-mechanism-layer-a`, OPEN/DRAFT/unmerged. The audit read committed git
blobs directly and did not checkout, modify, merge, cherry-pick, or rerun PR #27.

## Result

`FINAL_E1_REUSE_CANDIDATE = YES`

Scope: **PR #27 Layer B scientific outputs only, pending independent approval**.
PR #27's runtime, scenario-evaluation counts, Memory fields, and historical
`A1_full` algorithm label are not reusable for Final E5 or final algorithm claims.

## Checklist

| # | Field | Status | Key evidence |
|---:|---|---|---|
| 1 | Dataset identity | PASS | `rawls_24_real_single_hurricane_data_recalibration_v1` |
| 2 | Rawls24 scenario identity | PASS | 24 unique single hurricanes |
| 3 | Scenario order | PASS | exact `h01..h24` |
| 4 | Commodity identity | PASS | Water, Vaccine, Crackers |
| 5 | Commodity static parameters | PASS | formal template hash `eae86e57...1e02` |
| 6 | Demand mapping | PASS | Water direct; Medical x 10.0603621730382; Food x 14 |
| 7 | h/a | PASS | `(0,1)`, `(.083333.../month,1)`, `(0,.9)` |
| 8 | beta | PASS | 4 |
| 9 | lambda | PASS | `(1,1,1)` reconstructed from shortage costs |
| 10 | Absolute B | PASS | `19,137,905.85543848` |
| 11 | B_ref definition | PASS | `sum_i((cQ_i+h_i*tau)*Dref_i/a_i)` |
| 12 | Parameter-table identity | PASS | LA-0001..LA-1000, exactly 1,000 rows |
| 13 | Parameter-table SHA-256 | PASS | `ac617bef...31e0` recomputed from PR git blob |
| 14 | Seed | PASS | 20260903 |
| 15 | Sampling | PASS | deterministic constrained LHS v1 |
| 16 | Parameter ranges | PASS | all 16 bounds exact |
| 17 | Monotonic/order constraints | PASS | rho_Q/rho_F/eta/premium rules exact |
| 18 | M2 model identity | PASS | M2 in config, manifest, and 1,000 outputs |
| 19 | A1 mathematical path | PASS | Candidate Search + Full Exact Certification; 1,000 certified |
| 20 | Memory effect on scientific solve | PASS | enabled historically but proven inert; details below |
| 21 | Numerical exact oracle/validation | PASS | scale-aware `1e-7 + 1e-12*family_scale` |
| 22 | Tolerances | PASS | convergence `1e-7+1e-9*scale`; policy `1e-7` |
| 23 | Solver policy | PASS | gurobi_direct, one thread, no fallback, frozen options |
| 24 | Result schema | PASS | 1,000 scientific + 1,000 diagnostic rows; 53 hashes verified |
| 25 | Interpretation | PASS | exploratory status; no tuning; no probability claim |

Machine evidence: `docs/evidence/PR27_FINAL_E1_IDENTITY_AUDIT_v1.json`.

The subsequent machine-definition freeze used the saved PR #27 commodity-level F
quantities solely to apply the pre-registered `F_ACTIVE_ROW` filter for E3-B. It did
not use policy labels, R labels, objective, shortage, runtime, or any computational
or Memory metric to select representative rows. This static read does not change the
25/25 audit or the scientific-only reuse boundary.

## Memory identity finding

PR #27 is historically labeled `A1_full` and explicitly called the production solver
with `memory_phase_enabled=True`. Across all 1,000 saved Layer B raw traces:

- Memory-enabled solves: 1,000;
- Memory opportunities: 1,000;
- planned/executed Memory exact evaluations: 2,000/2,000;
- Memory hits: 0;
- iterations containing Memory evaluation: 1,000;
- Candidate first-choice changes versus the same active set with Memory disabled: 0;
- Memory-miss iterations proceeding to Full Exact Certification: 1,000.

Thus Memory imposed extra computational work but never added a scenario, changed a
Candidate choice, changed the active-set path, supplied an incumbent/UB, or displaced
Full Exact Certification. The realized scientific policy/objective/certificate path
is no-memory-equivalent. This satisfies the user-frozen exception for scientific
reuse candidacy, but it does not make the historical implementation the final A1.
Final A1 remains explicitly no-memory, and PR #27 computational metrics are excluded.

## Compared artifacts

- PR config and run/sample/summary/manifests;
- all 40 compressed raw A1 shards and all 1,000 trace records;
- 1,000 scientific and 1,000 computational rows;
- PR exact-oracle, numerical-validation, protocol, candidate, and orchestrator code;
- all 53 entries in PR #27 Layer B `HASHES.sha256`;
- main Rawls24 input/demand/provenance and formal economic template identities;
- final protocol and machine configuration in this branch.

## Limits and decisions not implied

This audit does not merge or promote PR #27, authorize E1 execution, certify E5
timings, or decide which generic numerical fixes enter main. `YES` means only that
the already-generated Layer B scientific outputs are candidates for direct Final E1
reuse after independent approval.
